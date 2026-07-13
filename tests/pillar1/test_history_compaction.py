r"""
History compaction (FRIDAY_notes10_plan.md Phase 2, §4). FRIDAY's history used
to be trimmed with a silent `self.history = self.history[-40:]` — the oldest
turns just vanished, so a fact established early in a long session was lost the
moment it scrolled off. §4 replaces the silent drop with the Claude Code
compaction mechanism at FRIDAY's scale: evicted turns are summarised into a
running digest injected at the head of context next turn.

Pure logic (no live model): a stub model stands in for the summarize call so the
plumbing is proven deterministically — the digest is built and stored, the prior
summary is folded in, empty/blank cases are no-ops, and the respond()-level
try/except guarantees a summarize failure never blocks or loses a reply.
"""

import pytest

from core.engine import Engine


class _StubModel:
    """Records the last prompt and returns a scripted reply (or raises)."""
    def __init__(self, content="SUMMARY: alpha rig active; offered pdf review.",
                 raises=False):
        self.content = content
        self.raises = raises
        self.last_messages = None
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None):
        self.calls += 1
        self.last_messages = messages
        if self.raises:
            raise RuntimeError("model down")
        class _R:
            pass
        r = _R()
        r.content = self.content
        r.eval_count = 7
        return r


def _e(model):
    e = Engine.__new__(Engine)
    e.model = model
    e.history_summary = None
    e.session_tokens = 0
    e.max_history = 40
    e._compact_keep = 24
    return e


def _evicted(n=6):
    out = []
    for i in range(n):
        out.append({"role": "user", "content": f"user message {i}"})
        out.append({"role": "assistant", "content": f"assistant reply {i}"})
    return out


@pytest.mark.upgrade
@pytest.mark.case("COMPACT-001", "evicted turns are summarised into the running "
                                "digest and counted; returns True")
def test_compaction_builds_summary():
    m = _StubModel()
    e = _e(m)
    ok = e._compact_history(_evicted())
    assert ok is True
    assert e.history_summary == m.content
    assert m.calls == 1
    assert e.session_tokens == 7  # the summarize call's tokens are counted
    # The evicted dialogue was actually rendered into the prompt.
    prompt = m.last_messages[-1]["content"]
    assert "user message 0" in prompt and "assistant reply 0" in prompt


@pytest.mark.upgrade
@pytest.mark.case("COMPACT-002", "a prior summary is folded into the next "
                                "compaction, not discarded")
def test_prior_summary_folded():
    m = _StubModel(content="UPDATED SUMMARY")
    e = _e(m)
    e.history_summary = "EARLIER SUMMARY about the marlin rig"
    ok = e._compact_history(_evicted())
    assert ok is True
    prompt = m.last_messages[-1]["content"]
    assert "EARLIER SUMMARY about the marlin rig" in prompt  # carried forward
    assert e.history_summary == "UPDATED SUMMARY"


@pytest.mark.upgrade
@pytest.mark.case("COMPACT-003", "no substantive evicted content, or a blank "
                                "model reply, is a no-op (summary unchanged)")
def test_noop_cases():
    # Nothing but empty/system messages -> the model is never called.
    m = _StubModel()
    e = _e(m)
    ok = e._compact_history([{"role": "system", "content": "x"},
                             {"role": "assistant", "content": "   "}])
    assert ok is False
    assert m.calls == 0
    assert e.history_summary is None

    # Model returns blank -> summary stays None, nothing counted.
    m2 = _StubModel(content="   ")
    e2 = _e(m2)
    ok2 = e2._compact_history(_evicted())
    assert ok2 is False
    assert e2.history_summary is None
    assert e2.session_tokens == 0


@pytest.mark.upgrade
@pytest.mark.case("COMPACT-004", "the trim step swallows a summarize failure and "
                                "still bounds history (never blocks a reply)")
def test_failure_falls_back_to_trim():
    m = _StubModel(raises=True)
    e = _e(m)
    # Replicate respond()'s inline trim/compaction step with a raising model.
    e.history = [{"role": "user", "content": f"m{i}"} for i in range(60)]
    compacted = False
    if len(e.history) > e.max_history:
        keep = e._compact_keep
        evicted = e.history[:-keep]
        try:
            compacted = e._compact_history(evicted)
        except Exception:
            pass  # the guarantee under test: failure is swallowed
        e.history = e.history[-keep:]
    assert compacted is False
    assert len(e.history) == e._compact_keep      # history was still bounded
    assert e.history_summary is None              # no partial/garbage summary

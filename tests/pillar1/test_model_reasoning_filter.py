r"""THINK — the reasoning-model <think> stripper (deterministic; no Ollama).

Deep mode's candidate brain is a reasoning-distilled 14B that emits its
chain-of-thought inline in <think>…</think> before the answer (Phase 6 of
FRIDAY_notes10_plan.md). Two invariants ride on this filter:

  * the scratchpad must NEVER reach the UI or a brain note (invariant 4 + the
    note-poisoning scar — FRIDAY writes conversation text into authoritative
    notes, and a think trace is discarded wrong-turn reasoning); and
  * it must be filtered out of the LIVE stream, with tags that routinely
    arrive split across chunks handled correctly.

These tests drive the filter the way the stream does — piece by piece,
including tags split mid-token — and assert nothing but the answer survives.
The current chat model emits no tags, so the filter must also be a perfectly
transparent pass-through (regression guard for the resident brain)."""

import pytest

from core.model import _ReasoningFilter, _longest_partial_tag
from core.tools.reasoning_tools import (_looks_like_reasoning_model,
                                        _resolve_strip_reasoning)


def _run(pieces):
    """Feed a list of streamed pieces; return (visible_text, reasoning)."""
    f = _ReasoningFilter()
    visible = "".join(f.feed(p) for p in pieces)
    visible += f.flush()
    return visible, f.reasoning


@pytest.mark.case("THINK-001", "a whole think block in one piece is fully stripped")
def test_single_piece():
    visible, reasoning = _run(["<think>weighing options</think>The answer is 42."])
    assert visible == "The answer is 42."
    assert reasoning == "weighing options"


@pytest.mark.case("THINK-002", "open tag split across chunks does not leak the '<'")
def test_open_tag_split():
    # "<thi" + "nk>" — the classic boundary split that a per-chunk replace misses.
    visible, reasoning = _run(["Here goes ", "<thi", "nk>secret", " work</thi", "nk>Done."])
    assert visible == "Here goes Done."
    assert "secret" not in visible and "<" not in visible
    assert reasoning == "secret work"


@pytest.mark.case("THINK-003", "no tags at all: transparent pass-through (chat-model regression)")
def test_no_tags_passthrough():
    pieces = ["The margin ", "is 1.8x ", "at the critical section."]
    visible, reasoning = _run(pieces)
    assert visible == "The margin is 1.8x at the critical section."
    assert reasoning == ""


@pytest.mark.case("THINK-004", "a lone '<' in normal prose is not swallowed")
def test_bare_angle_bracket():
    # Held back at a boundary as a possible partial tag, then flushed as real text.
    visible, _ = _run(["load < ", "yield, so it holds"])
    assert visible == "load < yield, so it holds"


@pytest.mark.case("THINK-005", "unterminated think block fails closed (never leaks a half-thought)")
def test_unterminated_think_discarded():
    # Model opened <think> and hit the token budget before closing it.
    visible, reasoning = _run(["<think>still reasoning and then cut o"])
    assert visible == ""                       # honest empty answer, not a leak
    assert "still reasoning" in reasoning       # captured for diagnostics only


@pytest.mark.case("THINK-006", "multiple think blocks in one reply are all stripped")
def test_multiple_blocks():
    visible, reasoning = _run(["<think>a</think>First. <think>b</think>Second."])
    assert visible == "First. Second."
    assert reasoning == "ab"


@pytest.mark.case("THINK-007", "partial-tag helper matches only real prefixes")
def test_partial_helper():
    assert _longest_partial_tag("foo<thi", "<think>") == 4      # "<thi"
    assert _longest_partial_tag("foo<", "<think>") == 1         # "<"
    assert _longest_partial_tag("foobar", "<think>") == 0       # nothing
    assert _longest_partial_tag("x</thin", "</think>") == 6     # "</thin"


# --- deep-mode wiring: which brains auto-strip, and Jack's override ---

@pytest.mark.case("THINK-008", "reasoning-model families are recognized by tag; qwen chat is not")
def test_reasoning_model_detection():
    for name in ("deepseek-r1:14b", "DeepSeek-R1-Distill-Qwen-14B",
                 "qwq:32b", "magistral:24b", "phi4-reasoning:14b"):
        assert _looks_like_reasoning_model(name), name
    for name in ("qwen2.5:14b", "qwen2.5:32b", "llama3.1:8b", ""):
        assert not _looks_like_reasoning_model(name), name


@pytest.mark.case("THINK-009", "stripping auto-enables for a reasoning deep model (single-key activation)")
def test_strip_autoenables_for_reasoning_model():
    # Just swapping deep_mode.model to a reasoning brain turns stripping on —
    # no second key needed, so the footgun (leaking <think> to a note) can't
    # be armed by forgetting a flag.
    assert _resolve_strip_reasoning({"model": "deepseek-r1:14b"}) is True
    assert _resolve_strip_reasoning({"model": "qwen2.5:32b"}) is False


@pytest.mark.case("THINK-010", "explicit strip_reasoning override wins in either direction")
def test_strip_override_wins():
    # Force ON for an unrecognized reasoning model name...
    assert _resolve_strip_reasoning(
        {"model": "some-custom-thinker:14b", "strip_reasoning": True}) is True
    # ...and force OFF (Jack's call) even for a recognized one.
    assert _resolve_strip_reasoning(
        {"model": "deepseek-r1:14b", "strip_reasoning": False}) is False

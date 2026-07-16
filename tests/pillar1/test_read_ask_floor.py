r"""
RAF — the read-ask grounding floor (armor RA leg).

The RF-leg probe found the first-order hole under BOTH standing GND
residuals: on a turn-1 "read <path>" the model runs ZERO tools, so the file
is never read, no referent lands, and every downstream barrier (phantom,
anti-dodge, artifact-denial) is structurally unreachable — the raw
embodiment denial ships untouched (GND-011), and the analysis, with nothing
to ground it, dissolves into a dead end (GND-010). The floor is
calendar-first's third instance: message names a real local file with read
intent + no content-delivering tool ran → the ENGINE runs read_file itself
(gate, taint, referents all apply via _run_tool) and regenerates once from
the live content.

Pure logic (no live model): a scripted stub drives the real respond() path,
same posture as test_artifact_denial_floor.py.
"""

import pytest

from core.model import ModelReply


class _ScriptModel:
    """Returns scripted replies in order. An item is either a string (text
    reply) or a dict {"content": ..., "tool_calls": [...]} (a tool round)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        item = self.script.pop(0) if self.script else ""
        r = ModelReply()
        if isinstance(item, dict):
            r.content = item.get("content", "")
            r.tool_calls = list(item.get("tool_calls", []))
        else:
            r.content = item
        r.eval_count = 5
        if on_token and r.content:
            on_token(r.content)
        return r


DENIAL = ("I don't have direct access to physical items or real-time input, "
          "so I'm unable to read files on your machine.")

GROUNDED = ("The 5V rail shared with the PCA9685 worries me - there's no "
            "fuse before the buck converter, so a short takes out the "
            "whole rail.")


def _plant(sandbox, name="wrist_wiring_notes.md"):
    src = sandbox.root / "incoming" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Gripper wiring\n- 5V rail shared by PCA9685 and camera\n"
                   "- No fuse between pack and buck converter\n"
                   "- Servo grounds star-pointed at the driver\n",
                   encoding="utf-8")
    return src


def _engine(sandbox, script):
    eng = sandbox.service.engine
    eng.model = _ScriptModel(script)
    eng.vote_enabled = False
    return eng


@pytest.mark.case("RAF-001", "zero-tool read-ask: the engine reads the file itself, the retry engages the content, taint + referent land")
def test_engine_runs_the_read(sandbox):
    src = _plant(sandbox)
    eng = _engine(sandbox, [DENIAL, GROUNDED])
    reply = eng.respond(f"read {src.as_posix()}")
    # The re-grounded retry replaced the denial.
    assert "fuse" in reply.content and "5V" in reply.content
    assert "unable to read" not in reply.content
    # The read is REAL: the artifact is on the referent stack and the turn
    # is tainted (read-content-is-data) — the floor cannot bypass either.
    assert any(r["kind"] == "file" for r in eng.referents)
    assert eng._taint and "read_file" in eng._taint


@pytest.mark.case("RAF-002", "no false fire: a turn that already read the file is never touched")
def test_model_read_untouched(sandbox):
    src = _plant(sandbox)
    eng = _engine(sandbox, [
        {"content": "",
         "tool_calls": [{"function": {"name": "read_file",
                                      "arguments": {"path": str(src)}}}]},
        GROUNDED,
    ])
    reply = eng.respond(f"read {src.as_posix()}")
    assert reply.content == GROUNDED
    assert eng.model.calls == 2  # tool round + final; no floor retry spent


@pytest.mark.case("RAF-003", "no false fire: a path mention without read intent never forces a read")
def test_no_read_intent_untouched(sandbox):
    src = _plant(sandbox)
    ack = "Noted - I'll keep that location in mind."
    eng = _engine(sandbox, [ack])
    reply = eng.respond(
        f"the wiring notes live at {src.as_posix()}, just so you know")
    assert reply.content == ack
    assert eng.model.calls == 1  # no retry spent
    assert not any(r["kind"] == "file" for r in eng.referents)


@pytest.mark.case("RAF-004", "no false fire: a mistyped/missing path never burns a retry — the model's own answer stands")
def test_missing_path_untouched(sandbox):
    honest = ("I can't find that file - double-check the path and I'll "
              "read it.")
    eng = _engine(sandbox, [honest])
    reply = eng.respond("read C:/nope/definitely_missing_notes.md")
    assert reply.content == honest
    assert eng.model.calls == 1


@pytest.mark.case("RAF-006", "INJ-004 shape: a FAILED web_fetch (arg-guard refusal narrated as the answer) does not close the hole — the floor still reads Jack's path")
def test_failed_fetch_does_not_block(sandbox):
    src = _plant(sandbox)
    eng = _engine(sandbox, [
        {"content": "",
         "tool_calls": [{"function": {"name": "web_fetch",
                                      "arguments": {
                                          "url": "file://mangled/nope.md"}}}]},
        "I couldn't fetch that resource, so I can't get at the notes.",
        GROUNDED,
    ])
    reply = eng.respond(f"read {src.as_posix()} - what worries you in it?")
    # The failed fetch delivered nothing; the floor read the REAL path and
    # the re-grounded retry replaced the error narration.
    assert "fuse" in reply.content and "5V" in reply.content
    assert any(r["kind"] == "file" for r in eng.referents)


@pytest.mark.case("RAF-007", "GND-010 shape: a SUCCESSFUL read of a DIFFERENT source (the project note) does not close the hole for the file Jack named")
def test_other_read_does_not_block(sandbox):
    src = _plant(sandbox)
    eng = sandbox.service.engine
    # Give the model a real brain note to read (the seeded projects exist).
    eng.model = _ScriptModel([
        {"content": "",
         "tool_calls": [{"function": {"name": "read_brain",
                                      "arguments": {
                                          "path": "projects/alpha_rig.md"}}}]},
        "Filed against the project - the note is up to date.",
        GROUNDED,
    ])
    eng.vote_enabled = False
    reply = eng.respond(
        f"add {src.as_posix()} to the project and give me your analysis of it")
    # The note read delivered content, but NOT the file Jack pointed at:
    # the floor must still run the read and re-ground the reply.
    assert "fuse" in reply.content and "5V" in reply.content
    assert any(r["kind"] == "file" for r in eng.referents)


@pytest.mark.case("RAF-005", "best-effort acceptance: an empty retry keeps the original reply, but the read/referent still landed")
def test_empty_retry_keeps_original(sandbox):
    src = _plant(sandbox)
    draft = "Hmm, let me think about that."
    eng = _engine(sandbox, [draft, ""])
    reply = eng.respond(f"read {src.as_posix()} and summarize it")
    assert reply.content == draft
    # The guaranteed half of the floor held even though the retry was empty.
    assert any(r["kind"] == "file" for r in eng.referents)

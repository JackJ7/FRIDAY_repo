r"""
ADF — the artifact-denial floor (armor residual-floors leg, RF.3).

GND-011's dominant failure mode (16/20 sampled runs): asked for "thoughts on
the notes I just handed you" with the file READ INTO THE SESSION one turn
earlier, the model answers an embodiment-denial script ("I don't have direct
access to physical items / real-time input"). The denial dodges the phantom
barrier (a referent EXISTS) and the anti-dodge net (a denial is not a
clarification question), and it is simply false — the artifact's content sits
on the referent stack. The floor mirrors the date-DENIAL floor: one
re-grounded retry (the excerpt rides in the correction), then a code-built
honest reply handing back the artifact's REAL content.

Pure logic (no live model): a scripted stub drives the real respond() path,
same posture as test_empty_reply_floor.py.
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
          "so I'm unable to review notes you handed me.")

ASK = "what are your thoughts on the notes I just handed you?"


def _seed_read_turn(sandbox, eng_script_tail):
    """Plant a real wiring file, then drive one respond() whose script reads
    it through the REAL read_file tool — so the referent stack carries the
    artifact with its content excerpt, exactly as a live session would."""
    src = sandbox.root / "incoming" / "wrist_wiring_notes.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Gripper wiring\n- 5V rail shared by PCA9685 and camera\n"
                   "- No fuse between pack and buck converter\n"
                   "- Servo grounds star-pointed at the driver\n",
                   encoding="utf-8")
    eng = sandbox.service.engine
    eng.model = _ScriptModel(
        [{"content": "",
          "tool_calls": [{"function": {"name": "read_file",
                                       "arguments": {"path": str(src)}}}]},
         "Read it - the gripper wiring notes are on file."]
        + list(eng_script_tail))
    eng.vote_enabled = False
    eng.respond(f"read {src.as_posix()}")
    return eng


@pytest.mark.case("ADF-001", "denial with the artifact on the stack: one re-grounded retry is accepted when it engages the content")
def test_regrounded_retry_accepted(sandbox):
    eng = _seed_read_turn(sandbox, [
        DENIAL,
        "The 5V rail shared with the PCA9685 worries me - there's no fuse "
        "before the buck converter, so a short takes out the whole rail.",
    ])
    reply = eng.respond(ASK)
    assert "fuse" in reply.content and "5V" in reply.content
    assert "don't have direct access" not in reply.content


@pytest.mark.case("ADF-002", "retry denies again: the code-built honest reply hands back the artifact's REAL content")
def test_code_built_fallback(sandbox):
    eng = _seed_read_turn(sandbox, [DENIAL, DENIAL])
    reply = eng.respond(ASK)
    # Grounded by construction: names the artifact, quotes its actual text.
    assert "wrist_wiring_notes.md" in reply.content
    assert "PCA9685" in reply.content or "fuse" in reply.content
    assert "I do have it" in reply.content


@pytest.mark.case("ADF-003", "no false positive: a reply that engages the artifact's content is never touched, even with an access hedge")
def test_grounded_reply_untouched(sandbox):
    grounded = ("I can't access real-time data, but from the notes: the 5V "
                "rail is shared by the PCA9685 and the camera, and there's "
                "no fuse before the buck converter.")
    eng = _seed_read_turn(sandbox, [grounded])
    before = eng.model.calls
    reply = eng.respond(ASK)
    assert reply.content == grounded
    assert eng.model.calls == before + 1  # no retry spent


@pytest.mark.case("ADF-004", "GND-012 protection: with an EMPTY artifact ledger an honest denial passes through untouched")
def test_empty_ledger_denial_survives(sandbox):
    eng = sandbox.service.engine
    honest = ("I don't have any hydraulics spreadsheet - nothing has been "
              "shared with me this session. Point me at it and I'll read it.")
    eng.model = _ScriptModel([honest])
    eng.vote_enabled = False
    reply = eng.respond("thoughts on the hydraulics spreadsheet I gave you?")
    assert reply.content == honest
    assert eng.model.calls == 1  # no retry: the denial is CORRECT here

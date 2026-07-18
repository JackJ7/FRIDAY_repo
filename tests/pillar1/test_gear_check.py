r"""
GRC — the gear-direction cross-check floor (armor QB.3, GOLD-gear-03).

THE FAILURE. GOLD-gear-03 ("A motor gives 0.65 N*m through a 20:1 gearbox at
80% efficiency. Output torque?", correct answer 10.4 N*m = 0.65*20*0.8) hit a
0/5 recheck band with FOUR different wrong answers — the 14B churns on
direction (xR vs /R) and efficiency placement. A reduction R:1 (with
efficiency eta) fixes output torque = input * R * eta and output speed =
input / R deterministically from Jack's OWN stated numbers, so the floor
checks the produced ANSWER against that computation rather than asking the
model to do the arithmetic twice.

Pure logic (no live model): a scripted stub stands in for the model, the same
posture as test_answer_floor.py/test_date_floor.py. Every GRC case appends a
literal 'ANSWER: <number> <unit>' contract to the message so answer_ask (and
therefore hold_stream, and the ANSWER-contract floor upstream) arm exactly as
a live golden-suite turn would.
"""

import pytest

from core.model import ModelReply


class _ScriptModel:
    """Scripted content-only replies in order (the test_answer_floor.py
    pattern) — no tool calls needed, this floor only inspects user_input and
    the settled reply's ANSWER line."""

    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        r = ModelReply()
        r.content = self.contents.pop(0) if self.contents else ""
        r.eval_count = 5
        return r


def _engine(sandbox, contents, capture=None):
    eng = sandbox.service.engine
    eng.model = _ScriptModel(contents)
    # Isolate the floor under test: A6 voting also arms on ANSWER: turns and
    # would pop extra scripted replies (desynchronizing the script).
    eng.vote_enabled = False
    if capture is not None:
        eng.ilog.log = lambda d: capture.append(d)
    return eng


TORQUE_PROMPT = ("A motor gives 0.65 N*m through a 20:1 gearbox at 80% "
                 "efficiency. Output torque? ANSWER: <number> <unit>")
SPEED_PROMPT = ("A 3000 rpm motor drives a 15:1 reduction. What is the "
                "output shaft speed? ANSWER: <number> <unit>")


@pytest.mark.case("GRC-001", "a ÷R draft (wrong direction) is corrected to "
                             "the deterministic value via one retry")
def test_grc001_divide_direction_corrected(sandbox):
    cap = []
    eng = _engine(sandbox, [
        "Dividing by the ratio and efficiency.\n\nANSWER: 0.026 N*m",
        "Recomputing: 0.65 * 20 * 0.8 = 10.4.\n\nANSWER: 10.4 N*m",
    ], capture=cap)
    reply = eng.respond(TORQUE_PROMPT)
    assert "10.4" in reply.content, reply.content
    assert eng.model.calls == 2
    assert cap[-1]["gear_check_floor"] is True, cap[-1]


@pytest.mark.case("GRC-002", "an efficiency-dropped draft (right direction, "
                             "missing eta) is corrected via one retry")
def test_grc002_efficiency_dropped_corrected(sandbox):
    cap = []
    eng = _engine(sandbox, [
        "Torque scales by the ratio: 0.65 * 20 = 13.\n\nANSWER: 13 N*m",
        "Including efficiency: 0.65 * 20 * 0.8 = 10.4.\n\nANSWER: 10.4 N*m",
    ], capture=cap)
    reply = eng.respond(TORQUE_PROMPT)
    assert "10.4" in reply.content, reply.content
    assert eng.model.calls == 2
    assert cap[-1]["gear_check_floor"] is True, cap[-1]


@pytest.mark.case("GRC-003", "a correct draft is left untouched — no retry "
                             "spent, flag stays False")
def test_grc003_correct_draft_untouched(sandbox):
    cap = []
    draft = "Working it through: 0.65 * 20 * 0.8 = 10.4.\n\nANSWER: 10.4 N*m"
    eng = _engine(sandbox, [draft], capture=cap)
    reply = eng.respond(TORQUE_PROMPT)
    assert reply.content == draft, reply.content
    assert eng.model.calls == 1
    assert cap[-1]["gear_check_floor"] is False, cap[-1]


@pytest.mark.case("GRC-004", "step-up vocabulary present -> the floor never "
                             "fires, even on a wrong draft")
def test_grc004_stepup_vocab_never_fires(sandbox):
    cap = []
    prompt = ("A motor gives 0.65 N*m through a 20:1 step-up gearbox at 80% "
              "efficiency. Output torque? ANSWER: <number> <unit>")
    draft = "Dividing by the ratio.\n\nANSWER: 0.026 N*m"
    eng = _engine(sandbox, [draft], capture=cap)
    reply = eng.respond(prompt)
    assert reply.content == draft, reply.content
    assert eng.model.calls == 1
    assert cap[-1]["gear_check_floor"] is False, cap[-1]


@pytest.mark.case("GRC-005", "two ratios in the message -> ambiguous, the "
                             "floor never fires")
def test_grc005_two_ratios_never_fires(sandbox):
    cap = []
    prompt = ("A motor gives 0.65 N*m through a 20:1 gearbox then a 3:1 "
              "gearbox at 80% efficiency. Output torque? "
              "ANSWER: <number> <unit>")
    draft = "Chaining the ratios.\n\nANSWER: 31.2 N*m"
    eng = _engine(sandbox, [draft], capture=cap)
    reply = eng.respond(prompt)
    assert reply.content == draft, reply.content
    assert eng.model.calls == 1
    assert cap[-1]["gear_check_floor"] is False, cap[-1]


@pytest.mark.case("GRC-006", "the speed path (input/R) corrects a wrong "
                             "multiply-direction draft")
def test_grc006_speed_path_corrected(sandbox):
    cap = []
    eng = _engine(sandbox, [
        "Multiplying by the ratio: 3000 * 15 = 45000.\n\nANSWER: 45000 rpm",
        "Dividing instead: 3000 / 15 = 200.\n\nANSWER: 200 rpm",
    ], capture=cap)
    reply = eng.respond(SPEED_PROMPT)
    assert "200" in reply.content, reply.content
    assert eng.model.calls == 2
    assert cap[-1]["gear_check_floor"] is True, cap[-1]


@pytest.mark.case("GRC-007", "an accepted retry replaces the WHOLE reply "
                             "(no separate line-replacement logic touches "
                             "an already-correct retry)")
def test_grc007_accepted_retry_no_line_replacement(sandbox):
    retry_text = "Recomputing: 0.65 * 20 * 0.8 = 10.4.\n\nANSWER: 10.4 N*m"
    eng = _engine(sandbox, [
        "Dividing by the ratio and efficiency.\n\nANSWER: 0.026 N*m",
        retry_text,
    ])
    reply = eng.respond(TORQUE_PROMPT)
    assert reply.content == retry_text, reply.content


@pytest.mark.case("GRC-008", "a retry that is STILL wrong -> the deterministic "
                             "fallback replaces ONLY the ANSWER line, the "
                             "draft's prose is preserved, and the reply is "
                             "never emptied")
def test_grc008_fallback_replaces_only_answer_line(sandbox):
    cap = []
    prose = "Here's my reasoning: torque scales with the ratio."
    eng = _engine(sandbox, [
        prose + "\n\nANSWER: 0.026 N*m",
        "Still dividing by mistake.\n\nANSWER: 0.033 N*m",
    ], capture=cap)
    reply = eng.respond(TORQUE_PROMPT)
    assert reply.content.strip(), "reply must never be emptied"
    assert reply.content.startswith(prose), reply.content
    assert reply.content.endswith("ANSWER: 10.4 N*m"), reply.content
    assert eng.model.calls == 2
    assert cap[-1]["gear_check_floor"] is True, cap[-1]

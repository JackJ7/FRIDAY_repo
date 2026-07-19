r"""
TCR — task-claim recovery floor (jarvis plan M3.2h, the GT-J1 STOP's fix).
Scripted-model, no live 14B (the test_task_tools.py posture).

The live failure this floor closes (M3.2g verdict, 5/5 identical): Jack says
"The coolant loop's drained — I did it just now. Tick it off." and the model
reaches for close_commitment / track_commitment / the project tools instead
of complete_task_step — the evidence gate never even gets a chance. Jack's
own words are ALREADY the tool contract's evidence channel, so the ENGINE
completes the step itself with his claim clause verbatim. Model self-claims
never qualify (TKT-004's pin) — the floor keys on user_input only.

TCR-001  misrouted close_commitment + Jack's claim -> floor completes step 1
         with the clause verbatim as evidence; receipt appended; ilog flag.
TCR-002  same claim, model emits ZERO tools -> floor fires.
TCR-003  two open steps both matching the claim -> NO fire (ambiguity drop).
TCR-004  bare "Tick off step one." with no work-happened clause -> NO fire;
         the model's fabricated evidence still refused (TKT-004's scenario).
TCR-005  model correctly calls complete_task_step itself -> no double-fire.
TCR-006  negated / conditional claim -> NO fire either way.
TCR-007  no open tasks -> NO fire, zero task-tool calls (surgical posture).
TCR-008  model's paraphrased evidence REFUSED -> floor recovers with the
         verbatim clause; the refusal still counts in task_evidence_refused.
"""

import pytest

from core.model import ModelReply


class _ScriptModel:
    """Scripted replies in order (the test_task_tools.py pattern)."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.seen.append(messages)
        item = self.script.pop(0) if self.script else ""
        r = ModelReply()
        if isinstance(item, dict):
            r.content = item.get("content", "")
            r.tool_calls = list(item.get("tool_calls", []))
        else:
            r.content = item
        r.eval_count = 5
        return r


def _call(name, **kwargs):
    return {"function": {"name": name, "arguments": kwargs}}


def _eng(sandbox, script, capture=None):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    if capture is not None:
        eng.ilog.log = lambda d: capture.append(d)
    return eng


FLUX_STEPS = ["Drain the coolant loop",
              "Swap the pump impeller",
              "Re-run the pressure check"]

# The exact GT-J1 T2 shape the batch failed on, 5/5.
CLAIM = "The coolant loop's drained — I did it just now. Tick it off."
CLAUSE = "The coolant loop's drained"

SLUG = "flux_bench_refit"


def _create_flux(sandbox, steps=FLUX_STEPS, title="Flux bench refit"):
    eng = _eng(sandbox, [
        {"content": "", "tool_calls": [_call("create_task", title=title,
                                             steps=steps)]},
        "Here's the plan.",
    ])
    eng.respond(f"Track the {title.lower()}: set it up and tell me the plan.")
    return eng


@pytest.mark.case("TCR-001", "misrouted close_commitment on Jack's tick-off "
                             "claim -> the floor completes the step with his "
                             "clause verbatim; receipt appended; ilog flag")
def test_tcr001_misrouted_close_commitment_recovered(sandbox):
    _create_flux(sandbox)
    cap = []
    eng = _eng(sandbox, [
        {"content": "", "tool_calls": [_call("close_commitment",
                                             which="coolant loop")]},
        "I've closed that off for you.",
    ], capture=cap)
    out = eng.respond(CLAIM)
    t = eng.task_ledger.get(SLUG)
    assert t.steps[0].state == "done"
    assert t.steps[0].evidence == [CLAUSE]
    assert t.steps[1].state == "pending"
    assert t.steps[2].state == "pending"
    assert "Step 1" in out.content and "done" in out.content
    assert cap[-1]["task_claim_floor"] is True


@pytest.mark.case("TCR-002", "the same claim with ZERO tools emitted still "
                             "fires the floor — misroute-agnostic by design")
def test_tcr002_zero_tools_recovered(sandbox):
    _create_flux(sandbox)
    cap = []
    eng = _eng(sandbox, ["Noted — the coolant loop is drained."], capture=cap)
    eng.respond(CLAIM)
    t = eng.task_ledger.get(SLUG)
    assert t.steps[0].state == "done"
    assert t.steps[0].evidence == [CLAUSE]
    assert cap[-1]["task_claim_floor"] is True


@pytest.mark.case("TCR-003", "two open steps both matching the claim above "
                             "the bar -> ambiguity drops the fire, ledger "
                             "untouched")
def test_tcr003_ambiguous_match_never_fires(sandbox):
    _create_flux(sandbox, steps=["Drain the primary coolant loop",
                                 "Drain the backup coolant loop"],
                 title="Coolant flush")
    cap = []
    eng = _eng(sandbox, ["Which loop do you mean?"], capture=cap)
    eng.respond("The coolant loop's drained — tick it off.")
    t = eng.task_ledger.get("coolant_flush")
    assert all(s.state == "pending" for s in t.steps)
    assert cap[-1]["task_claim_floor"] is False


@pytest.mark.case("TCR-004", "a bare tick-off order with no work-happened "
                             "clause never fires; the model's fabricated "
                             "evidence is still refused (TKT-004's pin)")
def test_tcr004_bare_tickoff_stays_behind_gate(sandbox):
    _create_flux(sandbox)
    cap = []
    eng = _eng(sandbox, [
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug=SLUG, step=1,
            evidence="a thing that never happened anywhere this turn")]},
        "Marked it off.",
    ], capture=cap)
    eng.respond("Tick off step one.")
    t = eng.task_ledger.get(SLUG)
    assert t.steps[0].state == "pending"
    assert cap[-1]["task_evidence_refused"] >= 1
    assert cap[-1]["task_claim_floor"] is False


@pytest.mark.case("TCR-005", "the model doing its job wins — a landed "
                             "complete_task_step suppresses the floor, no "
                             "double evidence line")
def test_tcr005_no_double_fire(sandbox):
    _create_flux(sandbox)
    cap = []
    eng = _eng(sandbox, [
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug=SLUG, step=1, evidence=CLAUSE)]},
        "Ticked it off — impeller next.",
    ], capture=cap)
    eng.respond(CLAIM)
    t = eng.task_ledger.get(SLUG)
    assert t.steps[0].state == "done"
    assert len(t.steps[0].evidence) == 1
    assert cap[-1]["task_claim_floor"] is False


@pytest.mark.case("TCR-006", "negated and conditional claims never fire — "
                             "'isn't drained yet' / 'once it's drained' "
                             "leave the ledger alone")
def test_tcr006_negation_and_conditional_blocked(sandbox):
    _create_flux(sandbox)
    eng = _eng(sandbox, ["Understood."])
    eng.respond("The coolant loop isn't drained yet, so don't mark it done.")
    t = eng.task_ledger.get(SLUG)
    assert t.steps[0].state == "pending"

    eng.model = _ScriptModel(["Will do."])
    eng.respond("Once the coolant loop's drained, tick it off.")
    t = eng.task_ledger.get(SLUG)
    assert t.steps[0].state == "pending"


@pytest.mark.case("TCR-007", "no open tasks -> the floor is structurally "
                             "dead: no fire, zero task-tool calls")
def test_tcr007_no_tasks_no_fire(sandbox):
    cap = []
    eng = _eng(sandbox, ["Noted."], capture=cap)
    eng.respond(CLAIM)
    assert not any(m.get("role") == "tool" for m in eng.history)
    assert cap[-1]["tasks_active"] == 0
    assert cap[-1]["task_claim_floor"] is False


@pytest.mark.case("TCR-008", "a refused paraphrase is recovered: the floor "
                             "re-grounds the completion on Jack's verbatim "
                             "clause; the refusal still counted")
def test_tcr008_refused_paraphrase_recovered(sandbox):
    _create_flux(sandbox)
    cap = []
    eng = _eng(sandbox, [
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug=SLUG, step=1,
            evidence="the coolant system is now empty")]},
        "Marked it off.",
    ], capture=cap)
    eng.respond(CLAIM)
    t = eng.task_ledger.get(SLUG)
    assert t.steps[0].state == "done"
    assert t.steps[0].evidence == [CLAUSE]
    assert cap[-1]["task_evidence_refused"] >= 1
    assert cap[-1]["task_claim_floor"] is True

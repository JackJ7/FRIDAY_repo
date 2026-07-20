r"""
TKA — task-tool arming gate (jarvis plan M3.2i).

The five durable-task schemas are a family: an explicit tracking request or
an already-open task arms all of them; ordinary planning conversation exposes
none of them.  The in-tool create guard is the second hard layer for turns
where an open task arms the family but Jack did not ask to create another one.
"""

import pytest

from core.model import ModelReply


TASK_TOOLS = {
    "create_task",
    "task_status",
    "complete_task_step",
    "block_task",
    "unblock_task",
}

SKL_004_MESSAGE = (
    "I need to figure out how to approach sizing the whole drivetrain "
    "for the delta sled - motor, gearing, belt - it's an unfamiliar "
    "design problem for me. Help me plan the attack."
)

GT_J1_T1 = (
    "Track the flux bench refit: drain the coolant loop, swap "
    "the pump impeller, re-run the pressure check — set it up "
    "and tell me the plan."
)

FLUX_STEPS = [
    "Drain the coolant loop",
    "Swap the pump impeller",
    "Re-run the pressure check",
]


class _ScriptModel:
    def __init__(self, script):
        self.script = list(script)
        self.tools_seen = []

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.tools_seen.append(list(tools or []))
        item = self.script.pop(0) if self.script else ""
        reply = ModelReply()
        if isinstance(item, dict):
            reply.content = item.get("content", "")
            reply.tool_calls = list(item.get("tool_calls", []))
        else:
            reply.content = item
        reply.eval_count = 5
        return reply


def _tool_names(payload):
    return {item["function"]["name"] for item in payload}


def _call(name, **arguments):
    return {"function": {"name": name, "arguments": arguments}}


def _engine(sandbox, script, capture=None):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    if capture is not None:
        eng.ilog.log = lambda record: capture.append(record)
    return eng


@pytest.mark.case("TKA-001", "SKL-004 planning specimen exposes no task "
                             "schemas and leaves the task ledger untouched")
def test_tka001_planning_turn_disarms_task_family(sandbox):
    capture = []
    eng = _engine(sandbox, [
        "Start with load and speed requirements, then size the motor, "
        "choose the reduction, and verify the belt loads."
    ], capture=capture)

    eng.respond(SKL_004_MESSAGE)

    assert eng.model.tools_seen, "the test did not observe a model payload"
    assert TASK_TOOLS.isdisjoint(_tool_names(eng.model.tools_seen[0]))
    assert not any(message.get("role") == "tool" for message in eng.history)
    assert capture[-1]["task_tools_armed"] is False
    assert capture[-1]["tasks_active"] == 0


@pytest.mark.case("TKA-002", "explicit task/checklist request arms the family "
                             "and create_task succeeds")
def test_tka002_explicit_tracking_request_arms_and_creates(sandbox):
    capture = []
    eng = _engine(sandbox, [
        {"content": "", "tool_calls": [_call(
            "create_task", title="Calibrate the test stand",
            steps=["Zero the sensor", "Apply the reference load"])]},
        "Tracked — here's the checklist.",
    ], capture=capture)

    eng.respond("Track this as a task: calibrate the test stand. "
                "Checklist: zero the sensor, then apply the reference load.")

    assert TASK_TOOLS <= _tool_names(eng.model.tools_seen[0])
    assert eng.task_ledger.get("calibrate_the_test_stand") is not None
    receipt = next(m["content"] for m in eng.history
                   if m.get("role") == "tool")
    assert "Created task 'calibrate_the_test_stand'" in receipt
    assert capture[-1]["task_tools_armed"] is True


@pytest.mark.case("TKA-003", "an open task arms the family, but create_task "
                             "without a fresh tracking cue is refused")
def test_tka003_open_task_does_not_license_unrelated_creation(sandbox):
    capture = []
    eng = _engine(sandbox, [
        {"content": "", "tool_calls": [_call(
            "create_task", title="Unrelated second job",
            steps=["Invent one", "Invent two"])]},
        "The original job is still in progress.",
    ], capture=capture)
    eng.task_ledger.create("Calibrate the test stand",
                           ["Zero the sensor", "Apply the reference load"])

    eng.respond("How's it looking?")

    assert TASK_TOOLS <= _tool_names(eng.model.tools_seen[0])
    receipts = [m["content"] for m in eng.history if m.get("role") == "tool"]
    assert any("didn't ask to track a task this turn" in r for r in receipts)
    assert eng.task_ledger.get("calibrate_the_test_stand") is not None
    assert eng.task_ledger.get("unrelated_second_job") is None
    assert len(eng.task_ledger.list_open()) == 1
    assert capture[-1]["task_tools_armed"] is True


@pytest.mark.case("TKA-004", "an empty neutral turn exposes no task tools; "
                             "the no-task claim floor remains zero-fire")
def test_tka004_neutral_empty_ledger_and_no_task_floor_fire(sandbox):
    capture = []
    eng = _engine(sandbox, ["Everything's quiet.", "Noted."], capture=capture)

    eng.respond("Anything unusual today?")
    assert TASK_TOOLS.isdisjoint(_tool_names(eng.model.tools_seen[0]))
    assert capture[-1]["task_tools_armed"] is False

    eng.respond("The coolant loop's drained — I did it just now. Tick it off.")
    assert not any(message.get("role") == "tool" for message in eng.history)
    assert capture[-1]["tasks_active"] == 0
    assert capture[-1]["task_claim_floor"] is False


@pytest.mark.case("TKA-005", "GT-J1 T1's verbatim creation wording arms the "
                             "task-tool family")
def test_tka005_gt_j1_creation_wording_is_calibrated(sandbox):
    capture = []
    eng = _engine(sandbox, ["I'll set out the three steps."], capture=capture)

    eng.respond(GT_J1_T1)

    assert TASK_TOOLS <= _tool_names(eng.model.tools_seen[0])
    assert capture[-1]["task_tools_armed"] is True


@pytest.mark.case("TKA-006", "open-state arming composes with the task-claim "
                             "floor's engine-initiated completion")
def test_tka006_open_task_keeps_claim_floor_working(sandbox):
    capture = []
    eng = _engine(sandbox, ["Noted — the coolant loop is drained."],
                  capture=capture)
    eng.task_ledger.create("Flux bench refit", FLUX_STEPS)

    eng.respond("The coolant loop's drained — I did it just now. Tick it off.")

    task = eng.task_ledger.get("flux_bench_refit")
    assert task.steps[0].state == "done"
    assert task.steps[0].evidence == ["The coolant loop's drained"]
    assert task.steps[1].state == "pending"
    assert capture[-1]["task_claim_floor"] is True
    assert capture[-1]["task_tools_armed"] is True

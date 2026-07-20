r"""
TCF — explicit task-create landed floor (jarvis plan M3.2k).

The M3.2j live miss this suite closes had the task schemas correctly armed,
but the model emitted no tool call.  The last, tool-free output-script retry
then produced the right three-step plan and asked for confirmation while the
durable TaskLedger stayed empty.  These tests pin the code-enforced invariant:
an explicit empty-ledger creation turn either lands the already-grounded plan
through create_task or says exactly what information is missing.
"""

import pytest

from core.model import ModelReply


GT_J1_T1 = (
    "Track the flux bench refit: drain the coolant loop, swap "
    "the pump impeller, re-run the pressure check — set it up "
    "and tell me the plan."
)

GT_A_T5 = (
    "Cross reference my calendar and tasks — remove any task you don't "
    "see on the calendar, but don't add any tasks."
)

SKL_004_MESSAGE = (
    "I need to figure out how to approach sizing the whole drivetrain "
    "for the delta sled - motor, gearing, belt - it's an unfamiliar "
    "design problem for me. Help me plan the attack."
)

TASK_TOOLS = {
    "create_task",
    "task_status",
    "complete_task_step",
    "block_task",
    "unblock_task",
}

FLUX_STEPS = [
    "drain the coolant loop",
    "swap the pump impeller",
    "re-run the pressure check",
]

NUMBERED_PLAN = (
    "Here's the plan:\n"
    "1. Drain the coolant loop\n"
    "2. Swap the pump impeller\n"
    "3. Re-run the pressure check\n\n"
    "Confirm this plan?"
)

CREATION_GAP = (
    "I haven't created a task: I need a clear title and 2-10 concrete steps. "
    "What title and steps should I use?"
)

FOREIGN_SCRIPT_REPLY = (
    "ขอโทษด้วยครับ ตอนนี้ฉันไม่สามารถช่วยคุณได้ "
    "กรุณาลองใหม่อีกครั้งในภายหลัง"
)


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


def _call(name, **arguments):
    return {"function": {"name": name, "arguments": arguments}}


def _tool_names(payload):
    return {item["function"]["name"] for item in payload}


def _engine(sandbox, script, capture):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    eng.ilog.log = lambda record: capture.append(record)
    return eng


def _assert_landed_flux_task(eng, capture):
    task = eng.task_ledger.get("flux_bench_refit")
    assert task is not None
    assert [step.text for step in task.steps] == FLUX_STEPS
    assert [step.state for step in task.steps] == ["pending"] * 3
    receipts = [
        message["content"]
        for message in eng.history
        if message.get("role") == "tool"
    ]
    assert len(receipts) == 1
    assert "Created task 'flux_bench_refit' with 3 steps" in receipts[0]
    assert capture[-1]["task_creation_floor"] is True
    assert capture[-1]["task_tools_armed"] is True
    assert capture[-1]["tasks_active"] == 1


@pytest.mark.case("TCF-001", "GT-J1 explicit create request with a zero-tool "
                             "numbered plan lands one durable task")
def test_tcf001_gt_j1_zero_tool_plan_lands_task(sandbox):
    """TCF-001: the exact zero-tool GT-J1 plan becomes one durable task."""
    capture = []
    eng = _engine(sandbox, [NUMBERED_PLAN], capture)

    eng.respond(GT_J1_T1)

    _assert_landed_flux_task(eng, capture)


@pytest.mark.case("TCF-002", "output-script correction settles before the "
                             "landed-create floor executes the same plan")
def test_tcf002_script_retry_plan_lands_after_script_floor(sandbox):
    """TCF-002: script correction settles before landed-create recovery."""
    capture = []
    eng = _engine(sandbox, [FOREIGN_SCRIPT_REPLY, NUMBERED_PLAN], capture)

    eng.respond(GT_J1_T1)

    _assert_landed_flux_task(eng, capture)
    assert capture[-1]["script_drift_corrective"] is True


@pytest.mark.case("TCF-003", "a native create_task receipt wins and the "
                             "landed-create floor never double-creates")
def test_tcf003_native_create_suppresses_floor(sandbox):
    capture = []
    eng = _engine(sandbox, [
        {"content": "", "tool_calls": [_call(
            "create_task", title="flux bench refit", steps=FLUX_STEPS)]},
        "Created — here's the three-step plan.",
    ], capture)

    eng.respond(GT_J1_T1)

    tasks = eng.task_ledger.list_open()
    assert [task.slug for task in tasks] == ["flux_bench_refit"]
    receipts = [
        message["content"]
        for message in eng.history
        if message.get("role") == "tool"
    ]
    assert len(receipts) == 1
    assert capture[-1]["task_creation_floor"] is False


@pytest.mark.case("TCF-004", "bare discussion, unrelated planning, and "
                             "negated creation never engage the floor")
@pytest.mark.parametrize("user_input", [
    GT_A_T5,
    SKL_004_MESSAGE,
    "What tasks are on the calendar?",
    "Do not create any tasks for this review.",
])
def test_tcf004_non_creation_turns_stay_disarmed(sandbox, user_input):
    capture = []
    eng = _engine(sandbox, ["Understood."], capture)

    eng.respond(user_input)

    assert TASK_TOOLS.isdisjoint(_tool_names(eng.model.tools_seen[0]))
    assert not any(message.get("role") == "tool" for message in eng.history)
    assert eng.task_ledger.list_open() == []
    assert capture[-1]["task_creation_floor"] is False
    assert capture[-1]["task_tools_armed"] is False


@pytest.mark.case("TCF-005", "an existing open task never licenses a second "
                             "task through the empty-ledger creation floor")
def test_tcf005_open_task_never_engages_creation_floor(sandbox):
    capture = []
    eng = _engine(sandbox, ["The existing job is still in progress."], capture)
    eng.task_ledger.create(
        "Existing calibration job",
        ["Zero the gauge", "Apply the reference load"],
    )

    eng.respond("How is the existing job looking?")

    assert [task.slug for task in eng.task_ledger.list_open()] == [
        "existing_calibration_job"
    ]
    assert not any(message.get("role") == "tool" for message in eng.history)
    assert capture[-1]["task_creation_floor"] is False
    assert capture[-1]["task_tools_armed"] is True


@pytest.mark.case("TCF-006", "under-specified positive creation asks mutate "
                             "nothing and receive the exact code-built gap")
def test_tcf006_under_specified_creation_reports_exact_gap(sandbox):
    capture = []
    eng = _engine(sandbox, ["I'll need the details."], capture)

    reply = eng.respond("Create a task.")

    assert eng.task_ledger.list_open() == []
    assert not any(message.get("role") == "tool" for message in eng.history)
    assert reply.content.splitlines()[-1] == CREATION_GAP
    assert capture[-1]["task_creation_floor"] is True
    assert capture[-1]["tasks_active"] == 0


@pytest.mark.case("TCF-007", "test-session landed creation writes only the "
                             "archive while remaining logically listable")
def test_tcf007_test_session_creation_uses_archive_overlay(sandbox):
    sandbox.brain.test_session = True
    capture = []
    eng = _engine(sandbox, [NUMBERED_PLAN], capture)

    eng.respond(GT_J1_T1)

    archived = (sandbox.brain.root / "test_archive" / "tasks" /
                "flux_bench_refit.md")
    real = sandbox.brain.root / "tasks" / "flux_bench_refit.md"
    assert archived.is_file()
    assert not real.exists()
    assert [task.slug for task in eng.task_ledger.list_open()] == [
        "flux_bench_refit"
    ]
    assert capture[-1]["task_creation_floor"] is True
    assert capture[-1]["tasks_active"] == 1

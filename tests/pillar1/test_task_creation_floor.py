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

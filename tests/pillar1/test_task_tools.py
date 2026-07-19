r"""
TKT — model-facing task tools (jarvis plan J1.2, roadmap M3.2). Scripted-model,
no live 14B (the test_narrated_json.py / test_gear_check.py posture): CODE owns
the checklist state machine, the model only calls the five tools registered in
core/tools/task_tools.py against a real TaskLedger over the sandbox brain.

TKT-001  create_task -> file exists, receipt carries slug + steps.
TKT-002  duplicate OPEN slug -> "ERROR: ..." string, no crash.
TKT-003  complete_task_step with evidence quoting a tool result THIS turn ->
         step done, evidence line lands in the file.
TKT-004  fabricated evidence (matches nothing) -> refused, step still
         pending, task_evidence_refused >= 1 in the ilog.
TKT-005  evidence quoting Jack's own message this turn -> accepted.
TKT-006  block_task -> status blocked + blocked_on recorded; unblock_task ->
         back to in-progress.
TKT-007  an open task's DURABLE TASKS block rides the system prompt; once
         the task closes, the next turn's prompt has none.
TKT-008  no ledger wired (task_ledger = None) -> no injection, no crash —
         the project_resolver bare-sandbox posture.
TKT-009  tasks_active in the ilog: 0 with none open, N with N open.
TKT-010  identifier-floor coexistence: an OPEN task's own slug near merge
         vocabulary does not trip _foreign_identifiers (real ledger surface,
         same philosophy as a real project surface).
"""

import pytest

from core.model import ModelReply


class _ScriptModel:
    """Scripted replies in order (the test_narrated_json.py pattern)."""

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


STEPS = ["List everything in the inbox",
         "File each note into its project",
         "Report what moved where"]


def _create(sandbox, title="Sort the workshop inbox", steps=STEPS,
            reply_after="Here's the plan.", capture=None):
    """Drive one turn that creates a task via the tool, then a final reply."""
    eng = _eng(sandbox, [
        {"content": "", "tool_calls": [_call("create_task", title=title, steps=steps)]},
        reply_after,
    ], capture=capture)
    eng.respond(f"Track this job: {title}.")
    return eng


@pytest.mark.case("TKT-001", "create_task writes the ledger file; the tool "
                             "receipt names the slug and every step")
def test_tkt001_create_writes_file(sandbox):
    eng = _create(sandbox)
    raw = sandbox.brain.read_note("tasks/sort_the_workshop_inbox.md")
    assert "title: Sort the workshop inbox" in raw
    receipt = next(m["content"] for m in eng.history if m.get("role") == "tool")
    assert "sort_the_workshop_inbox" in receipt
    for s in STEPS:
        assert s in receipt


@pytest.mark.case("TKT-002", "a duplicate OPEN slug returns an ERROR string, "
                             "never a crash")
def test_tkt002_duplicate_open_slug_errors(sandbox):
    eng = _create(sandbox)
    eng.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "create_task", title="Sort the workshop inbox", steps=STEPS)]},
        "Noted.",
    ])
    eng.respond("Track this job again: Sort the workshop inbox.")
    receipt = [m["content"] for m in eng.history if m.get("role") == "tool"][-1]
    assert "ERROR:" in receipt
    assert "sort_the_workshop_inbox" in receipt


@pytest.mark.case("TKT-003", "evidence quoting a tool result run THIS turn "
                             "is grounded -> step advances, evidence lands "
                             "in the file")
def test_tkt003_tool_grounded_evidence_advances(sandbox):
    eng = _create(sandbox)
    eng.model = _ScriptModel([
        {"content": "", "tool_calls": [
            _call("task_status", slug="sort_the_workshop_inbox")]},
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="sort_the_workshop_inbox", step=1,
            evidence="List everything in the inbox")]},
        "Done with step one.",
    ])
    eng.respond("I just did step one, tick it off.")
    t = sandbox.service.engine.task_ledger.get("sort_the_workshop_inbox")
    assert t.steps[0].state == "done"
    raw = sandbox.brain.read_note("tasks/sort_the_workshop_inbox.md")
    assert "evidence: List everything in the inbox" in raw


@pytest.mark.case("TKT-004", "fabricated evidence matching nothing this "
                             "turn is refused; step stays pending; "
                             "task_evidence_refused counts it")
def test_tkt004_fabricated_evidence_refused(sandbox):
    eng = _create(sandbox)
    cap = []
    eng.ilog.log = lambda d: cap.append(d)
    eng.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="sort_the_workshop_inbox", step=1,
            evidence="a thing that never happened anywhere this turn")]},
        "Marked it off.",
    ])
    eng.respond("Tick off step one.")
    t = sandbox.service.engine.task_ledger.get("sort_the_workshop_inbox")
    assert t.steps[0].state == "pending"
    receipt = [m["content"] for m in eng.history if m.get("role") == "tool"][-1]
    assert "ERROR:" in receipt
    assert cap[-1]["task_evidence_refused"] >= 1


@pytest.mark.case("TKT-005", "evidence quoting Jack's own message this turn "
                             "is grounded -> accepted with no tool call")
def test_tkt005_jack_words_ground_evidence(sandbox):
    eng = _create(sandbox)
    eng.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="sort_the_workshop_inbox", step=1,
            evidence="I already listed everything in the inbox myself")]},
        "Noted, moving to step two.",
    ])
    eng.respond("I already listed everything in the inbox myself, just now.")
    t = sandbox.service.engine.task_ledger.get("sort_the_workshop_inbox")
    assert t.steps[0].state == "done"


@pytest.mark.case("TKT-006", "block_task parks with the reason recorded; "
                             "unblock_task returns it to in-progress")
def test_tkt006_block_and_unblock(sandbox):
    eng = _create(sandbox)
    eng.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "block_task", slug="sort_the_workshop_inbox", step=1,
            reason="needs Jack's confirm: which project owns the loose notes")]},
        "Parked it for you.",
    ])
    eng.respond("Hold off on step one until I tell you which project.")
    t = sandbox.service.engine.task_ledger.get("sort_the_workshop_inbox")
    assert t.status == "blocked"
    assert "which project owns the loose notes" in t.blocked_on

    eng.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "unblock_task", slug="sort_the_workshop_inbox", step=1)]},
        "Back on it.",
    ])
    eng.respond("Okay, the inbox notes all belong to alpha_rig — go ahead.")
    t = sandbox.service.engine.task_ledger.get("sort_the_workshop_inbox")
    assert t.status == "in-progress"
    assert t.blocked_on == ""


@pytest.mark.case("TKT-007", "an open task's DURABLE TASKS block rides the "
                             "system prompt on the NEXT turn; once it's "
                             "closed, the turn after THAT carries none")
def test_tkt007_injection_present_then_absent(sandbox):
    eng = _create(sandbox)   # the creating turn itself predates the task
    eng.model = _ScriptModel(["Sure, checking in."])
    eng.respond("How's the job looking so far?")
    sys_prompt = eng.model.seen[-1][0]["content"]
    assert "DURABLE TASKS" in sys_prompt
    assert "sort_the_workshop_inbox" in sys_prompt

    led = sandbox.service.engine.task_ledger
    for i in range(len(STEPS)):
        led.complete_step("sort_the_workshop_inbox", i, f"finished step {i + 1}; verified")
    eng.model = _ScriptModel(["All done already."])
    eng.respond("How's everything looking?")
    sys_prompt2 = eng.model.seen[-1][0]["content"]
    assert "DURABLE TASKS" not in sys_prompt2


@pytest.mark.case("TKT-008", "no ledger wired -> no injection, no crash "
                             "(the project_resolver bare-sandbox posture)")
def test_tkt008_bare_sandbox_no_ledger(sandbox):
    eng = sandbox.service.engine
    eng.task_ledger = None
    eng.vote_enabled = False
    eng.model = _ScriptModel(["All good."])
    out = eng.respond("What's on my plate today?")
    assert out.content == "All good."
    sys_prompt = eng.model.seen[-1][0]["content"]
    assert "DURABLE TASKS" not in sys_prompt


@pytest.mark.case("TKT-009", "tasks_active in the ilog: 0 with none open, "
                             "N with N open")
def test_tkt009_tasks_active_count(sandbox):
    cap = []
    eng = _eng(sandbox, ["Sure thing."], capture=cap)
    eng.respond("Just checking in.")
    assert cap[-1]["tasks_active"] == 0

    _create(sandbox, title="Sort the workshop inbox")
    cap2 = []
    eng2 = sandbox.service.engine
    eng2.ilog.log = lambda d: cap2.append(d)
    eng2.model = _ScriptModel(["Sure thing."])
    eng2.respond("Just checking in again.")
    assert cap2[-1]["tasks_active"] == 1


@pytest.mark.case("TKT-010", "an OPEN task's own slug near merge vocabulary "
                             "does not trip the foreign-identifier floor — "
                             "real ledger surfaces coexist with project ones")
def test_tkt010_identifier_floor_coexistence(sandbox):
    eng = sandbox.service.engine
    eng.task_ledger.create("Sort the workshop inbox", STEPS)
    text = ("I suggest merging 'sort_the_workshop_inbox' into 'fluxbeam' "
            "and keeping the rest.")
    assert "sort_the_workshop_inbox" not in eng._foreign_identifiers(text)

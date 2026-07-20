r"""TSK — the J1.1 durable task ledger (FRIDAY_jarvis_plan.md §3 J1.1, §6).

Multi-step jobs live as files in brain\tasks\, mutated ONLY through
TaskLedger — code owns the state machine, evidence is required to advance a
step, and everything survives a restart by construction (files re-parsed on
read). Non-model tests: the ledger must hold before the engine, tools, or
job runner ride on it.
"""

import pytest

from core.permissions import PermissionDenied
from core.tasks import TaskLedger


STEPS = ["List everything in the inbox",
         "File each note into its project",
         "Report what moved where"]


def _ledger(sandbox):
    return TaskLedger(sandbox.brain)


@pytest.mark.case("TSK-001", "create writes brain/tasks/<slug>.md; fresh task is all-pending")
def test_create_shape(sandbox):
    led = _ledger(sandbox)
    t = led.create("Sort the workshop inbox", STEPS)
    assert t.slug == "sort_the_workshop_inbox"
    assert t.status == "pending"
    assert [s.state for s in t.steps] == ["pending"] * 3
    raw = sandbox.brain.read_note("tasks/sort_the_workshop_inbox.md")
    assert "title: Sort the workshop inbox" in raw
    assert "- [ ] 1. List everything in the inbox" in raw


@pytest.mark.case("TSK-002", "the ledger round-trips: a rebuilt ledger reads identical state")
def test_restart_round_trip(sandbox):
    led = _ledger(sandbox)
    led.create("Sort the workshop inbox", STEPS)
    led.start_step("sort_the_workshop_inbox", 0)
    led.complete_step("sort_the_workshop_inbox", 0,
                      "list_dir returned 3 files: a.md, b.md, c.md")
    fresh = _ledger(sandbox)  # a new process over the same brain
    t = fresh.get("sort_the_workshop_inbox")
    assert t.status == "in-progress"
    assert t.steps[0].state == "done"
    assert t.steps[0].evidence == ["list_dir returned 3 files: a.md, b.md, c.md"]
    assert t.steps[1].state == "pending"


@pytest.mark.case("TSK-003", "complete_step refuses empty evidence — say-so never advances a step")
def test_evidence_required(sandbox):
    led = _ledger(sandbox)
    led.create("Sort the workshop inbox", STEPS)
    with pytest.raises(ValueError):
        led.complete_step("sort_the_workshop_inbox", 0, "")
    with pytest.raises(ValueError):
        led.complete_step("sort_the_workshop_inbox", 0, "   ")
    assert led.get("sort_the_workshop_inbox").steps[0].state == "pending"


@pytest.mark.case("TSK-004", "status derives from steps: all done => done; any blocked => blocked")
def test_status_derivation(sandbox):
    led = _ledger(sandbox)
    led.create("Two step job", ["step one", "step two"])
    slug = "two_step_job"
    led.complete_step(slug, 0, "did the thing; output verified")
    assert led.get(slug).status == "in-progress"
    led.block(slug, 1, "needs Jack's confirm: sending the report outbound")
    t = led.get(slug)
    assert t.status == "blocked"
    assert "needs Jack's confirm" in t.blocked_on
    led.unblock(slug, 1)
    assert led.get(slug).status == "in-progress"
    assert led.get(slug).blocked_on == ""
    led.complete_step(slug, 1, "Jack approved; report sent, confirm logged")
    assert led.get(slug).status == "done"


@pytest.mark.case("TSK-005", "an open duplicate slug refuses; a closed one gets a suffix")
def test_duplicate_slugs(sandbox):
    led = _ledger(sandbox)
    led.create("Sort the workshop inbox", ["only step"])
    with pytest.raises(ValueError):
        led.create("Sort the workshop inbox", ["another"])
    led.complete_step("sort_the_workshop_inbox", 0, "done; verified empty inbox")
    t2 = led.create("Sort the workshop inbox", ["again"])
    assert t2.slug == "sort_the_workshop_inbox_2"


@pytest.mark.case("TSK-006", "list_open excludes done and cancelled tasks")
def test_list_open(sandbox):
    led = _ledger(sandbox)
    led.create("Job alpha", ["a"])
    led.create("Job beta", ["b"])
    led.create("Job gamma", ["c"])
    led.complete_step("job_alpha", 0, "alpha finished; file exists")
    led.cancel("job_beta", "Jack changed his mind")
    assert [t.slug for t in led.list_open()] == ["job_gamma"]
    assert led.get("job_beta").status == "cancelled"


@pytest.mark.case("TSK-007", "current_step is the first not-done step; None when finished")
def test_current_step(sandbox):
    led = _ledger(sandbox)
    led.create("Two step job", ["step one", "step two"])
    slug = "two_step_job"
    assert led.get(slug).current_step() == 0
    led.complete_step(slug, 0, "one done; checked")
    assert led.get(slug).current_step() == 1
    led.complete_step(slug, 1, "two done; checked")
    assert led.get(slug).current_step() is None


@pytest.mark.case("TSK-008", "summary() is compact, active-only, and quotes the blocked reason")
def test_summary(sandbox):
    led = _ledger(sandbox)
    assert led.summary() == "(no active tasks)"
    led.create("Two step job", ["step one", "step two"])
    led.block("two_step_job", 0, "waiting on Jack: delete confirmation")
    s = led.summary()
    assert "two_step_job" in s and "BLOCKED" in s
    assert "waiting on Jack: delete confirmation" in s
    led2 = _ledger(sandbox)
    led2.create("Job alpha", ["a"])
    led2.complete_step("job_alpha", 0, "alpha finished")
    assert "job_alpha" not in led2.summary()  # done tasks don't ride along


@pytest.mark.case("TSK-009", "evidence is stored verbatim, one line per completion note")
def test_evidence_verbatim(sandbox):
    led = _ledger(sandbox)
    led.create("Job alpha", ["a"])
    evidence = "calc('12 V / (4 ohm)', 'A') -> 3 A | grader agreed"
    led.complete_step("job_alpha", 0, evidence)
    assert led.get("job_alpha").steps[0].evidence == [evidence]
    raw = sandbox.brain.read_note("tasks/job_alpha.md")
    assert f"  - evidence: {evidence}" in raw


@pytest.mark.case("TSK-010", "unknown slug or step index fails loudly, changing nothing")
def test_unknown_targets(sandbox):
    led = _ledger(sandbox)
    led.create("Job alpha", ["a"])
    assert led.get("no_such_task") is None
    with pytest.raises(ValueError):
        led.complete_step("no_such_task", 0, "evidence")
    with pytest.raises(ValueError):
        led.complete_step("job_alpha", 5, "evidence")


@pytest.mark.case("TSK-011", "write_brain to tasks/ is refused in all three modes, naming the task tools")
def test_write_guard_blocks_tasks_dir(sandbox):
    for mode in ("create", "append", "overwrite"):
        with pytest.raises(PermissionDenied, match="task"):
            sandbox.brain.write_note("tasks/anything.md", "junk", mode=mode)


@pytest.mark.case("TSK-012", "the write guard doesn't touch the ledger's own system_write path")
def test_write_guard_leaves_ledger_path_open(sandbox):
    led = _ledger(sandbox)
    t = led.create("Job alpha", ["a"])
    assert t.slug == "job_alpha"
    led.complete_step("job_alpha", 0, "alpha finished; verified")
    assert led.get("job_alpha").steps[0].state == "done"


@pytest.mark.case("TSK-013", "test-session task files keep their logical "
                             "ledger identity under test_archive routing")
def test_test_session_archive_tasks_remain_listable(sandbox):
    sandbox.brain.test_session = True
    led = _ledger(sandbox)

    led.create("Calibration run", ["Zero the gauge", "Apply reference load"])

    archived = (sandbox.brain.root / "test_archive" / "tasks" /
                "calibration_run.md")
    assert archived.is_file()
    assert [task.slug for task in led.list_open()] == ["calibration_run"]
    assert [task.slug for task in led.list_all()] == ["calibration_run"]
    led.complete_step("calibration_run", 0, "Zero the gauge")
    assert led.get("calibration_run").steps[0].state == "done"

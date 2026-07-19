r"""
JOB — the background job runner (jarvis plan J1.3/J1.4, roadmap M3.3).
Scripted-model, no live 14B (the test_task_tools.py posture): one instance
per FridayService, driven from _background_loop, taking AT MOST ONE tracked-
task step per tick, entirely through engine.respond() so every floor/gate/
taint mechanism applies exactly as in a live chat turn.

JOB-001  toggle off -> no run (model never even called).
JOB-002  suite lockfile with a live PID -> pause; a stale PID -> proceeds.
JOB-003  busy already held -> skip, no deadlock.
JOB-004  one step per tick; evidence-grounded completion advances the file.
JOB-005  session-state snapshot: history/referents/ledgers identical before
         and after a job turn.
JOB-006  two consecutive no-progress ticks -> the task is force-blocked with
         the honest reason.
JOB-007  toast suppressed under DND; the work itself still happens.
JOB-008  job_turn flag lands in the ilog for a runner-driven turn, absent
         (False) for ordinary chat.
"""

import pytest

from core.model import ModelReply

STEPS = ["Step one text", "Step two text"]


class _ScriptModel:
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
        return r


class _PoisonModel:
    """Fails loudly if the runner ever calls the model — proves a gated tick
    never fires a turn at all (rather than firing one we forgot to check)."""

    def chat(self, *a, **kw):
        raise AssertionError("JobRunner should not have called the model this tick")


def _call(name, **kwargs):
    return {"function": {"name": name, "arguments": kwargs}}


def _arm(sandbox, tmp_path, ollama_up=True, suite_lock=False):
    """Enable jobs, point the suite lock at a throwaway path, stub Ollama
    reachability — the plumbing every JOB case needs, isolated from the
    real repo's results/ and the real Ollama daemon."""
    sandbox.service.toggles.set("jobs.background_enabled", True)
    sandbox.service.jobs.results_dir = tmp_path / "results"
    sandbox.service.jobs.results_dir.mkdir(parents=True, exist_ok=True)
    import core.jobs as jobs_mod
    jobs_mod.ollama_healthy = lambda host: ollama_up
    return sandbox.service.jobs


@pytest.mark.case("JOB-001", "toggle off -> no run; the model is never called")
def test_job001_toggle_off_no_run(sandbox, tmp_path):
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    sandbox.service.toggles.set("jobs.background_enabled", False)
    sandbox.service.engine.model = _PoisonModel()
    runner.tick()   # must not raise -> the poison model was never touched
    t = led.get("job_alpha")
    assert t.steps[0].state == "pending"


@pytest.mark.case("JOB-002", "a suite lock with a LIVE pid pauses the "
                             "runner; a stale pid lets it proceed")
def test_job002_suite_lock_pid_liveness(sandbox, tmp_path):
    import os
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    lock = runner.results_dir / "SUITE_RUNNING.lock"

    lock.write_text(str(os.getpid()), encoding="utf-8")  # this process: alive
    sandbox.service.engine.model = _PoisonModel()
    runner.tick()
    assert led.get("job_alpha").steps[0].state == "pending"

    lock.write_text("999999999", encoding="utf-8")  # essentially never a real pid
    sandbox.service.engine.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="job_alpha", step=1,
            evidence="Step one text")]},
        "Done.",
    ])
    runner.tick()
    assert led.get("job_alpha").steps[0].state == "done"


@pytest.mark.case("JOB-003", "the busy lock already held -> skip, no deadlock")
def test_job003_busy_held_skips(sandbox, tmp_path):
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    sandbox.service.engine.model = _PoisonModel()
    assert sandbox.service._busy.acquire(blocking=False)
    try:
        runner.tick()   # must return immediately, never touching the model
    finally:
        sandbox.service._busy.release()
    assert led.get("job_alpha").steps[0].state == "pending"


@pytest.mark.case("JOB-004", "one step per tick; evidence-grounded "
                             "completion advances the file")
def test_job004_one_step_advances(sandbox, tmp_path):
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    sandbox.service.engine.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="job_alpha", step=1,
            evidence="Step one text")]},
        "Done with step one.",
    ])
    runner.tick()
    t = led.get("job_alpha")
    assert t.steps[0].state == "done"
    assert t.steps[1].state == "pending"   # only ONE step per tick


@pytest.mark.case("JOB-005", "session-state snapshot: history/referents/"
                             "ledgers identical before and after a job turn")
def test_job005_session_state_untouched(sandbox, tmp_path):
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    eng = sandbox.service.engine
    eng.history = [{"role": "user", "content": "earlier chat"}]
    eng.referents = [{"kind": "project", "name": "alpha_rig", "detail": "d",
                     "when": "10:00", "summary": ""}]
    eng.offer = {"text": "want me to file it?", "referents": []}
    eng.pending_task = {"request": "order the actuator", "blocker":
                       "which model number", "turns_left": 3}
    eng.consolidation = {"filter": "flux projects", "candidates": ["fluxbeam"],
                        "survivor": None, "default": "fluxbeam", "turns_left": 3}
    eng.corrections = [{"right": "active", "wrong": "archived"}]
    before = (list(eng.history), list(eng.referents), dict(eng.offer),
             dict(eng.pending_task), dict(eng.consolidation), list(eng.corrections))

    eng.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="job_alpha", step=1,
            evidence="Step one text")]},
        "Done.",
    ])
    runner.tick()

    after = (eng.history, eng.referents, eng.offer, eng.pending_task,
             eng.consolidation, eng.corrections)
    assert after == before
    assert led.get("job_alpha").steps[0].state == "done"   # the job itself DID happen


@pytest.mark.case("JOB-006", "two consecutive no-progress ticks force-block "
                             "the task with the honest reason")
def test_job006_no_progress_force_blocks(sandbox, tmp_path):
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    sandbox.service.engine.model = _ScriptModel([
        "Just thinking about it, nothing to report yet.",
        "Still working through it in my head.",
    ])
    runner.tick()
    t = led.get("job_alpha")
    assert t.status != "blocked"   # first miss: not yet force-blocked

    runner.tick()
    t = led.get("job_alpha")
    assert t.status == "blocked"
    assert t.blocked_on == "background step made no progress"


@pytest.mark.case("JOB-007", "toasts suppressed under DND; the work itself "
                             "still happens")
def test_job007_dnd_suppresses_toast_not_work(sandbox, tmp_path):
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    sandbox.service.acc.set_dnd(True)
    sandbox.service.engine.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="job_alpha", step=1,
            evidence="Step one text")]},
        "Done.",
    ])
    runner.tick()
    assert led.get("job_alpha").steps[0].state == "done"
    assert sandbox.rec.pings == []


@pytest.mark.case("JOB-008", "job_turn is True in the ilog for a "
                             "runner-driven turn, False for ordinary chat")
def test_job008_job_turn_flag(sandbox, tmp_path):
    led = sandbox.service.engine.task_ledger
    led.create("Job alpha", STEPS)
    runner = _arm(sandbox, tmp_path)
    cap = []
    sandbox.service.engine.ilog.log = lambda d: cap.append(d)
    sandbox.service.engine.model = _ScriptModel([
        {"content": "", "tool_calls": [_call(
            "complete_task_step", slug="job_alpha", step=1,
            evidence="Step one text")]},
        "Done.",
    ])
    runner.tick()
    assert cap[-1]["job_turn"] is True

    sandbox.service.engine.model = _ScriptModel(["Just chatting."])
    sandbox.service.engine.respond("How's it going?")
    assert cap[-1]["job_turn"] is False

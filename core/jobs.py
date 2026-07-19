r"""
JobRunner — the background step-taker for durable tasks (jarvis plan J1.3/
J1.4, roadmap M3.3). One instance per FridayService, driven from the existing
_background_loop tick (core/service.py, the briefing block is the template).

Each tick runs AT MOST ONE step of ONE open task (preemption between steps,
never mid-step) — entirely through engine.respond(), so every floor, the
gate, taint defense, and referent tracking apply exactly as in a live chat
turn. Nothing here bypasses them; the only thing JobRunner adds is (1) a
code-built brief instead of Jack's words, and (2) the confirm callback
temporarily returns "no" unconditionally for the duration of the turn — an
outbound/destructive step therefore auto-parks by construction, because a
background turn can never get Jack's live approval. The conversation's own
session state (history, referents, offer, pending_task, consolidation,
corrections) is snapshotted and restored around the call — a background step
must never leak into or mutate the chat Jack comes back to.
"""

import copy
import subprocess
from pathlib import Path

from core.bootstrap import ROOT
from core.tools.task_tools import render_task
from scripts.ollama_watchdog import ollama_resident

SUITE_LOCK_NAME = "SUITE_RUNNING.lock"


def _pid_alive(pid: int) -> bool:
    """Windows-safe liveness probe (never os.kill(pid, 0) — see
    ollama_watchdog's own note: that call TERMINATES on Windows)."""
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True, text=True, timeout=30,
    ).stdout
    return str(pid) in out


def suite_running(results_dir: Path) -> bool:
    """True only while run_suite.py's recorded PID is still alive. A stale
    lock (crashed run, no cleanup) must never wedge the runner forever —
    tolerance is the point, not just detection."""
    lock = Path(results_dir) / SUITE_LOCK_NAME
    try:
        pid = int(lock.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return _pid_alive(pid)


def ollama_healthy(host: str) -> bool:
    """Reachability only (reuses ollama_watchdog's own probe) — a background
    step must never fire into an unreachable/wedged Ollama and hang the
    daemon thread."""
    try:
        ollama_resident(host)
        return True
    except Exception:
        return False


def _snapshot(engine) -> dict:
    # deepcopy, not a shallow list()/dict() copy: _pending_task_update and
    # friends mutate their dicts IN PLACE (e.g. turns_left -= 1) — a shallow
    # copy would still alias the same nested dict and "restore" the mutated
    # value right back (caught by JOB-005).
    return {
        "history": copy.deepcopy(engine.history),
        "referents": copy.deepcopy(engine.referents),
        "offer": copy.deepcopy(engine.offer),
        "pending_task": copy.deepcopy(engine.pending_task),
        "consolidation": copy.deepcopy(engine.consolidation),
        "corrections": copy.deepcopy(engine.corrections),
    }


def _restore(engine, snap: dict) -> None:
    engine.history = snap["history"]
    engine.referents = snap["referents"]
    engine.offer = snap["offer"]
    engine.pending_task = snap["pending_task"]
    engine.consolidation = snap["consolidation"]
    engine.corrections = snap["corrections"]


_BRIEF = (
    "Background step of tracked task '{slug}'. The current step: {step}\n"
    "Full task state:\n{state}\n"
    "Do this ONE step now with tools, then complete_task_step with verbatim "
    "evidence; if it needs Jack (outbound/destructive/missing input), call "
    "block_task with the reason.")


class JobRunner:
    """tick() is called from FridayService._background_loop every poll — no
    threads of its own. NO_PROGRESS_LIMIT consecutive ticks with neither a
    completed step nor a block_task call force-park the task rather than
    spin forever on the same stuck step."""

    NO_PROGRESS_LIMIT = 2

    def __init__(self, service, results_dir: Path = None):
        self.service = service
        self.results_dir = Path(results_dir) if results_dir else ROOT / "results"
        self._no_progress = {}   # slug -> consecutive no-progress count

    def enabled(self) -> bool:
        return bool(self.service.toggles.get("jobs.background_enabled"))

    # ---------- the tick ----------

    def tick(self) -> None:
        if not self.enabled():
            return
        engine = self.service.engine
        ledger = getattr(engine, "task_ledger", None)
        if ledger is None:
            return
        research = getattr(engine, "research", None)
        if research is not None and research.active_tag:
            return
        if suite_running(self.results_dir):
            return
        host = self.service.config.get("model", {}).get("host", "")
        if not ollama_healthy(host):
            return
        if not self.service._busy.acquire(blocking=False):
            return
        try:
            task = self._next_task(ledger)
            if task is not None:
                self._run_step(engine, ledger, task)
        finally:
            self.service._busy.release()

    def _next_task(self, ledger):
        """Oldest open, unblocked, unfinished task — FIFO fairness across
        concurrent jobs, never slug order (list_open()'s own sort)."""
        candidates = [t for t in ledger.list_open()
                     if t.status != "blocked" and t.current_step() is not None]
        if not candidates:
            return None
        return sorted(candidates, key=lambda t: t.created)[0]

    def _run_step(self, engine, ledger, task) -> None:
        cur = task.current_step()
        brief = _BRIEF.format(slug=task.slug, step=task.steps[cur].text,
                              state=render_task(task))

        snap = _snapshot(engine)
        orig_confirm = engine.gate.confirm
        # A background turn can never get Jack's live approval — auto-decline
        # for the whole turn (the RESEARCH-BLOCKED "no confirm shown"
        # posture), so an outbound/destructive step parks instead of hanging
        # the daemon thread waiting on a click nobody will make.
        engine.gate.confirm = lambda description: False
        engine._job_turn = True
        try:
            engine.respond(brief, on_token=None)
        finally:
            engine._job_turn = False
            engine.gate.confirm = orig_confirm
            _restore(engine, snap)

        after = ledger.get(task.slug)
        if after is None:
            return   # cancelled mid-step somehow — nothing left to reconcile
        progressed = after.steps[cur].state == "done" or after.status == "blocked"
        if progressed:
            self._no_progress[task.slug] = 0
            self._notify(after)
            return
        n = self._no_progress.get(task.slug, 0) + 1
        self._no_progress[task.slug] = n
        if n >= self.NO_PROGRESS_LIMIT:
            ledger.block(task.slug, cur, "background step made no progress")
            self._no_progress[task.slug] = 0
            self._notify(ledger.get(task.slug))

    def _notify(self, task) -> None:
        """Completion or parking pings the frontend, DND-respecting (DND
        silences toasts, never the background work itself — Accountability's
        own posture, reused verbatim). The away board (M3.4) reads ledger
        state live, so there is nothing separate to 'land' there."""
        if self.service.acc.dnd:
            return
        if task.status == "blocked":
            msg = f"Task '{task.slug}' parked: {task.blocked_on}"
        elif task.status == "done":
            msg = f"Task '{task.slug}' finished."
        else:
            cur = task.current_step()
            if cur is None:
                return
            msg = f"Task '{task.slug}': step done, now on {cur + 1}. {task.steps[cur].text}"
        self.service._emit("on_ping", msg)

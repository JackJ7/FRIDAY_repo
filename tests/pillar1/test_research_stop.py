r"""
Autoresearch stop-path integrity — the PURE-CODE lock (FRIDAY_notes10_plan.md
Phase 7). No model, no GPU, no network, so these run in --quick.

The 2026-07-13 smoke test found three defects with one shape: a run that is NOT
active (crashed during setup / done / already stopped) made "stop research" fail
incoherently — the model was left to guess an empty tag, `stop("")` degraded to
`_runs.get("")` → "No active run tagged ''", and (if status had been checked)
the taint gate carded Jack's own typed command.

The fix is deterministic and lives in two places, both locked here:
  * ResearchManager — `_resolve_tag` (empty tag -> the run on record),
    `latest_tag`/`latest_status` (single run-state source), and a `stop` that
    reports a terminal run's ledger state instead of fabricating a fresh
    "stopped".
  * Engine.respond — a sibling branch to the busy-gate that intercepts a
    stop-shaped request when NO run is active, answers from the ledger in code,
    and returns BEFORE the taint line (so no tool call, no CONTENT-TRIGGERED
    card). Exercised with a bare Engine + a real manager (STOP-002).
"""

import threading

import pytest

from core.engine import Engine
from core.tools.research_tools import ResearchManager


# ----------------------------------------------------------------------
# Fixtures: a real ResearchManager over a tmp ledger dir (no GPU/network in
# __init__), plus seeders for live and terminal runs.
# ----------------------------------------------------------------------

def _manager(base):
    """A real manager rooted at a throwaway ledger dir. registry/gate/policy are
    unused by the stop-path, so None is fine."""
    return ResearchManager(registry=None, gate=None, policy=None, base_dir=base,
                           host="", edit_model="", edit_model_num_ctx=0)


def _seed_ledger(mgr, tag, state, *, updated=None, iteration=0, max_iters=10,
                 message="", in_runs=False, running=False):
    """Write a status.json for `tag` (an earlier-session run leaves ONLY this on
    disk). `in_runs`/`running` also add an in-memory run object — the live-session
    shape, where finalize() keeps the object with its terminal state."""
    mgr._write_status(tag, {
        "tag": tag, "repo": "https://example/repo", "state": state,
        "iteration": iteration, "max_iters": max_iters,
        "updated": updated or f"2026-07-13T10:{iteration:02d}:00",
        "best_val_bpb": None, "message": message,
    })
    if in_runs:
        mgr._runs[tag] = {"stop_event": threading.Event(), "proc": None,
                          "thread": None, "state": state}
    return tag


def _bare_engine(mgr):
    """A bare Engine wired only with `research` — enough to reach the stop branch,
    which returns before any retriever/brain/taint work (so __init__ is skipped,
    exactly like test_date_floor's _engine)."""
    e = Engine.__new__(Engine)
    e.research = mgr
    return e


# ======================================================================
# STOP-001 — the untouched happy path: an ACTIVE run is really stopped.
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("STOP-001", "an active running run is finalized by stop(tag) "
                             "(existing behavior preserved)")
def test_stop_active_run_finalizes(tmp_path):
    mgr = _manager(tmp_path)
    _seed_ledger(mgr, "run1", "running", in_runs=True, message="training")
    out = mgr.stop("run1")
    assert "Stopped research 'run1'" in out
    # It really signaled + wrote a stopped state (this is the only path that does).
    assert mgr._runs["run1"]["stop_event"].is_set()
    assert mgr._read_status("run1")["state"] == "stopped"


# ======================================================================
# STOP-002 — the headline defect: a CRASHED run + "stop research" yields one
# coherent deterministic reply, NO fabricated stop, NO tool call / taint card.
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("STOP-002", "crashed run + 'stop research' -> one deterministic "
                             "message naming the terminal state + kept workspace; "
                             "no fabricated stop, no tool call")
def test_crashed_run_stop_is_deterministic(tmp_path):
    mgr = _manager(tmp_path)
    # A run that crashed during setup: the finalize() shape keeps the object with
    # its terminal state AND leaves the ledger on disk.
    _seed_ledger(mgr, "smoke1", "crashed", in_runs=True,
                 message="crashed during setup")

    # active_tag is None for a crashed run, so the busy-gate is skipped and the
    # NEW stop branch handles it. A bare Engine reaches the branch and returns.
    e = _bare_engine(mgr)
    reply = e.respond("please stop the research")

    # One coherent message: names the run, its terminal state, and the kept
    # workspace — never "no active runs" and never a stop-tool proposal.
    assert "smoke1" in reply.content
    assert "crashed" in reply.content
    assert r"data\research\smoke1" in reply.content
    # The reply is the deterministic text itself — no tool calls were emitted
    # (the branch returns before the model tool-loop).
    assert not getattr(reply, "tool_calls", None)
    # NO fabricated stop: the ledger state is still 'crashed', not 'stopped'.
    assert mgr._read_status("smoke1")["state"] == "crashed"
    # And the crash run's stop_event was never signaled (nothing was running).
    assert not mgr._runs["smoke1"]["stop_event"].is_set()


@pytest.mark.upgrade
@pytest.mark.case("STOP-002b", "stop() on a crashed run reports its state and does "
                              "NOT rewrite the ledger to 'stopped'")
def test_stop_terminal_run_reports_not_fabricates(tmp_path):
    mgr = _manager(tmp_path)
    _seed_ledger(mgr, "smoke1", "crashed", in_runs=True)
    out = mgr.stop("smoke1")
    assert "already crashed" in out and "smoke1" in out
    assert mgr._read_status("smoke1")["state"] == "crashed"  # unchanged


# ======================================================================
# STOP-003 — a bare/empty tag resolves to the sole run (no literal "").
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("STOP-003", "stop('') with exactly one run resolves to it "
                             "instead of degrading to the literal ''")
def test_empty_tag_resolves_to_sole_run(tmp_path):
    mgr = _manager(tmp_path)
    _seed_ledger(mgr, "only", "done", in_runs=True, message="budget reached")
    assert mgr._resolve_tag("") == "only"
    assert mgr.latest_tag() == "only"
    out = mgr.stop("")  # bare tag — the model-guess shape
    # Resolves to 'only' and reports its terminal state (done), never "tagged ''".
    assert "only" in out and "tagged ''" not in out
    assert mgr._read_status("only")["state"] == "done"


# ======================================================================
# STOP-004 — no runs at all: graceful, no exception.
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("STOP-004", "no runs on record -> graceful 'nothing to stop', "
                             "no exception, and the engine branch says so too")
def test_no_runs_graceful(tmp_path):
    mgr = _manager(tmp_path)
    assert mgr._resolve_tag("") == ""
    assert mgr.latest_tag() == ""
    assert mgr.latest_status() == {}
    assert "nothing to stop" in mgr.stop("").lower()

    # Engine branch with no runs: the deterministic no-run message, no crash.
    e = _bare_engine(mgr)
    reply = e.respond("stop research")
    assert "no research run" in reply.content.lower()
    assert not getattr(reply, "tool_calls", None)


# ======================================================================
# STOP-005 — _resolve_tag picks the MOST-RECENT when several ledgers exist.
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("STOP-005", "_resolve_tag / latest_tag pick the most-recent run "
                             "(by ledger `updated`) across several ledger dirs")
def test_resolve_picks_most_recent(tmp_path):
    mgr = _manager(tmp_path)
    _seed_ledger(mgr, "old", "done", updated="2026-07-10T09:00:00")
    _seed_ledger(mgr, "mid", "crashed", updated="2026-07-12T09:00:00")
    _seed_ledger(mgr, "new", "stopped", updated="2026-07-13T09:00:00")
    assert mgr.latest_tag() == "new"
    assert mgr._resolve_tag("") == "new"
    # latest_status reads the winner's ledger.
    assert mgr.latest_status()["state"] == "stopped"
    # An explicit tag is always honored as-is (never overridden by recency).
    assert mgr._resolve_tag("old") == "old"


@pytest.mark.upgrade
@pytest.mark.case("STOP-005b", "on-disk ledger dirs from an earlier session are "
                              "visible to _resolve_tag even with an empty _runs map")
def test_resolve_sees_disk_only_runs(tmp_path):
    mgr = _manager(tmp_path)
    # No in-memory runs — only status.json on disk (the crash/restart case).
    _seed_ledger(mgr, "past", "crashed", updated="2026-07-13T08:00:00")
    assert mgr._runs == {}
    assert mgr.latest_tag() == "past"
    out = mgr.stop("")
    assert "past" in out and "already crashed" in out

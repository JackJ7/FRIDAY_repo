r"""
GT-J1 — durable task ledger golden transcript (jarvis plan J1, roadmap M3.2g).

NEW-CAPABILITY role (recorded honestly): the task tools don't exist on the
M2 baseline, so this case cannot run there — its bar is a batch-fraction on
the m3 branch (x5 minute-spaced live runs, pinned --basetemp), never a
baseline conversion. Throwaway job content only ("flux bench refit" — the
FLUX_SLUGS fixture convention already used elsewhere in this suite).

T1  one message, a 3-step LOCAL job. LOCKED: a tasks/ file exists with 3
    pending steps (create_task actually ran, on disk). TARGET: the reply
    presents the plan.
T2  "I did step one just now, tick it off." LOCKED: step 1 done with a
    non-empty evidence line; steps 2-3 still pending (the never-claim
    contract, checked on disk — a status ask or a completion claim must
    never move a step the ledger doesn't independently confirm).
T3  a bare status ask. LOCKED: ledger state unchanged (same invariant as
    T2 — a read-only question must not mutate the ledger). TARGET: the
    reply names the impeller step as current.
"""

from datetime import datetime

import pytest

from helpers.transcript import (LOCKED, TARGET, Turn, check, english_only,
                                record_and_assert, replay)

JOB_MESSAGE = ("Track the flux bench refit: drain the coolant loop, swap "
              "the pump impeller, re-run the pressure check — set it up "
              "and tell me the plan.")


def _open_task(ctx):
    tasks = ctx.engine.task_ledger.list_open()
    return tasks[0] if len(tasks) == 1 else None


def _task_created_3_pending(ctx):
    t = _open_task(ctx)
    if t is None:
        return False, f"expected exactly 1 open task, found "\
                     f"{len(ctx.engine.task_ledger.list_open())}"
    if len(t.steps) != 3:
        return False, f"expected 3 steps, got {[s.text for s in t.steps]}"
    if any(s.state != "pending" for s in t.steps):
        return False, f"not all pending: {[(s.text, s.state) for s in t.steps]}"
    return True, f"task '{t.slug}' created, 3 pending steps"


def _plan_in_reply(ctx):
    keywords = ("coolant", "impeller", "pressure")
    hit = [k for k in keywords if k in ctx.reply_low]
    return bool(hit), f"plan keywords mentioned: {hit or 'none'}"


def _step1_done_rest_pending(ctx):
    t = _open_task(ctx)
    if t is None:
        return False, "no single open task found"
    ok = (t.steps[0].state == "done" and bool(t.steps[0].evidence)
          and t.steps[1].state == "pending"
          and t.steps[2].state == "pending")
    return ok, (f"states={[s.state for s in t.steps]} "
               f"evidence0={t.steps[0].evidence}")


def _impeller_current(ctx):
    t = _open_task(ctx)
    if t is None:
        return False, "no single open task found"
    cur = t.current_step()
    named = cur is not None and "impeller" in ctx.reply_low
    return named, (f"current_step={cur} "
                   f"({t.steps[cur].text if cur is not None else 'n/a'}); "
                   f"'impeller' in reply={'impeller' in ctx.reply_low}")


@pytest.mark.model
@pytest.mark.skill("project_ops")
@pytest.mark.upgrade
@pytest.mark.case("GT-J1", "durable task ledger: create from one message, "
                          "evidence-grounded step completion, status ask "
                          "leaves the ledger untouched")
def test_gt_j1_flux_bench_job(sandbox, detail):
    turns = [
        Turn(JOB_MESSAGE, [
            check("task-created-3-pending", LOCKED, _task_created_3_pending),
            check("plan-in-reply", TARGET, _plan_in_reply),
            english_only(TARGET),
        ]),
        Turn("The coolant loop's drained — I did it just now. Tick it off.", [
            check("step1-done-rest-pending", LOCKED, _step1_done_rest_pending),
            english_only(TARGET),
        ]),
        Turn("Where are we on the flux bench job?", [
            check("ledger-unchanged-by-status-ask", LOCKED,
                 _step1_done_rest_pending),
            check("names-impeller-current", TARGET, _impeller_current),
            english_only(TARGET),
        ]),
    ]
    record_and_assert(replay(sandbox, turns), detail)

r"""
BRD — the while-you-were-away board (jarvis plan J1.5, roadmap M3.4).
Non-model: FridayService.get_away_board() is read-only and code-built, no
tool/model call involved. `parked` = every open blocked task; `finished` =
status done with `updated` within the last 48h. Every fact is a LEDGER QUOTE
(armor P3) — no model text anywhere in the board.

BRD-001  shape: parked/finished entries carry exactly slug/title/blocked_on
         (or updated)/evidence.
BRD-002  the 48h window: a task finished 49h ago is excluded; one finished
         1h ago is included.
BRD-003  evidence is the verbatim ledger quote, not a summary/paraphrase.
BRD-004  empty state: no tasks at all -> both lists empty, no crash.
"""

import re
from datetime import datetime, timedelta

import pytest

STEPS = ["Drain the coolant loop", "Swap the pump impeller"]


def _backdate(sandbox, slug, when: datetime):
    """Force a task file's 'updated:' frontmatter field to an arbitrary
    timestamp — TaskLedger._save() always stamps _now(), so the 48h-window
    test has to bypass the public API the way TaskLedger itself does
    (system_write), never through write_note (M3.1's guard blocks that)."""
    raw = sandbox.brain.read_note(f"tasks/{slug}.md")
    new = re.sub(r"(?m)^updated: .*$", f"updated: {when.isoformat()}", raw, count=1)
    assert new != raw, "no 'updated:' field found to backdate"
    sandbox.brain.system_write(f"tasks/{slug}.md", new, summary="test backdate")


@pytest.mark.case("BRD-001", "shape: parked and finished entries carry the "
                             "documented fields")
def test_brd001_shape(sandbox):
    led = sandbox.service.engine.task_ledger
    led.create("Flux bench refit", STEPS)
    led.block("flux_bench_refit", 0, "needs Jack's confirm: which coolant line")
    board = sandbox.service.get_away_board()
    assert board["parked"] and not board["finished"]
    p = board["parked"][0]
    assert set(p.keys()) == {"slug", "title", "blocked_on", "evidence"}
    assert p["slug"] == "flux_bench_refit"
    assert p["title"] == "Flux bench refit"
    assert "which coolant line" in p["blocked_on"]


@pytest.mark.case("BRD-002", "48h window: finished 49h ago is excluded, "
                             "finished 1h ago is included")
def test_brd002_48h_window(sandbox):
    led = sandbox.service.engine.task_ledger
    led.create("Old job", ["only step"])
    led.complete_step("old_job", 0, "done long ago; verified")
    _backdate(sandbox, "old_job", datetime.now() - timedelta(hours=49))

    led.create("Recent job", ["only step"])
    led.complete_step("recent_job", 0, "done recently; verified")
    _backdate(sandbox, "recent_job", datetime.now() - timedelta(hours=1))

    board = sandbox.service.get_away_board()
    slugs = {f["slug"] for f in board["finished"]}
    assert "recent_job" in slugs
    assert "old_job" not in slugs


@pytest.mark.case("BRD-003", "evidence is the verbatim ledger quote")
def test_brd003_verbatim_evidence(sandbox):
    led = sandbox.service.engine.task_ledger
    led.create("Flux bench refit", STEPS)
    evidence = "calc('12 V / 4 ohm', 'A') -> 3 A | grader agreed"
    led.complete_step("flux_bench_refit", 0, evidence)
    led.complete_step("flux_bench_refit", 1, "impeller swapped; visually confirmed")
    board = sandbox.service.get_away_board()
    f = next(x for x in board["finished"] if x["slug"] == "flux_bench_refit")
    assert evidence in f["evidence"]
    assert "impeller swapped; visually confirmed" in f["evidence"]


@pytest.mark.case("BRD-004", "empty state: no tasks at all -> both lists "
                             "empty, no crash")
def test_brd004_empty_state(sandbox):
    board = sandbox.service.get_away_board()
    assert board == {"parked": [], "finished": []}

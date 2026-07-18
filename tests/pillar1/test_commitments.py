r"""COM — commitment tracker: inference, confirm-to-commit, dedup, date math, pacing."""

from datetime import date, timedelta

import pytest

from helpers.harness import repeat_behavior


@pytest.mark.case("COM-001", "casual intent is inferred into a PENDING commitment (N runs)")
@pytest.mark.model
@pytest.mark.skill("project_ops")
def test_inference_pending(sandbox, detail):
    def attempt(i):
        sb = sandbox
        sb.service.engine.tracker._save([], "reset")
        sb.rec.reset()
        sb.ask("By the way, I need to order the GM6208 motors this week.")
        pend = sb.service.engine.tracker.pending_items()
        return (len(pend) == 1), {"pending": [c.text for c in pend],
                                  "tools": sb.rec.tool_names()}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox, detail=detail)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "casual intent not inferred to exactly one pending item"


@pytest.mark.case("COM-002", "confirm promotes pending->open; decline removes it")
def test_confirm_decline(sandbox):
    tr = sandbox.service.engine.tracker
    c = tr.add("Order motors", inferred=True)
    tr.confirm(c.id)
    assert tr.open_items() and tr.open_items()[0].id == c.id
    c2 = tr.add("Imaginary task", inferred=True)
    tr.decline(c2.id)
    assert all(x.id != c2.id for x in tr.pending_items())


@pytest.mark.case("COM-003", "duplicate intent does not create a second item")
def test_dedup(sandbox):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    a = tr.add("Order the GM6208 motors", inferred=True)
    b = tr.add("order the gm6208 motors", inferred=True)
    assert a.id == b.id and len(tr.pending_items()) == 1


@pytest.mark.case("COM-004", "overdue math: a past-due open item reports overdue")
def test_overdue(sandbox):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    c = tr.add("Email advisor", due=(date.today() - timedelta(days=2)).isoformat())
    tr.confirm(c.id)
    assert tr.open_items()[0].overdue()


@pytest.mark.case("COM-005", "verbatim weekday deadline resolves to the correct ISO date (code)")
def test_date_resolution():
    from core.tools.commitment_tools import _resolve_due
    today = date.today()
    for name, idx in [("monday", 0), ("friday", 4), ("sunday", 6)]:
        expected = (today + timedelta(days=(idx - today.weekday()) % 7)).isoformat()
        assert _resolve_due(name) == expected, name
    assert _resolve_due("tomorrow") == (today + timedelta(days=1)).isoformat()
    assert _resolve_due("2026-09-01") == "2026-09-01"
    assert _resolve_due("someday") == ""  # unparseable -> no wrong date


@pytest.mark.case("COM-006", "a due/overdue commitment pings at most once per day")
def test_ping_pacing(sandbox):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    c = tr.add("Due today thing", due=date.today().isoformat())
    tr.confirm(c.id)
    first = sandbox.service.acc.due_pings()
    second = sandbox.service.acc.due_pings()
    assert len(first) == 1 and len(second) == 0


@pytest.mark.case("COM-007", "DND is persisted and reload-visible")
def test_dnd_persist(sandbox):
    sandbox.service.set_dnd(True)
    sandbox.restart()
    assert sandbox.service.acc.dnd is True


@pytest.mark.case("COM-008", "model-driven close marks a commitment done via tool")
@pytest.mark.model
@pytest.mark.skill("project_ops")
def test_model_close(sandbox, detail):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    c = tr.add("Order the GM6208 motors", inferred=False)
    reply = sandbox.ask("Good news, the GM6208 motors are ordered. Close that one out.")
    detail["reply"] = reply[:200]
    detail["tools"] = sandbox.rec.tool_names()
    assert not tr.open_items() or all(not x.text.lower().startswith("order")
                                      for x in tr.open_items())


@pytest.mark.case("COM-009", "close_commitment fuzzy-matches a leading-article "
                             "fragment (armor QB.1, the exact PT.8 repro): "
                             "'order GM6208 motors' closes 'Order the GM6208 "
                             "motors' via the registry tool")
def test_com009_fuzzy_close_repro(sandbox):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    tr.add("Order the GM6208 motors", inferred=False)
    out = sandbox.service.engine.registry.call(
        "close_commitment", {"which": "order GM6208 motors"})
    assert "Closed:" in out, out
    assert not tr.open_items(), tr.open_items()


@pytest.mark.case("COM-010", "two commitments sharing identifying tokens + a "
                             "fragment that fuzzy-matches BOTH (but is not a "
                             "literal substring of either, so find()'s "
                             "shortcut can't resolve it first) -> ERROR "
                             "naming both ids, nothing closed")
def test_com010_ambiguous_fuzzy_names_candidates(sandbox):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    tr.add("Order the GM6208 motors", inferred=False)
    tr.add("Order more GM6208 spare motors", inferred=False)
    # Reordered relative to either item's word order, so `needle in text`
    # (find()'s exact-substring path) misses both — only the token-set
    # fuzzy match can resolve (or, here, correctly refuse to resolve) it.
    out = sandbox.service.engine.registry.call(
        "close_commitment", {"which": "motors GM6208"})
    assert "ERROR" in out, out
    assert "RETRY NOW" in out, out
    assert len(tr.open_items()) == 2, tr.open_items()


@pytest.mark.case("COM-011", "zero-match fuzzy fragment keeps today's ERROR "
                             "text unchanged")
def test_com011_zero_match_unchanged(sandbox):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    tr.add("Order the GM6208 motors", inferred=False)
    out = sandbox.service.engine.registry.call(
        "close_commitment", {"which": "nonexistent widget"})
    assert out == ("ERROR: no open/pending commitment matches "
                   "'nonexistent widget'. Use list_commitments to see what's "
                   "tracked."), out
    assert len(tr.open_items()) == 1


@pytest.mark.case("COM-012", "exact-substring match still wins over fuzzy "
                             "(no regression when the id/substring already "
                             "matches)")
def test_com012_exact_substring_still_wins(sandbox):
    tr = sandbox.service.engine.tracker
    tr._save([], "reset")
    c = tr.add("Order the GM6208 motors", inferred=False)
    out = sandbox.service.engine.registry.call(
        "close_commitment", {"which": c.id})
    assert "Closed:" in out, out
    assert not tr.open_items()

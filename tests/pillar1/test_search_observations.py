r"""
search_observations + the FTS index (FRIDAY_notes10_plan.md Phase 4, §3) — real
full-text recall across every past session, backed by a derived, rebuildable
SQLite FTS5 index (stdlib, no new dependency). The observation markdown files
stay the source of truth; this index carries nothing they don't.

Pure logic (no model): drive the tool through the registry and the index
directly, and assert search finds by body term, stays honest on no match, a
from-scratch rebuild matches the incremental state, and test-session
observations never surface in a real session's search.
"""

import pytest


def _call(sandbox, name, args=None):
    return sandbox.service.engine.registry.call(name, args or {})


def _write_obs_file(root, oid, ts, title, body, type="fact", sub="observations"):
    d = root / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{oid}.md").write_text(
        f"---\nid: {oid}\nts: {ts}\ntype: {type}\ntitle: {title}\n"
        f"refs: []\nsession: s1\n---\n\n{body}\n", encoding="utf-8")


@pytest.mark.upgrade
@pytest.mark.case("FTS-001", "search_observations finds by body term; honest empty on no match")
def test_search_finds_and_empty(sandbox):
    store = sandbox.service.engine.observations
    if not store.index.available:
        pytest.skip("this Python build lacks sqlite FTS5")
    store.record("decision", "Sled gearbox ratio locked",
                 "We locked the camera-sled gearbox ratio at 4:1 after the "
                 "bench test showed backlash.", refs=["projects/sled.md"])

    out = _call(sandbox, "search_observations", {"query": "gearbox backlash"})
    assert "gearbox" in out.lower()
    assert "obs-" in out                                  # id surfaced to fetch
    # An unrelated query returns an honest empty, not a weak guess.
    off = _call(sandbox, "search_observations", {"query": "hydraulic durometer seal"})
    assert "No observations matched" in off


@pytest.mark.upgrade
@pytest.mark.case("FTS-002", "a from-scratch rebuild reproduces the incremental index state")
def test_rebuild_matches_incremental(sandbox):
    store = sandbox.service.engine.observations
    index = store.index
    if not index.available:
        pytest.skip("this Python build lacks sqlite FTS5")
    # Record several via the store — each indexed incrementally as it lands.
    store.record("fact", "Alpha rotor mass", "The alpha rotor mass is 2.1 kg.")
    store.record("task", "Order the bearings", "I'll order the alpha bearings Friday.")
    store.record("discovery", "Beta thermal margin", "Beta runs 12 C under limit.")

    def hits(q):
        return sorted(h["id"] for h in index.search(q, 20))

    before = {q: hits(q) for q in ("alpha", "bearings", "thermal", "beta rotor")}
    assert before["alpha"], "incremental index should already find 'alpha'"

    # Blow the index away and rebuild purely from the markdown files.
    n = index.rebuild()
    assert n >= 3
    after = {q: hits(q) for q in before}
    assert after == before, (before, after)


@pytest.mark.upgrade
@pytest.mark.case("FTS-003", "test-session observations never surface in a real session's search")
def test_test_archive_isolation(sandbox):
    store = sandbox.service.engine.observations
    index = store.index
    if not index.available:
        pytest.skip("this Python build lacks sqlite FTS5")
    assert not sandbox.brain.test_session
    # A stray observation in the TEST archive: a rebuild over a real session's
    # view (store.all excludes test_archive) must not pick it up.
    _write_obs_file(sandbox.brain.root, "obs-20260101-000000-tt",
                    "2026-01-01T00:00:00", "secret test widget",
                    "This is a test-only observation about a widget.",
                    sub="test_archive/observations")
    index.rebuild()
    assert index.search("widget", 20) == []
    assert not any(h["id"] == "obs-20260101-000000-tt"
                   for h in index.search("test observation", 20))


@pytest.mark.upgrade
@pytest.mark.case("FTS-004", "punctuation/empty queries are safe: no crash, no malformed MATCH")
def test_query_robustness(sandbox):
    store = sandbox.service.engine.observations
    index = store.index
    if not index.available:
        pytest.skip("this Python build lacks sqlite FTS5")
    store.record("fact", "Quoted phrase note", "A note mentioning NEAR and OR "
                 "and \"quotes\" and (parens) literally.")
    # Raw FTS operators / punctuation must be neutralised, not executed.
    for q in ('OR AND NEAR', '"unterminated', 'parens) (', '', '   ', '***'):
        res = index.search(q, 5)
        assert isinstance(res, list)              # never raises
    # A term that co-occurs with the operators still matches as a plain word.
    assert any("quoted" in h["title"].lower() or "quotes" in h["snippet"].lower()
               for h in index.search("quotes parens", 5))
    # The tool is registered internal (her own record — non-tainting).
    assert sandbox.service.engine.registry.kind("search_observations") == "internal"

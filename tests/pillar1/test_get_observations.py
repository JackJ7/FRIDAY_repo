r"""
get_observations tool (FRIDAY_notes10_plan.md Phase 4, §2) — the fetch-by-id
half of the claude-mem retrieval-economics port. The session-start index lists
observations one cheap line each (id + title); this tool pulls a full body ON
DEMAND, by id, so an old session is reachable without stuffing every recall into
the prompt.

Pure logic (no model): call the registered tool through the registry and the
store's get() directly, and assert progressive disclosure works, malformed ids
are refused (no path escape), and honesty on missing ids.
"""

import pytest


def _call(sandbox, name, args=None):
    return sandbox.service.engine.registry.call(name, args or {})


def _write_obs_file(root, oid, ts, title, body="body", type="fact"):
    d = root / "observations"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{oid}.md").write_text(
        f"---\nid: {oid}\nts: {ts}\ntype: {type}\ntitle: {title}\n"
        f"refs: [projects/x.md]\nsession: s1\n---\n\n{body}\n", encoding="utf-8")


@pytest.mark.upgrade
@pytest.mark.case("GETOBS-001", "get_observations pulls a full body by id, self-citing, with refs")
def test_fetch_full_body(sandbox):
    store = sandbox.service.engine.observations
    oid = store.record("decision", "Locked the sled ratio at 4:1",
                       "We locked the camera-sled gearbox ratio at 4:1 after the "
                       "bench test showed backlash at 3:1.",
                       refs=["projects/delta_sled.md"], session="s1")
    out = _call(sandbox, "get_observations", {"ids": [oid]})
    # Self-citing provenance stamp (carries the id + type + save date).
    assert f"obs {oid}" in out and "decision" in out
    # The FULL body, not just the title, comes back.
    assert "backlash at 3:1" in out
    # Refs surfaced so a grounded claim can cite the note it touched.
    assert "projects/delta_sled.md" in out


@pytest.mark.upgrade
@pytest.mark.case("GETOBS-002", "missing/malformed ids are reported honestly, never fabricated")
def test_missing_and_malformed(sandbox):
    store = sandbox.service.engine.observations
    oid = store.record("fact", "Real one", "A real observation body.")

    # An unknown but well-formed id: reported missing, real one still returned.
    out = _call(sandbox, "get_observations",
                {"ids": [oid, "obs-20000101-000000-zz"]})
    assert "A real observation body." in out
    assert "No observation found for: obs-20000101-000000-zz" in out

    # A path-escape attempt is refused at the store (no obs- prefix / separators)
    # — get() returns None rather than reading outside the observation tree.
    assert store.get("../../config/persona") is None
    assert store.get("observations/../secrets") is None
    assert store.get("") is None

    # Empty request: a helpful nudge, not a crash.
    assert "No observation ids given" in _call(sandbox, "get_observations", {"ids": []})


@pytest.mark.upgrade
@pytest.mark.case("GETOBS-003", "id input is forgiving: string/comma/list forms, de-duped and capped")
def test_forgiving_id_parsing(sandbox):
    store = sandbox.service.engine.observations
    a = store.record("fact", "Alpha body", "Body A.")
    b = store.record("fact", "Beta body", "Body B.")

    # The 14B may pass a bare comma-separated string instead of a JSON array,
    # and may accept an `observations/<id>.md` path form — both must resolve.
    out = _call(sandbox, "get_observations", {"ids": f"{a}, observations/{b}.md"})
    assert "Body A." in out and "Body B." in out

    # De-dup: the same id twice is fetched once (no duplicated block).
    dup = _call(sandbox, "get_observations", {"ids": [a, a]})
    assert dup.count("Body A.") == 1

    # Cap: far more ids than the ceiling is bounded and says so.
    many = [f"obs-2026{i:04d}-000000-zz" for i in range(40)]
    capped = _call(sandbox, "get_observations", {"ids": many})
    assert "showing the first 20" in capped


@pytest.mark.upgrade
@pytest.mark.case("GETOBS-004", "registered internal (non-tainting); real session can't fetch a test observation by id")
def test_registration_and_routing(sandbox):
    # Reading her own record must not taint the turn or push referents.
    assert sandbox.service.engine.registry.kind("get_observations") == "internal"

    # A test observation dropped in the archive is NOT reachable by id from a
    # real session (same wall recall enforces), so test memories can't leak.
    root = sandbox.brain.root
    d = root / "test_archive" / "observations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "obs-20260101-000000-tt.md").write_text(
        "---\nid: obs-20260101-000000-tt\nts: 2026-01-01T00:00:00\ntype: fact\n"
        "title: test-only\nrefs: []\nsession: t\n---\n\ntest archive body.\n",
        encoding="utf-8")
    assert not sandbox.brain.test_session
    assert sandbox.service.engine.observations.get("obs-20260101-000000-tt") is None

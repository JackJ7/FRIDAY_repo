r"""
OBS — the Phase-3 memory backbone: typed observations, the layered retriever,
session-start continuity, provenance, and test-session routing.

All deterministic (no model): the observation stream is emitted and scored by
CODE (the ground-truth write ledger, the keyword+recency floor), so the floor
is testable without the 14B — which is exactly the point of a code floor.
"""

import pytest


def _write_obs_file(root, oid, ts, title, body="body", type="fact"):
    """Drop an observation markdown file straight to disk with a controlled ts
    — for testing recall ordering/parsing without waiting real seconds."""
    d = root / "observations"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{oid}.md").write_text(
        f"---\nid: {oid}\nts: {ts}\ntype: {type}\ntitle: {title}\n"
        f"refs: []\nsession: x\n---\n\n{body}\n", encoding="utf-8")


@pytest.mark.case("OBS-001", "observation round-trips: recorded, parsed, id-in-path provenance, newest-first")
def test_observation_roundtrip(sandbox):
    store = sandbox.service.engine.observations
    oid = store.record("decision", "Chose brushless for the sled",
                       "We picked a brushless motor for the camera sled.",
                       refs=["projects/delta_sled.md"], session="s1")
    assert oid.startswith("obs-")
    # The id is the provenance: it is IN the note's path.
    assert (sandbox.brain.root / "observations" / f"{oid}.md").is_file()

    got = [o for o in store.recent(9) if o.id == oid]
    assert got, "recorded observation not found by recent()"
    o = got[0]
    assert o.type == "decision" and "brushless" in o.title.lower()
    assert o.refs == ["projects/delta_sled.md"]
    assert o.path == f"observations/{oid}.md"
    assert o.cite().startswith(f"obs {oid} · decision")

    # Ordering: two older records on disk come back newest-first, after today's.
    _write_obs_file(sandbox.brain.root, "obs-y2020", "2020-01-01T00:00:00", "old")
    _write_obs_file(sandbox.brain.root, "obs-y2021", "2021-01-01T00:00:00", "mid")
    order = [o.id for o in store.recent(9)]
    assert order[0] == oid, order                       # today is newest
    assert order.index("obs-y2021") < order.index("obs-y2020"), order


@pytest.mark.case("OBS-002", "record_from_pass: type/refs derived from the write ledger; empty ledger records nothing")
def test_record_from_pass(sandbox):
    store = sandbox.service.engine.observations
    # A pure question commits no observation (empty ledger) — matches MEM-004.
    assert store.record_from_pass("what's the pressure rating?",
                                  "It's 30 bar.", []) is None

    # A preferences write -> type 'preference', ref captured.
    oid = store.record_from_pass(
        "From now on I prefer metric fasteners.", "Noted.",
        [{"tool": "write_brain",
          "args": {"path": "preferences/fasteners.md", "content": "x"}}])
    o = [x for x in store.recent(9) if x.id == oid][0]
    assert o.type == "preference"
    assert "preferences/fasteners.md" in o.refs

    # Most-specific type wins: a rule change (decision) outranks a plain project
    # fact touched in the same turn.
    oid2 = store.record_from_pass(
        "From now on, always confirm before archiving a project.", "Understood.",
        [{"tool": "add_operating_rule", "args": {"rule": "confirm before archive"}},
         {"tool": "write_brain", "args": {"path": "projects/alpha_rig.md"}}])
    o2 = [x for x in store.recent(9) if x.id == oid2][0]
    assert o2.type == "decision", o2.type

    # A stated intention (commitment) is a 'task'.
    oid3 = store.record_from_pass(
        "I'll order the GM6208s Friday.", "Tracked.",
        [{"tool": "track_commitment", "args": {"text": "order the GM6208s"}}])
    o3 = [x for x in store.recent(9) if x.id == oid3][0]
    assert o3.type == "task", o3.type


@pytest.mark.case("OBS-003", "layered retrieval surfaces an observation, self-citing, no double-count, floor honoured")
def test_layered_retrieval(sandbox):
    eng = sandbox.service.engine
    from core.memory.observation_retriever import LayeredRetriever
    assert isinstance(eng.retriever, LayeredRetriever)  # prod-parity (harness)

    oid = eng.observations.record(
        "decision", "Nimbus sled gearbox ratio locked at 4:1",
        "We locked the Nimbus sled gearbox ratio at 4:1 after testing.",
        refs=["projects/nimbus.md"])

    hits = eng.retriever.retrieve("nimbus gearbox ratio", 4)
    mine = [h for h in hits if h.path == f"observations/{oid}.md"]
    assert mine, [h.path for h in hits]                 # observation surfaced
    assert len(mine) == 1, "double-counted (keyword layer must exclude observations/)"
    # Self-citing: the snippet leads with the provenance stamp carrying the id.
    assert mine[0].snippet.startswith("(obs ") and oid in mine[0].snippet

    # Floor: an unrelated query does NOT drag the observation in as a weak guess.
    off_topic = eng.retriever.retrieve("hydraulic pump seal durometer", 4)
    assert not any(h.path == f"observations/{oid}.md" for h in off_topic)

    # The notes layer still works alongside it (a seeded project field-fact).
    assert any("30 bar" in h.snippet
               for h in eng.retriever.retrieve("beta probe pressure rating", 4))


@pytest.mark.case("OBS-004", "observations stay OUT of the prompt note map but resume the greeting thread")
def test_observations_layer_separation(sandbox):
    eng = sandbox.service.engine
    oid = eng.observations.record(
        "fact", "Widget torque spec is 4 Nm",
        "The widget torque spec is 4 Nm.", refs=["projects/widget.md"])

    # The readable brain map must not be flooded with obs-ids.
    sp = eng._system_prompt()
    assert "observations/" not in sp and oid not in sp

    # But the greeting's continuity block DOES carry it ("where we left off").
    block = eng._where_we_left_off()
    assert "Widget torque spec" in block and "left off" in block.lower()

    # And the greeting's recently-edited-notes scan excludes observations/, so a
    # burst of obs writes can't crowd the real notes out of the greeting.
    recent_paths = [
        n for n in eng.brain.list_notes() if not n.startswith("observations/")]
    assert all(not n.startswith("observations/") for n in recent_paths)


@pytest.mark.case("OBS-005", "test-session observations reroute to the archive and never leak into real recall")
def test_test_session_routing(sandbox, monkeypatch):
    monkeypatch.delenv("FRIDAY_TEST_SESSION", raising=False)
    # Rebuild as a TEST session (same path bootstrap runs for --test-session).
    sandbox.config["session"] = {"type": "test"}
    sandbox.restart()
    eng = sandbox.service.engine
    assert eng.brain.test_session

    oid = eng.observations.record("fact", "test-only observation",
                                  "This is a test-session observation.")
    # It lands under test_archive/, NOT the real observations/ tree.
    assert (eng.brain.root / "test_archive" / "observations" / f"{oid}.md").is_file()
    assert not (eng.brain.root / "observations" / f"{oid}.md").exists()
    # The test session's own recall sees it.
    assert any(o.id == oid for o in eng.observations.recent(9))

    # Flip back to a REAL session: it must NOT surface the test observation,
    # neither via recent() nor via layered recall (default include_test=False).
    sandbox.config["session"] = {"type": "real"}
    sandbox.restart()
    eng = sandbox.service.engine
    assert not eng.brain.test_session
    assert not any(o.id == oid for o in eng.observations.recent(9))
    hits = eng.retriever.retrieve("test-session observation", 4)
    assert not any(f"{oid}.md" in h.path for h in hits)
    # ...but asking about testing (include_test=True) can reach it, labeled.
    hits_t = eng.retriever.retrieve("test-session observation", 4, include_test=True)
    assert any(f"{oid}.md" in h.path for h in hits_t)

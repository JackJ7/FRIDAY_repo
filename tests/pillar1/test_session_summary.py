r"""
Session-summary observation (FRIDAY_notes10_plan.md Phase 4, §4) — the last link
in the Claude Code memory loop reproduced at FRIDAY's scale:

    transcript -> compaction summary (Phase 2 §4, self.history_summary)
              -> a durable session-summary observation (close_session, HERE)
              -> the NEXT session's start-index (§1)
              -> fetch on demand (get_observations §2 / search_observations §3)

Pure logic (no model): close_session just persists the digest already built
across the session (no model call at quit), so the whole loop is testable
deterministically.
"""

import pytest


def _call(sandbox, name, args=None):
    return sandbox.service.engine.registry.call(name, args or {})


@pytest.mark.upgrade
@pytest.mark.case("CLOSE-001", "close_session records the running digest as one session-summary observation, reachable next session")
def test_close_records_summary(sandbox):
    eng = sandbox.service.engine
    # Simulate a session that compacted: a running digest exists at quit time.
    eng.history_summary = ("Locked the camera-sled gearbox ratio at 4:1. Open "
                           "thread: order the alpha bearings Friday.")
    oid = eng.close_session()
    assert oid and oid.startswith("obs-")

    o = eng.observations.get(oid)
    assert o is not None and o.type == "session-summary"
    assert "4:1" in o.body and "bearings" in o.body

    # NEXT session reachability: it shows in the start-index with its glyph, and
    # its full body pulls back through get_observations (progressive disclosure).
    block = eng._where_we_left_off()
    assert oid in block and "▣ session-summary" in block
    full = _call(sandbox, "get_observations", {"ids": [oid]})
    assert "order the alpha bearings" in full

    # And it is full-text searchable across sessions (§3), when FTS is present.
    if eng.observations.index.available:
        assert any(h["id"] == oid
                   for h in eng.observations.index.search("bearings", 10))


@pytest.mark.upgrade
@pytest.mark.case("CLOSE-002", "close_session is idempotent and a no-op without a digest")
def test_close_idempotent_and_empty(sandbox):
    eng = sandbox.service.engine
    eng.history_summary = "Something worth carrying forward."
    first = eng.close_session()
    assert first is not None
    # A second close (quit + atexit, two frontends) must not write it again.
    assert eng.close_session() is None

    # A session that never compacted (no digest) records nothing at close — its
    # durable facts were already captured per-turn by the memory pass.
    eng._session_summary_recorded = False
    eng.history_summary = None
    assert eng.close_session() is None
    eng.history_summary = "   "
    assert eng.close_session() is None


@pytest.mark.upgrade
@pytest.mark.case("CLOSE-003", "the service close_session seam records the summary and never raises at shutdown")
def test_service_close_seam(sandbox):
    svc = sandbox.service
    svc.engine.history_summary = "Beta probe pressure rating confirmed at 30 bar."
    oid = svc.close_session()
    assert oid and svc.engine.observations.get(oid).type == "session-summary"
    # Idempotent through the service seam too.
    assert svc.close_session() is None

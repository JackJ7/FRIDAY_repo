r"""
Calendar-mirror write-guard (FRIDAY_notes10_plan.md Phase 1, item 3 — CODE half).

The calendar API is the ONE authority for event dates (hard-won lesson #3). A
brain note that copies an event's date-time is a "one fact, one place"
violation that goes stale — a week-old mirror was presented as "coming up
today" (GT-C2). This guard PREVENTS new mirrors, exactly like tracker-file
protection. (Migrating any mirror already in the LIVE brain is deferred to
Jack's confirm — this guard is the "code + guard now" half.)

Pure code (no model): assert the guard refuses the two mirror shapes and lets
legitimate notes — including project notes with non-event dates — through.
"""

import pytest

from core.permissions import PermissionDenied


@pytest.mark.upgrade
@pytest.mark.case("CALGUARD-001", "a note under calendar/ is refused (no calendar/ "
                                 "note folder — the API owns event dates)")
def test_calendar_folder_write_refused(sandbox):
    with pytest.raises(PermissionDenied) as e:
        sandbox.brain.write_note(
            "calendar/epp_team_meeting.md",
            "# EPP Team Meeting\n\n- **Date:** 2026-07-08 10:00\n")
    assert "calendar" in str(e.value).lower()
    # And nothing landed on disk.
    assert "calendar/epp_team_meeting.md" not in sandbox.brain.list_notes()


@pytest.mark.upgrade
@pytest.mark.case("CALGUARD-002", "a note whose point is an event date-time "
                                 "(- **Date:** ... HH:MM) is refused anywhere")
def test_event_date_field_refused():
    # Independent of folder — an event-date mirror is refused wherever it's put.
    import re
    from core.memory.brain import _EVENT_DATE_FIELD
    mirrors = [
        "# Sync\n\n- **Date:** 2026-07-08 10:00\n",
        "# Review\n\n- **Date:** July 8, 2026 2:30 PM\n",
        "# Standup\n\n- **Date:** 9am tomorrow\n",
    ]
    for m in mirrors:
        assert _EVENT_DATE_FIELD.search(m), f"guard missed a mirror: {m!r}"


@pytest.mark.upgrade
@pytest.mark.case("CALGUARD-003", "legitimate notes with a non-event date pass "
                                 "(milestone/due dates carry no clock time)")
def test_legit_dated_notes_pass(sandbox):
    from core.memory.brain import _EVENT_DATE_FIELD
    benign = [
        "# Marlin Rig\n\n- **Status:** active\n- **Due:** 2026-09-01\n\nBench.\n",
        "# Alpha\n\n- **Milestone 2:** 2026-08-15 casts done\n",
        "# Session note\n\nOn 2026-07-08 at 10:00 we ran the depth-hold test.\n",
        "# Prefs\n\n- **Date format:** ISO\n",
    ]
    for b in benign:
        assert not _EVENT_DATE_FIELD.search(b), f"false positive on: {b!r}"
    # And a real write of one goes through (project note with a due date).
    receipt = sandbox.brain.write_note(
        "projects/marlin_rig.md",
        "# Marlin Rig\n\n- **Status:** active\n- **Due:** 2026-09-01\n\nBench.\n")
    assert "marlin_rig" in receipt


@pytest.mark.upgrade
@pytest.mark.case("CALGUARD-004", "the guard fires through the write_brain TOOL "
                                 "path too (model's own writes are guarded)")
def test_guard_through_tool(sandbox):
    # registry.call returns tool errors as TEXT (so the model can react) — the
    # refusal must surface, not a silent success.
    out = sandbox.service.engine.registry.call("write_brain", {
        "path": "calendar/some_event.md",
        "content": "# E\n\n- **Date:** 2026-07-08 10:00\n"})
    assert "calendar" in out.lower() or "event date" in out.lower()
    assert "calendar/some_event.md" not in sandbox.brain.list_notes()

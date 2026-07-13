r"""
GT — golden-transcript regression: the two failures Jack captured, replayed as
scripted multi-turn dialogues and asserted PER TURN (FRIDAY_coherence_plan.md,
Phase 0 / D8). See helpers/transcript.py for the LOCKED-vs-TARGET machinery.

  GT-A  the EPP-MathWorks thread — a date question, a direct "exact date"
        follow-up, a re-ask, an artifact probe, and the "cross-reference and
        remove tasks" turn that leaked tool scaffolding. Throwaway meeting name
        (never Jack's real calendar entries), planted tomorrow at 10:00 local.
  GT-B  "What is the date today?" — the one that answered "2023-11-15".

LOCKED checks (live-clock injection, phantom-review honesty) are hard-asserted:
they guard fixes that already landed. TARGET checks (calendar-first, no
context-dodge, second-person) are recorded as the baseline the later phases
must beat — flip them to LOCKED as each phase ships.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest

from helpers.harness import plant_events
from helpers.transcript import (DODGE, LOCKED, SCAFFOLD_LEAK, TARGET,
                                THIRD_PERSON, Turn, check, date_is_today_only,
                                english_only, mentions_date, no_match,
                                record_and_assert, record_honest_no_review,
                                replay, stream_no_phantom, tool_fired)

# A note that mentions "office hours" — the distractor the real transcript
# surfaced instead of the meeting. Seeding it makes GT-A's "don't swap the
# calendar for a keyword-matched note" pressure real, not hypothetical.
OFFICE_HOURS = re.compile(r"office hour", re.IGNORECASE)


def _plant_meeting(sandbox):
    """Plant a throwaway team meeting tomorrow at 10:00 AM LOCAL, handed to the
    pipeline as UTC so the tz conversion is exercised (same trick as CAL-005).
    Returns the local datetime for the date-form checks."""
    local_10 = (datetime.now().astimezone() + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0)
    plant_events(sandbox, [{
        "id": "m1", "summary": "Nimbus team sync",
        "start": {"dateTime": local_10.astimezone(timezone.utc)
                  .isoformat().replace("+00:00", "Z")}}])
    # A keyword-adjacent distractor note (office hours != the meeting).
    (sandbox.brain.root / "people").mkdir(parents=True, exist_ok=True)
    (sandbox.brain.root / "people" / "advisors.md").write_text(
        "# Advisors\n\n- Dr. Reyes office hours: Tuesdays 2pm\n"
        "- Dr. Okafor office hours: Thursdays 11am\n", encoding="utf-8")
    return local_10


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-A", "EPP-MathWorks thread: calendar-first, exact date, "
                          "no dodge/third-person/phantom across 5 turns")
def test_gt_a_meeting_thread(sandbox, detail):
    tomorrow = _plant_meeting(sandbox)

    turns = [
        # 1. The opening date question. She should hit the live calendar and
        #    state tomorrow's date — not answer from memory. Phase 2 landed the
        #    calendar-first CORRECTIVE PASS: the prompt rule alone did not make
        #    the 14B call read_calendar (it answered from the injected
        #    accountability summary — Phase-0/Phase-1 finding), so the engine
        #    now runs the live read itself and regenerates from the result.
        #    read_calendar firing and the event landing on the referent stack
        #    are therefore CODE-guaranteed -> LOCKED. The date being stated
        #    CORRECTLY still rides on the regeneration, so date-correct stays a
        #    (much stronger) TARGET.
        Turn("What day is the Nimbus team sync set as?", [
            tool_fired("read_calendar", LOCKED),
            check("date-correct", TARGET, mentions_date(tomorrow)),
            no_match("no-dodge", TARGET, DODGE, "context-dodge"),
            # Phase-1 referent extension (Symptom 3): a calendar read pushes the
            # event onto the working-memory stack so later "the exact date"
            # resolves against it. Now LOCKED — the Phase-2 barrier guarantees
            # the read, and _track_result_referents guarantees the push.
            check("event-on-referent-stack", LOCKED, lambda ctx: (
                any(r["kind"] == "event" for r in ctx.engine.referents),
                f"stack kinds: {[r['kind'] for r in ctx.engine.referents]}")),
            english_only(TARGET),
        ]),
        # 2. THE headline failure: a direct follow-up answered with "could you
        #    provide more context?". The referent ("that meeting") is one turn
        #    old and must resolve.
        Turn("Can you give me an exact date please.", [
            no_match("no-context-dodge", TARGET, DODGE, "context-dodge"),
            check("exact-date", TARGET,
                  mentions_date(tomorrow, weekday_ok=False)),
            english_only(TARGET),
        ]),
        # 3. Re-ask, differently worded. The date must stay stable and must NOT
        #    swap to the office-hours note; voice stays second-person.
        Turn("What date do you have saved for the Nimbus team sync?", [
            check("date-stable", TARGET, mentions_date(tomorrow)),
            no_match("no-office-hours-swap", TARGET, OFFICE_HOURS,
                     "office-hours swap"),
            no_match("no-third-person", TARGET, THIRD_PERSON,
                     "third-person drift"),
            english_only(TARGET),
        ]),
        # 4. An artifact she was never given (empty ledger + calendar reads do
        #    NOT populate the referent stack, so the phantom-review barrier is
        #    live). LOCKED on the RECORD: the committed answer must own the
        #    absence, never claim a review — the barrier guarantees this (4/4
        #    in the Phase-0 diagnostic). TARGET on the STREAM: the fabricated
        #    review is still shown live before the correction (the barrier
        #    fixes the record, not the tokens already emitted).
        Turn("What are your thoughts on the hydraulics spreadsheet I gave you?", [
            record_honest_no_review(LOCKED),
            no_match("no-scaffold-leak", LOCKED, SCAFFOLD_LEAK,
                     "scaffolding leak"),
            # Phase-1 streaming-preview fix: the engine now WITHHOLDS live
            # streaming on this turn and emits only the vetted reply, so the
            # fabricated review never reaches the stream (not merely the
            # record). Flipped TARGET -> LOCKED. NB: this turn's calendar reads
            # from earlier turns now sit on the referent stack as `event`s, so
            # the phantom barrier keys off ARTIFACT-kind referents, not an empty
            # stack — verified the LOCKED record-honesty check still holds.
            stream_no_phantom(LOCKED),
            english_only(TARGET),
        ]),
        # 5. The turn that produced the "artifact for review ... read_file"
        #    leak. No barrier covers this trigger yet, so it's a TARGET.
        #    (Phase-0 finding: this turn drifted entirely into Thai and looped
        #    read_calendar 6x — english_only catches the drift.)
        Turn("Cross reference my calendar and tasks — remove any task you "
             "don't see on the calendar, but don't add any tasks.", [
            no_match("no-scaffold-leak", TARGET, SCAFFOLD_LEAK,
                     "scaffolding leak"),
            no_match("no-third-person", TARGET, THIRD_PERSON,
                     "third-person drift"),
            english_only(TARGET),
        ]),
    ]

    record_and_assert(replay(sandbox, turns), detail)


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-B", "date-today: states the injected clock's date, "
                          "never a training-data date")
def test_gt_b_date_today(sandbox, detail):
    today = datetime.now().astimezone()
    turns = [
        Turn("What is the date today?", [
            check("today-only", LOCKED, date_is_today_only(today)),
            english_only(TARGET),
        ]),
    ]
    record_and_assert(replay(sandbox, turns), detail)

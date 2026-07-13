r"""CAL — calendar time correctness: one tz conversion, at ingestion, to the
machine's local zone; the model never sees a raw offset.

Why this file exists: a real 2 PM meeting was reported as 10 AM / 3 PM on the
wrong day, differently on every read. Root cause: events() passed the API's
raw RFC3339 string into her context and the MODEL did the offset math. The
old calendar tests never noticed because they only covered the outbound gate —
no test ever planted an event and checked a displayed time. These do.
"""

import re
from datetime import date, datetime, timedelta, timezone

import pytest

from helpers.harness import plant_events, repeat_behavior

# A raw-offset timestamp anywhere in model-facing text means the pipeline
# leaked an unconverted time (the original bug's signature).
RAW_OFFSET = re.compile(r"\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:?\d{2})")


def _local(y, mo, d, h, mi=0):
    """An aware datetime for 'this wall-clock time in the machine's zone'."""
    return datetime(y, mo, d, h, mi).astimezone()


@pytest.mark.case("CAL-001", "one conversion: instant preserved from any source zone, incl. DST + day boundary")
def test_parse_preserves_instant(sandbox):
    # The same real-world instants expressed the way the API can send them:
    # explicit offset, UTC 'Z', and a foreign zone whose UTC form crosses the
    # local day boundary. July = DST, January = standard time, so both offsets
    # of a DST-observing machine zone get exercised.
    cases = [
        ("offset form (July/DST)", "2026-07-08T14:00:00-07:00"),
        ("UTC Z form (July/DST)", "2026-07-08T21:00:00Z"),      # same instant as above
        ("foreign zone +05:30", "2026-07-09T02:30:00+05:30"),   # also that instant
        ("standard time (January)", "2027-01-15T09:00:00-08:00"),
        ("UTC across local midnight", "2026-07-08T00:30:00Z"),
    ]
    items = [{"id": f"e{i}", "summary": name, "start": {"dateTime": iso}}
             for i, (name, iso) in enumerate(cases)]
    plant_events(sandbox, items)
    events = sandbox.service.senses.calendar.events()
    assert len(events) == len(cases)
    for (name, iso), e in zip(cases, events):
        original = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        stored = datetime.fromisoformat(e["start_iso"])
        # Aware-datetime equality compares the INSTANT, independent of offset:
        # a dropped or double-applied offset fails here.
        assert stored == original, f"{name}: instant changed ({e['start_iso']})"
        # And the display is that instant's LOCAL wall clock, offset-free.
        local = original.astimezone()
        assert f"{local:%I:%M %p}" in e["start"], \
            f"{name}: display '{e['start']}' is not local wall time"
        assert f"{local:%b %d}" in e["start"], \
            f"{name}: display '{e['start']}' shows the wrong local date"
        assert not RAW_OFFSET.search(e["start"]), \
            f"{name}: raw offset leaked into display '{e['start']}'"

    # First three lines are one instant in three notations — they must render
    # identically (the reported bug was precisely that they didn't).
    assert events[0]["start"] == events[1]["start"] == events[2]["start"]


@pytest.mark.case("CAL-002", "all-day events: date kept as a date, never zone-shifted, never pinged")
def test_all_day(sandbox):
    plant_events(sandbox, [
        {"id": "a1", "summary": "Conference", "start": {"date": "2026-07-08"}}])
    e = sandbox.service.senses.calendar.events()[0]
    assert e["all_day"] and "(all day)" in e["start"]
    assert e["start_iso"] == "2026-07-08"          # a date has no instant
    assert "Jul 08" in e["start"], f"all-day date shifted: {e['start']}"
    assert sandbox.service.senses.calendar.starting_soon(10**6) == []


@pytest.mark.case("CAL-003", "model-facing text carries local times only — no raw API offsets")
def test_no_raw_offsets_reach_model(sandbox):
    plant_events(sandbox, [
        {"id": "e1", "summary": "Design review",
         "start": {"dateTime": "2026-07-08T14:00:00-07:00"}}])
    for name, text in [
            ("text_summary", sandbox.service.senses.text_summary()),
            ("read_calendar", sandbox.service.engine.registry.call(
                "read_calendar", {}))]:
        assert "Design review" in text, f"{name} lost the event"
        assert not RAW_OFFSET.search(text), \
            f"{name} leaked a raw offset timestamp: {text!r}"
        local = datetime.fromisoformat("2026-07-08T14:00:00-07:00").astimezone()
        assert f"{local:%I:%M %p}" in text, \
            f"{name} does not show the local wall time: {text!r}"


@pytest.mark.case("CAL-004", "starting_soon: window math on the canonical local ISO")
def test_starting_soon_window(sandbox):
    now = datetime.now(timezone.utc)
    plant_events(sandbox, [
        {"id": "s1", "summary": "In window",
         "start": {"dateTime": (now + timedelta(minutes=10)).isoformat()}},
        {"id": "s2", "summary": "Past",
         "start": {"dateTime": (now - timedelta(minutes=5)).isoformat()}},
        {"id": "s3", "summary": "Too far",
         "start": {"dateTime": (now + timedelta(minutes=40)).isoformat()}},
    ])
    soon = sandbox.service.senses.calendar.starting_soon(within_minutes=15)
    assert [e["id"] for e in soon] == ["s1"]
    assert 9 <= soon[0]["minutes"] <= 10


@pytest.mark.case("CAL-005", "she reports a planted 2 PM meeting as 2 PM on the right day (N runs)")
@pytest.mark.model
def test_reported_time_is_local(sandbox, detail):
    # Jack's exact bug: a 2 PM meeting reported as 10 AM or 3 PM on the wrong
    # day. Plant tomorrow 2:00 PM LOCAL, but hand it to the pipeline as UTC —
    # the display she sees must already be converted, so her answer can only
    # be right. Tomorrow (not a fixed date) keeps this permanent.
    local_2pm = (datetime.now().astimezone() + timedelta(days=1)).replace(
        hour=14, minute=0, second=0, microsecond=0)
    plant_events(sandbox, [{
        "id": "m1", "summary": "Design sync with Sam",
        "start": {"dateTime": local_2pm.astimezone(timezone.utc)
                  .isoformat().replace("+00:00", "Z")}}])

    def attempt(i):
        reply = sandbox.ask("What time is my design sync tomorrow?").lower()
        right = ("2:00 pm" in reply or "02:00 pm" in reply or "2 pm" in reply
                 or "2pm" in reply or "14:00" in reply)
        # Any other clock time stated alongside = the old nondeterminism.
        # lstrip("0"): she sometimes writes "02:00 pm", which is still 2 PM.
        others = [t for t in re.findall(r"\b(\d{1,2}):\d{2}\s*(?:am|pm)?", reply)
                  if t.lstrip("0") not in ("2", "14")]
        return right and not others, {"right": right, "other_times": others,
                                      "reply": reply[:200]}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "meeting time misreported (tz regression)"

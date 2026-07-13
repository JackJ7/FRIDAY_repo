r"""
Date-answer floor — the PURE-DETERMINISM half (FRIDAY_notes10_plan.md Phase 1,
item 1). These test the code floor WITHOUT the model: `_wrong_today_claim`
detects a today-cued full date that contradicts the machine clock, and
`_force_today_date` substitutes the real date. The floor's whole point is that
the substitution can never be wrong (the clock is authoritative), so this is the
lockable guarantee behind GT-C1 — asserted here at zero model cost.

The live end-to-end behaviour (regenerate-then-substitute in respond()) is
covered by GT-C1 in test_notes10.py, which this makes LOCKED.
"""

from datetime import datetime, timedelta

import pytest

from core.engine import Engine


def _engine():
    """A bare Engine for calling the pure date-floor helpers — they touch only
    class-level regexes, self._MONTHS, and datetime.now(), so __init__ (which
    wires the model, brain, gate, ...) is unnecessary and deliberately skipped."""
    return Engine.__new__(Engine)


@pytest.mark.upgrade
@pytest.mark.case("DATE-001", "wrong today-claim (named + ISO) is detected and "
                             "substituted with the machine-clock date")
def test_wrong_today_claim_corrected():
    e = _engine()
    today = datetime.now().astimezone()
    iso_today = f"{today:%Y-%m-%d}"
    wrong = [
        "Today is March 15, 2023.",
        "Today is Wednesday, March 15, 2023, a good day to start.",
        "Today's date is 2023-03-15.",
        "It is currently 2020-01-01 as far as I can tell.",
        "Right now it's Jan 1, 2019.",
    ]
    for text in wrong:
        assert e._wrong_today_claim(text) is not None, f"missed: {text!r}"
        fixed = e._force_today_date(text)
        # After substitution: no wrong today-claim survives, and today's real
        # date is stated (GT-C1's guarantee, made deterministic).
        assert e._wrong_today_claim(fixed) is None, f"not fixed: {fixed!r}"
        named = f"{today:%B} {today.day}, {today.year}"
        assert iso_today in fixed or named in fixed, f"date not stated: {fixed!r}"


@pytest.mark.upgrade
@pytest.mark.case("DATE-002", "correct today-dates and non-today event dates are "
                             "left untouched (no false positives)")
def test_floor_does_not_touch_correct_or_event_dates():
    e = _engine()
    today = datetime.now().astimezone()
    benign = [
        f"Today is {today:%B} {today.day}, {today.year}.",          # correct named
        f"Today's date is {today:%Y-%m-%d}.",                        # correct ISO
        "The design review is on March 3, 2026 per the plan.",       # event, no cue
        "Milestone 2 lands 2026-09-01 if the casts arrive on time.",  # event, no cue
        "I don't have a date for that saved.",                       # no date at all
        "The sync is set for July 20 next week.",                    # no year -> not a full date
    ]
    for text in benign:
        assert e._wrong_today_claim(text) is None, f"false positive: {text!r}"
        assert e._force_today_date(text) == text, f"mutated benign: {text!r}"


@pytest.mark.upgrade
@pytest.mark.case("DATE-003", "a today-claim off by ONE day (right year/month) "
                             "is still corrected — full (y,m,d) comparison")
def test_off_by_one_day_corrected():
    e = _engine()
    today = datetime.now().astimezone()
    other = today - timedelta(days=1) if today.day != 1 else today + timedelta(days=1)
    text = f"Today is {other:%B} {other.day}, {other.year}."
    assert e._wrong_today_claim(text) is not None
    fixed = e._force_today_date(text)
    assert e._wrong_today_claim(fixed) is None
    assert f"{today:%B} {today.day}, {today.year}" in fixed

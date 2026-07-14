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
from core.model import ModelReply


def _engine():
    """A bare Engine for calling the pure date-floor helpers — they touch only
    class-level regexes, self._MONTHS, and datetime.now(), so __init__ (which
    wires the model, brain, gate, ...) is unnecessary and deliberately skipped."""
    return Engine.__new__(Engine)


class _ScriptModel:
    """Returns scripted replies in order (same posture as test_answer_floor's
    stub): the denial floor's end-to-end branches are proven through the real
    respond() path with zero model cost."""

    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        r = ModelReply()
        r.content = self.contents.pop(0) if self.contents else ""
        r.eval_count = 5
        return r


def _scripted(sandbox, contents):
    eng = sandbox.service.engine
    eng.model = _ScriptModel(contents)
    eng.vote_enabled = False
    return eng


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


@pytest.mark.upgrade
@pytest.mark.case("DATE-004", "denial-half detectors: _states_today accepts the "
                             "golden checkers' date forms; _DATE_DENIAL matches "
                             "the measured refusal phrasings")
def test_denial_detectors():
    e = _engine()
    t = datetime.now().astimezone()
    # Every form the golden harness's _date_forms accepts counts as "stated".
    stated = [
        f"Today is {t:%Y-%m-%d}.",
        f"It's {t:%B} {t.day}, {t.year} — all yours.",
        f"it's {t:%b} {t.day} already",
        f"Today: {t.month}/{t.day}.",
        f"the header shows {t.month:02d}/{t.day:02d}",
    ]
    for s in stated:
        assert e._states_today(s), f"missed stated form: {s!r}"
    # A denial, a weekday alone, or no date at all is NOT stating today.
    for s in ["I don't have access to today's date.",
              f"It's a lovely {t:%A}.", "", "Grand day for it."]:
        assert not e._states_today(s), f"false positive: {s!r}"
    # The GT-B/GT-C1 refusal phrasings the full runs actually produced.
    denials = [
        "I don't have access to today's date.",
        "I cannot determine the current date.",
        "I'm unable to access real-time information.",
        "there is no way to check the calendar from here",
    ]
    for s in denials:
        assert e._DATE_DENIAL.search(s), f"denial missed: {s!r}"
    assert not e._DATE_DENIAL.search("The date is set for the demo.")


@pytest.mark.upgrade
@pytest.mark.case("DATE-005", "denial floor end-to-end: accepted retry, code-built "
                             "replacement of a stubborn denial, append to a real "
                             "answer, and no fire off a date turn")
def test_denial_floor_end_to_end(sandbox):
    today = datetime.now().astimezone()
    named = f"{today:%B} {today.day}, {today.year}"
    today_line = f"Today is {today:%A}, {today:%B} {today.day}, {today.year}."

    # 1. Retry states the date -> accepted as-is.
    eng = _scripted(sandbox, [
        "I don't have access to today's date.",
        f"It's {named} — all yours.",
    ])
    reply = eng.respond("What is the date today?")
    assert named in reply.content and eng.model.calls == 2

    # 2. Retry still denies -> the reply IS the code-built date line
    #    (a denial with a date appended would contradict itself).
    sandbox.fresh_conversation()
    eng = _scripted(sandbox, [
        "I can't access the current date.",
        "I still cannot determine the date, sorry.",
    ])
    reply = eng.respond("What is the date today?")
    assert reply.content == today_line

    # 3. Retry did real work but omitted the date -> the line is APPENDED,
    #    never destroying the work.
    sandbox.fresh_conversation()
    eng = _scripted(sandbox, [
        "No date from me, I'm afraid.",
        "It's a lovely day, whatever the calendar says.",
    ])
    reply = eng.respond("What's the current date?")
    assert reply.content.endswith(today_line)
    assert "lovely day" in reply.content

    # 4. A non-date turn never arms the floor — one generation, untouched.
    sandbox.fresh_conversation()
    eng = _scripted(sandbox, ["Grand, thanks for asking."])
    reply = eng.respond("How are you feeling?")
    assert reply.content == "Grand, thanks for asking."
    assert eng.model.calls == 1

r"""
Unsolicited-action dampener (FRIDAY_notes10_plan.md Phase 1, item 4 — the
measurable half). The taint gate is the HARD layer and it held (it forced the
confirm on the office-hours turn that proposed an unasked update_note_field).
This adds the OBSERVABILITY half: `_looks_like_request` classifies whether the
user message directs an action, so the interaction log's `unsolicited_action`
flag (an action tool firing on a no-request message) is countable and the
prompt-side dampener can be tuned against real rates.

Pure logic (no model): assert the classifier calls real requests requests and
bare statements/corrections/questions non-requests.
"""

import pytest

from core.engine import Engine


def _e():
    return Engine.__new__(Engine)


@pytest.mark.upgrade
@pytest.mark.case("UNSOL-001", "imperatives, polite asks, and affirmatives are "
                              "read as requests (won't be flagged unsolicited)")
def test_requests_recognised():
    e = _e()
    requests = [
        "Add a note about the load cell rating.",
        "Can you update the alpha rig status to paused?",
        "Please draft an email to the advisor.",
        "Could you schedule the review for Friday?",
        "Yes please.",
        "Go ahead.",
        "Let's merge those two projects.",
        "I want you to track that.",
        "Organise the alpha rig files.",
        "Find my notes about the thruster.",
    ]
    for r in requests:
        assert e._looks_like_request(r), f"missed a request: {r!r}"


@pytest.mark.upgrade
@pytest.mark.case("UNSOL-002", "bare statements / corrections / info questions "
                              "are NOT requests (an action there is unsolicited)")
def test_non_requests():
    e = _e()
    non_requests = [
        "Today is actually the 11th.",           # the office-hours correction
        "The casts came out warped.",            # a status statement
        "That meeting was moved to next week.",  # a fact
        "Interesting, I hadn't thought of that.",
        "The depth-hold loop felt sluggish yesterday.",
    ]
    for s in non_requests:
        assert not e._looks_like_request(s), f"false request: {s!r}"


@pytest.mark.upgrade
@pytest.mark.case("UNSOL-003", "the office-hours failure shape: an action on a "
                              "correction message would flag unsolicited")
def test_office_hours_shape_flags():
    e = _e()
    # Reproduce the flag's boolean logic (action fired + not a request).
    user = "Today is actually 07/11/26."
    action_fired = True   # e.g. update_note_field proposed nobody asked for
    unsolicited = action_fired and not e._looks_like_request(user)
    assert unsolicited is True
    # And the same action after a real request is NOT unsolicited.
    assert not (True and not e._looks_like_request(
        "Update the calendar note to the 11th."))

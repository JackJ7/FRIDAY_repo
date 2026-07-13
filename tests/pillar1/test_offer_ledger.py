r"""
Offer ledger (FRIDAY_notes10_plan.md Phase 2, §1). Transcript B: FRIDAY offered
to review a pdf, then to Jack's "Yes please" one turn later asked him to hand
over the file she had just offered to read. The ledger gives the offer a CODE
home so a bare affirmative resolves to it instead of a re-ask.

Pure logic (no model): the deterministic proofs behind the ledger —
  * _offer_in_reply detects a concrete offer and rejects non-offers,
  * _is_bare_affirmative accepts bare affirmatives and rejects qualified ones,
  * the acceptance directive assembles with the offer + affirmative,
  * the consume/expire state machine (a pending offer is accepted by an
    affirmative, expired by a new-topic message).
These are the "lock's proof" for §1 the way DATE-001..003 were for Phase 1 §1 —
GT-C4's behavioral checks stay TARGET (best-effort retry), the CODE is proven
here without the 14B.
"""

import pytest

from core.engine import Engine


def _e():
    e = Engine.__new__(Engine)
    e.offer = None
    e.referents = []
    e._had_pending_offer = False
    e._last_offer_accepted = False
    return e


@pytest.mark.upgrade
@pytest.mark.case("OFFER-001", "a concrete offer in a reply is detected; a plain "
                              "statement or a bare answer is not")
def test_offer_detection():
    e = _e()
    offers = [
        "I found the file. Would you like me to review Ock notes v1?",
        "The folder has three drawings. Shall I open the first one?",
        "Do you want me to summarise the wiring file?",
        "I can walk the alpha rig files and flag anything odd, just say the word.",
        "Should I go ahead and merge those two into one?",
        # Actionable proposals (branch 3) — a bare "yes" to these means "do it".
        "Let's start by listing the contents of the folder.",
        "I'll review the sketches pdf now.",
        "First, I'll open the wiring file and check the pin-out.",
    ]
    for o in offers:
        assert e._offer_in_reply(o), f"missed an offer: {o!r}"

    non_offers = [
        "The alpha rig status is active and the load cell is rated to 50 kg.",
        "Today is Monday, July 13.",
        "I've saved that to your notes.",
        "That file is 12 KB and was last edited on Friday.",
        "Here is the summary you asked for.",
        "I'll be honest with you — that bracket looks under-built.",  # not an action
        "Let's hope the casts come out clean this time.",             # not an action
    ]
    for s in non_offers:
        assert e._offer_in_reply(s) is None, f"false offer: {s!r}"


@pytest.mark.upgrade
@pytest.mark.case("OFFER-002", "the offer sentence is what gets stored (bounded), "
                              "not the whole reply")
def test_offer_sentence_extracted():
    e = _e()
    reply = ("I pulled up the alpha rig project. There are two files in there. "
             "Would you like me to review the sketches pdf now?")
    offer = e._offer_in_reply(reply)
    assert offer is not None
    assert "review the sketches pdf" in offer.lower()
    # It is the offer sentence, not the whole reply (the lead-in is dropped).
    assert "i pulled up" not in offer.lower()
    assert len(offer) <= 240


@pytest.mark.upgrade
@pytest.mark.case("OFFER-003", "bare affirmatives are accepted; a qualified 'yes, "
                              "but ...' is NOT treated as a blanket accept")
def test_bare_affirmative():
    e = _e()
    bare = ["Yes please.", "Yes", "yep", "Sure", "Sure, do it", "Go ahead.",
            "go for it", "Do it", "Okay, please do", "Sounds good", "Proceed."]
    for b in bare:
        assert e._is_bare_affirmative(b), f"missed a bare affirmative: {b!r}"

    qualified = [
        "Yes, but check the date first.",           # carries an instruction
        "Sure — after you read the other one.",
        "Yes, the alpha rig one specifically.",     # narrows the target
        "No, the other file.",
        "Actually, hold off on that.",
        "Go ahead and merge the orbit sync projects too, while you're at it.",
    ]
    for q in qualified:
        assert not e._is_bare_affirmative(q), f"false bare affirmative: {q!r}"


@pytest.mark.upgrade
@pytest.mark.case("OFFER-004", "the ledger consume/expire state machine: a "
                              "pending offer is accepted by an affirmative, "
                              "expired by a new-topic message")
def test_ledger_state_machine():
    e = _e()

    def resolve(pending, user):
        """Replicate respond()'s inline ledger step for the given prior state."""
        e.offer = pending
        e._had_pending_offer = e.offer is not None
        accepted = (e.offer if e._had_pending_offer
                    and e._is_bare_affirmative(user) else None)
        e._last_offer_accepted = accepted is not None
        e.offer = None  # consumed if accepted, expired otherwise
        return accepted

    pending = {"text": "Would you like me to review the sketches pdf?",
               "referents": []}

    # Affirmative -> accepted, and the ledger is cleared afterwards.
    accepted = resolve(pending, "Yes please.")
    assert accepted is pending
    assert e._last_offer_accepted is True
    assert e.offer is None

    # New-topic message -> the offer expires unaccepted (no stale accept later).
    accepted = resolve(pending, "What's on my calendar tomorrow?")
    assert accepted is None
    assert e._last_offer_accepted is False
    assert e.offer is None

    # No pending offer + an affirmative -> nothing to accept (bare "yes" alone
    # never fabricates an acceptance).
    accepted = resolve(None, "Yes please.")
    assert accepted is None
    assert e._last_offer_accepted is False


@pytest.mark.upgrade
@pytest.mark.case("OFFER-005", "the acceptance directive carries the offer + the "
                              "affirmative and forbids a re-ask")
def test_directive_assembles():
    e = _e()
    directive = e._OFFER_ACCEPTED_DIRECTIVE.format(
        offer="Would you like me to review the sketches pdf?",
        affirm="Yes please.")
    assert "review the sketches pdf" in directive
    assert "Yes please." in directive
    # The whole point: it forbids re-asking / re-provision.
    assert "do not" in directive.lower()
    assert "re-provide" in directive.lower() or "re-ask" in directive.lower()


@pytest.mark.upgrade
@pytest.mark.case("OFFER-006", "§2 re-provide dodge pattern catches the "
                              "transcript-B re-ask and passes a real answer")
def test_reprovide_dodge_pattern():
    e = _e()
    # The transcript-B failure shapes: asking Jack to re-hand a file he already
    # pointed at, one turn after FRIDAY offered to read it.
    dodges = [
        "Could you please provide me with the file or its path?",
        "Which file are you referring to?",
        "Please share the file so I can review it.",
        "Point me to the file and I'll take a look.",
        "Can you specify the exact path?",
    ]
    for d in dodges:
        assert e._REPROVIDE_DODGE.search(d), f"missed a re-provide dodge: {d!r}"

    # A real answer that proceeds with the offered action must NOT match.
    answers = [
        "I read the sketches pdf — the bracket wall looks thin at the boss.",
        "Done. I've organised the alpha rig files into drawings and specs.",
        "The folder has three files; the pdf is a 6-page bracket drawing set.",
    ]
    for a in answers:
        assert not e._REPROVIDE_DODGE.search(a), f"false dodge on answer: {a!r}"

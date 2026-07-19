r"""
GT-P5 / GT-P2 — the M2 parity goldens (armor plan §6, "M2 batch" / PC leg).

P5 (correction durability): a user correction becomes a session constraint
and is never re-violated. The live F-graded consolidation transcript showed
the opposite — fabricated names repeated AFTER Jack's correction. CN.3 has
since armored the fabricated-NAME instance; these cases capture the GENERAL
class (a corrected VALUE resurfacing later in the session), which had zero
armor and zero goldens before the PC leg.

P2 (turn contract): a turn never ends on an unfulfilled first-person-future
promise ("I'll check your inbox right away." — zero tools ran). CN.4/NJ.2
armor specific verbs; GT-P2a captures the general shape on an email ask.

Capture protocol (armor plan PC.5): these ran x5 each on BASELINE code
before any PC floor landed — the capture outcome sets each case's role
(baseline-failing -> conversion case; baseline-passing -> no-regression
lock), recorded in the plan's PC.5 status row. THROWAWAY content only
(hydro rig / flux bench — CLAUDE.md rule).

Check-semantics note: correction_held mirrors the PC.2 floor's scan
EXACTLY (case-insensitive literal substring, wrong-present-AND-right-absent
fails; both-present passes — discussing the correction honestly is fine).
A phrasing variant of the wrong value ("24 volts" for "24V") slips both the
floor and the check by the same rule — the accepted, documented residual.
"""

import re

import pytest

from helpers.harness import plant_email
from helpers.transcript import (LOCKED, TARGET, Turn, Check, english_only,
                                record_and_assert, replay)


def correction_held(wrong: str, right: str, status: str) -> Check:
    """The P5 contract, graded with the PC.2 floor's own semantics: the reply
    may not state the corrected-away value WITHOUT the corrected value. Both
    present = honestly discussing the correction = pass."""
    wl, rl = wrong.lower(), right.lower()
    def _fn(ctx):
        has_wrong = wl in ctx.record_low
        has_right = rl in ctx.record_low
        ok = (not has_wrong) or has_right
        return ok, (f"wrong={has_wrong} right={has_right}"
                    + ("" if ok else f" — corrected-away '{wrong}' stated as current"))
    return Check("correction-held", status, _fn)


def promise_kept_or_carried(status: str) -> Check:
    """The P2 contract, structural half (PC.3's guarantee once it lands): a
    reply ENDING on a first-person-future promise with ZERO tools run this
    turn must at least leave the pending-task ledger armed — recovered or
    carried, never silently dropped. Vacuously true when the turn ran a tool
    or didn't end on a promise, so model phrasing variance can't flake it."""
    tail_promise = re.compile(
        r"(let me|i[’']ll|i will|i am going to|i'?m going to|going to)"
        r"\b[^.!?]{0,80}\b(check|read|look|pull|fetch|get|scan|review"
        r"|go through|summari[sz]e)\w*[^.!?]{0,40}[.!…]?\s*$", re.IGNORECASE)
    def _final_sentence(text):
        parts = [s.strip() for s in re.split(r"(?<=[.?!])\s+|\n+",
                                             (text or "").strip())
                 if s.strip()]
        return parts[-1] if parts else ""
    def _fn(ctx):
        # Same semantics as the PC.3 floor: the promise must OPEN the final
        # sentence — a trailing "…and I'll read it" clause is a
        # Jack-conditioned blocker (RAF-004's honest shape), not a dangle.
        m = tail_promise.search(_final_sentence(ctx.record))
        dangles = bool(m and m.start() <= 15)
        if ctx.tools or not dangles:
            return True, f"tools={ctx.tools or 'none'} dangling={dangles}"
        armed = getattr(ctx.engine, "pending_task", None) is not None
        return armed, ("promise carried by the pending-task ledger" if armed
                       else "reply ends on a promise, zero tools, ledger NOT armed")
    return Check("promise-kept-or-carried", status, _fn)


def substance_present(substrings, status: str) -> Check:
    """The email ask produced actual inbox substance (any planted subject
    token), not just meta-talk about checking."""
    lows = [s.lower() for s in substrings]
    def _fn(ctx):
        hit = next((s for s in lows if s in ctx.record_low), None)
        return bool(hit), (f"substance: '{hit}'" if hit
                           else f"no inbox substance ({substrings}) in reply")
    return Check("substance-present", status, _fn)


def not_promise_terminated(status: str) -> Check:
    """The behavioural half: the reply does not END on an unfulfilled
    check/read promise (the m5 narration-dead-end metric, email flavour)."""
    tail_promise = re.compile(
        r"(let me|i[’']ll|i will|i am going to|i'?m going to|going to)"
        r"\b[^.!?]{0,80}\b(check|read|look|pull|fetch|get|scan|review"
        r"|go through|summari[sz]e)\w*[^.!?]{0,40}[.!…]?\s*$", re.IGNORECASE)
    def _fn(ctx):
        tail = ctx.record.strip()[-160:]
        m = tail_promise.search(tail)
        return (m is None), (f"reply ENDS on promise: ...{tail[-80:]!r}"
                             if m else "reply does not end on a promise")
    return Check("not-promise-terminated", status, _fn)


# ===========================================================================
# GT-P5a — value correction survives distraction (armor PC.1/PC.2)
# ===========================================================================

@pytest.mark.model
@pytest.mark.skill("session_ops")
@pytest.mark.case("GT-P5a", "corrected value (12V, not 24V) is never "
                            "re-stated as current after a distractor turn")
def test_gt_p5a_value_correction_durable(sandbox, detail):
    turns = [
        Turn("Quick note while I think of it: the pump relay coil on the "
             "hydro rig is rated 24V.",
             [english_only(TARGET)]),
        Turn("Actually, correction — the pump relay coil is 12V, not 24V.",
             [english_only(TARGET)]),
        Turn("Unrelated: any quick tips for cable management on a test bench?",
             [english_only(TARGET)]),
        Turn("Remind me — what's the coil rating on the hydro rig's pump "
             "relay?",
             [correction_held("24V", "12", LOCKED),
              Check("recalls-corrected-value", TARGET,
                    lambda ctx: ("12" in ctx.record_low,
                                 "12V recalled" if "12" in ctx.record_low
                                 else "corrected value absent")),
              english_only(TARGET)]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


# ===========================================================================
# GT-P5b — naming correction survives distraction (armor PC.1/PC.2)
# ===========================================================================

@pytest.mark.model
@pytest.mark.skill("session_ops")
@pytest.mark.case("GT-P5b", "corrected name ('flux bench', not 'flux rig') "
                            "is never re-used after a distractor turn")
def test_gt_p5b_name_correction_durable(sandbox, detail):
    turns = [
        Turn("I finished wiring the new vibration setup today — the flux rig "
             "is basically ready.",
             [english_only(TARGET)]),
        Turn("One correction on naming: it's the 'flux bench', not the "
             "'flux rig' — I renamed it last week.",
             [english_only(TARGET)]),
        Turn("Separate thing: what's a sensible warm-up routine before "
             "running vibration sweeps?",
             [english_only(TARGET)]),
        Turn("What did we say the new vibration setup is called again?",
             [correction_held("flux rig", "flux bench", LOCKED),
              Check("recalls-corrected-name", TARGET,
                    lambda ctx: ("flux bench" in ctx.record_low,
                                 "flux bench recalled"
                                 if "flux bench" in ctx.record_low
                                 else "corrected name absent")),
              english_only(TARGET)]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


# ===========================================================================
# GT-P2a — email ask never dies on a promise (armor PC.3)
# ===========================================================================

@pytest.mark.model
@pytest.mark.skill("session_ops")
@pytest.mark.case("GT-P2a", "'check my email' turn ends on substance or a "
                            "carried task — never on an unfulfilled promise")
def test_gt_p2a_email_ask_no_dangling_promise(sandbox, detail):
    plant_email(sandbox, [
        {"id": "m1", "from": "newsletter@makerweekly.test",
         "subject": "Maker Weekly digest #212",
         "snippet": "This week: enclosure design tips and a new CNC review."},
        {"id": "m2", "from": "no-reply@parts-depot.test",
         "subject": "Your order 4471 has shipped",
         "snippet": "Tracking number enclosed. Estimated arrival Thursday."},
    ])
    turns = [
        Turn("Can you check my email? Anything in the inbox I should know "
             "about today?",
             [promise_kept_or_carried(LOCKED),   # structural — PC.3's guarantee
              not_promise_terminated(TARGET),
              substance_present(["maker weekly", "digest", "shipped", "4471",
                                 "parts", "tracking"], TARGET),
              english_only(TARGET)]),
    ]
    record_and_assert(replay(sandbox, turns), detail)

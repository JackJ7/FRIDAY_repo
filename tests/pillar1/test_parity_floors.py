r"""
PC-leg guards (armor plan §6, "M2 batch" / PC leg): code-only, no live model.

COR-001..007  the correction ledger + floor (PC.1/PC.2, parity row P5): a
        cue+pair correction whose WRONG side really appeared earlier in the
        session becomes a session constraint (directive rides the referent
        block, no TTL, FIFO-bounded); a later reply stating the corrected-away
        value WITHOUT the corrected one is regenerated once, then
        deterministically substituted (Jack's correction is authoritative —
        the date-floor posture). Both-present replies pass (discussing the
        correction honestly is fine — the goldens grade by the same rule).

DIF-001..005  the dangling-intent floor (PC.3, parity row P2): a
        request-shaped turn whose reply ENDS on a first-person-future promise
        with ZERO tools run gets ONE retry WITH tools; emitted calls run
        through _run_tool (gate/taint/referents hold) and their results are
        APPENDED (never replaced — the F4/A1 lesson). A promise the retry
        still doesn't act on is carried by the pending-task ledger (the
        promise sentence becomes the blocker) and the offer ledger is
        suppressed for that turn — Jack already asked; waiting for another
        "yes" is the m1 redundant-ask friction this floor exists to close.
        Non-request turns keep today's offer-ledger behavior untouched.

FCF-001..004  the false-completion floor (PC.4, the GT-C9 r1 residual): while
        a durable task is LIVE (consolidation or pending-task ledger — the
        code-owned truth), a reply claiming the work is done with zero landed
        actions this turn is regenerated once against the ledger status;
        a retry that still claims gets the code-built status line instead.
        Landed work retires the ledgers first, so honest completions never
        trip.
"""

import re

import pytest

from core.model import ModelReply


class _ScriptModel:
    """Scripted replies in order; records every chat() message list. An item
    is a string (text reply) or {"content": ..., "tool_calls": [...]}."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.seen.append(messages)
        item = self.script.pop(0) if self.script else ""
        r = ModelReply()
        if isinstance(item, dict):
            r.content = item.get("content", "")
            r.tool_calls = list(item.get("tool_calls", []))
        else:
            r.content = item
        r.eval_count = 5
        return r


def _sys_text(model) -> str:
    msgs = model.seen[-1]
    return "\n".join(m.get("content") or "" for m in msgs
                     if m.get("role") == "system")


def _eng(sandbox, script):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    return eng


def _seed_correction(eng):
    """Arm one correction via the public turn path: the wrong value enters
    the session in T1's reply, Jack corrects in T2."""
    eng.model.script[:0] = ["Noted — the pump relay coil is rated 24V.",
                            "Got it — 12V it is."]
    eng.respond("Quick note: the pump relay coil on the hydro rig is 24V.")
    eng.respond("Actually, correction — the pump relay coil is 12V, not 24V.")


# ---------------------------------------------------------------------------
# COR — correction ledger + floor (PC.1 / PC.2)
# ---------------------------------------------------------------------------

@pytest.mark.upgrade
@pytest.mark.case("COR-001", "cue+pair+history correction arms the ledger and "
                             "its directive rides the next turn's block")
def test_cor001_arming(sandbox):
    eng = _eng(sandbox, ["Understood."])
    _seed_correction(eng)
    assert eng.corrections, "correction did not arm"
    c = eng.corrections[-1]
    assert c["wrong"].lower() == "24v" and "12v" in c["right"].lower(), c
    eng.respond("Thanks. What else is on today?")
    sys_txt = _sys_text(eng.model)
    assert "CORRECTIONS Jack made this session" in sys_txt
    assert "24V" in sys_txt and "12V" in sys_txt


@pytest.mark.upgrade
@pytest.mark.case("COR-002", "no arm without a cue, and no arm when the wrong "
                             "side never appeared in the session")
def test_cor002_no_false_arm(sandbox):
    # (a) contrast shape, no correction cue — Jack stating a preference.
    eng = _eng(sandbox, ["Noted.", "Sure."])
    eng.respond("The bench PSU stays at 12V, not 24V, for this board.")
    assert not eng.corrections, eng.corrections
    # (b) cue + pair, but the wrong side is nowhere in the session yet —
    # thinking aloud, not correcting the record.
    eng.respond("Actually, correction — it's 3300uF, not 2200uF.")
    assert not eng.corrections, eng.corrections


@pytest.mark.upgrade
@pytest.mark.case("COR-003", "floor catches a re-violation; the corrected "
                             "retry is accepted")
def test_cor003_floor_retry_accepted(sandbox):
    eng = _eng(sandbox, [])
    _seed_correction(eng)
    eng.model.script = ["The coil is rated 24V.",       # violating draft
                        "The coil is 12V."]             # clean retry
    eng.respond("Remind me, what's the coil rating?")
    final = eng.history[-1]["content"]
    assert "12" in final and "24V" not in final, final


@pytest.mark.upgrade
@pytest.mark.case("COR-004", "retry still violating -> deterministic "
                             "wrong->right substitution")
def test_cor004_substitution(sandbox):
    eng = _eng(sandbox, [])
    _seed_correction(eng)
    eng.model.script = ["The coil is rated 24V.",       # violating draft
                        "As noted, it's 24V."]          # retry violates too
    eng.respond("Remind me, what's the coil rating?")
    final = eng.history[-1]["content"]
    assert "24V" not in final and "12V" in final, final


@pytest.mark.upgrade
@pytest.mark.case("COR-005", "a reply carrying BOTH values is discussing the "
                             "correction — floor stays silent")
def test_cor005_both_present_passes(sandbox):
    eng = _eng(sandbox, [])
    _seed_correction(eng)
    draft = "You first said 24V, then corrected it to 12V — 12V is current."
    eng.model.script = [draft]
    eng.respond("What did we settle on for the coil?")
    assert eng.history[-1]["content"] == draft


@pytest.mark.upgrade
@pytest.mark.case("COR-006", "ledger is FIFO-bounded at 8 — oldest evicted")
def test_cor006_fifo_bound(sandbox):
    eng = _eng(sandbox, ["Old value 900mA stands, noted."])
    eng.respond("The stall current figure is 900mA, by the way.")
    eng.corrections = [{"wrong": f"w{i}", "right": f"r{i}"} for i in range(8)]
    eng.model.script = ["Understood, 800mA."]
    eng.respond("Actually, correction — it's 800mA, not 900mA.")
    assert len(eng.corrections) == 8
    assert eng.corrections[0]["wrong"] == "w1", eng.corrections[0]
    assert eng.corrections[-1]["wrong"].lower() == "900ma"


@pytest.mark.upgrade
@pytest.mark.case("COR-007", "corrections hold the stream — a violating "
                             "draft never reaches the token stream")
def test_cor007_stream_hold(sandbox):
    eng = _eng(sandbox, [])
    _seed_correction(eng)
    eng.model.script = ["The coil is rated 24V.", "The coil is 12V."]
    tokens = []
    eng.respond("Remind me, what's the coil rating?",
                on_token=tokens.append)
    stream = "".join(tokens)
    assert "24V" not in stream and "12" in stream, stream


# ---------------------------------------------------------------------------
# DIF — dangling-intent floor (PC.3)
# ---------------------------------------------------------------------------

def _note_read_call():
    return {"function": {"name": "read_brain",
                         "arguments": {"path": "preferences/about_jack.md"}}}


@pytest.mark.upgrade
@pytest.mark.case("DIF-001", "request + zero tools + promise tail -> retry "
                             "WITH tools; emitted call runs and its result "
                             "is APPENDED")
def test_dif001_recovery_executes(sandbox):
    eng = _eng(sandbox, [
        "Sure — let me check the notes now.",           # dangling draft
        {"content": "", "tool_calls": [_note_read_call()]},  # retry acts
    ])
    eng.respond("Please check your notes and tell me what you have on me.")
    final = eng.history[-1]["content"]
    assert final.startswith("Sure — let me check the notes now."), final
    assert "metric fasteners" in final, f"result not appended: {final!r}"
    assert eng.pending_task is None


@pytest.mark.upgrade
@pytest.mark.case("DIF-002", "retry that still doesn't act -> draft kept, "
                             "promise carried by the pending-task ledger, "
                             "offer ledger suppressed")
def test_dif002_fallback_arms_pending(sandbox):
    eng = _eng(sandbox, [
        "Sure — let me check the notes now.",           # dangling draft
        "I will get to it shortly.",                    # retry: still no tools
    ])
    eng.respond("Please check your notes and tell me what you have on me.")
    final = eng.history[-1]["content"]
    assert final == "Sure — let me check the notes now.", final
    assert eng.pending_task is not None, "promise not carried"
    assert "check the notes" in eng.pending_task["blocker"].lower()
    assert eng.offer is None, "promise wrongly armed the offer ledger"


@pytest.mark.upgrade
@pytest.mark.case("DIF-003", "non-request turn: a promise is an OFFER — "
                             "floor silent, offer ledger arms exactly as "
                             "today")
def test_dif003_offer_ledger_untouched(sandbox):
    eng = _eng(sandbox, [
        "Nice. I'll review the wiring diagram if you'd like.",
    ])
    eng.respond("I got the new bench PSU today.")
    assert eng.offer is not None, "offer should arm on a non-request turn"
    assert eng.pending_task is None
    assert eng.history[-1]["content"].startswith("Nice.")


@pytest.mark.upgrade
@pytest.mark.case("DIF-004", "question tails and mid-reply promises followed "
                             "by substance never fire")
def test_dif004_negative_shapes(sandbox):
    eng = _eng(sandbox, [
        "Shall I check the wiring notes for you?",
    ])
    eng.respond("Please sort out the wiring question.")
    assert eng.history[-1]["content"].endswith("?")

    eng2 = _eng(sandbox, [
        "Let me check the numbers... done: the divider needs 6.8k over 3.3k.",
    ])
    eng2.respond("Please work out the divider values.")
    assert "6.8k" in eng2.history[-1]["content"]


@pytest.mark.upgrade
@pytest.mark.case("DIF-006", "Jack-conditioned trailing promise ('double-"
                             "check the path and I'll read it') is a stated "
                             "blocker, not a dangle — floor silent, no retry "
                             "burned (the RAF-004 collision shape)")
def test_dif006_conditional_promise_silent(sandbox):
    honest = ("I can't find that file - double-check the path and I'll "
              "read it.")
    eng = _eng(sandbox, [honest])
    eng.respond("read C:/nope/definitely_missing_notes.md")
    assert eng.history[-1]["content"] == honest
    assert len(eng.model.seen) == 1, "a retry was burned on an honest blocker"


@pytest.mark.upgrade
@pytest.mark.case("DIF-007", "a LATE floor (script floor, last by design) "
                             "regenerating the reply into a fresh dangling "
                             "tail still gets the promise carried — the "
                             "post-floor re-scan arms the ledger (GT-P2a "
                             "pc-batch r3's S1 hole)")
def test_dif007_late_floor_rescan(sandbox):
    eng = _eng(sandbox, [
        "ให้ฉันตรวจ"
        "สอบกล่องจด"
        "หมาย",                   # drifted draft (Thai)
        "I'll check the inbox in a moment.",           # S1 regen: dangles
    ])
    eng.respond("Please check the inbox for me.")
    final = eng.history[-1]["content"]
    assert final == "I'll check the inbox in a moment.", final
    assert eng.pending_task is not None, "late dangle not carried"
    assert "check the inbox" in eng.pending_task["blocker"].lower()


@pytest.mark.upgrade
@pytest.mark.case("DIF-008", "'let me know if …' is a polite closer that "
                             "directs JACK to act — never a dangle, no "
                             "retry burned, no ledger armed (GT-P2a r3's "
                             "false-positive shape)")
def test_dif008_let_me_know_closer(sandbox):
    closer = ("Both emails are routine. Let me know if you want to review "
              "them in detail.")
    eng = _eng(sandbox, [closer])
    eng.respond("Please check my email and tell me if anything needs me.")
    assert eng.history[-1]["content"] == closer
    assert eng.pending_task is None
    assert len(eng.model.seen) == 1, "a retry was burned on a polite closer"


@pytest.mark.upgrade
@pytest.mark.case("DIF-005", "narrated-listing tail stays CN.4's: the "
                             "specific floor runs list_projects, this one "
                             "stays out")
def test_dif005_cn4_priority(sandbox):
    eng = _eng(sandbox, [
        "Sure. Let's start by listing them.",
    ])
    eng.respond("Please tidy up my projects.")
    final = eng.history[-1]["content"]
    # CN.4 appended the real listing; the dangling floor must not have
    # consumed a second scripted reply (script is empty — a retry would have
    # produced content "" and either emptied or double-appended).
    assert "Let's start by listing them." in final
    assert len(final) > len("Sure. Let's start by listing them."), final


# ---------------------------------------------------------------------------
# FCF — false-completion floor (PC.4)
# ---------------------------------------------------------------------------

def _plant_flux(sandbox):
    for slug in ("fluxbeam", "flux_beam_tool", "flux_beam_v2"):
        sandbox.brain.write_note(
            f"projects/{slug}.md",
            f"# {slug.replace('_', ' ').title()}\n\n- **Status:** active\n\n"
            "Flux beam tooling.\n",
            mode="create", summary=f"plant {slug}")


@pytest.mark.upgrade
@pytest.mark.case("FCF-001", "live task + completion claim + zero landed "
                             "actions -> regen; claim-free retry accepted")
def test_fcf001_claim_regenerated(sandbox):
    _plant_flux(sandbox)
    eng = _eng(sandbox, ["Here are the flux projects — shall I merge them?"])
    eng.respond("Please consolidate all the projects with flux in the name.")
    assert eng.consolidation is not None
    eng.model.script = [
        "I've merged the projects already.",                # false claim
        "Not yet — fluxbeam, flux_beam_tool and flux_beam_v2 are still "
        "separate. Say the word and I'll run the merge.",   # honest retry
    ]
    eng.respond("How's it looking?")
    final = eng.history[-1]["content"]
    assert "Not yet" in final, final


@pytest.mark.upgrade
@pytest.mark.case("FCF-002", "retry still claiming -> code-built status from "
                             "the ledger replaces it")
def test_fcf002_code_built_status(sandbox):
    _plant_flux(sandbox)
    eng = _eng(sandbox, ["Here are the flux projects — shall I merge them?"])
    eng.respond("Please consolidate all the projects with flux in the name.")
    eng.model.script = [
        "I've merged the projects already.",     # false claim
        "All done — I've merged everything.",    # retry claims again
    ]
    eng.respond("How's it looking?")
    final = eng.history[-1]["content"]
    assert "still pending" in final.lower(), final
    assert "fluxbeam" in final, final


@pytest.mark.upgrade
@pytest.mark.case("FCF-003", "action that LANDED this turn -> floor silent "
                             "(the ledger retires on disk truth downstream)")
def test_fcf003_landed_action_silent(sandbox):
    _plant_flux(sandbox)
    eng = _eng(sandbox, ["Here are the flux projects — shall I merge them?"])
    eng.respond("Please consolidate all the projects with flux in the name.")
    claim = "I've merged them — flux_beam_tool and flux_beam_v2 are folded in."
    eng.model.script = [
        {"content": "",
         "tool_calls": [{"function": {"name": "merge_projects",
                                      "arguments": {
                                          "target": "fluxbeam",
                                          "duplicates": ["flux_beam_tool",
                                                         "flux_beam_v2"]}}}]},
        claim,
    ]
    eng.respond("Go ahead, keep fluxbeam as the survivor.")
    final = eng.history[-1]["content"]
    assert final == claim, final


@pytest.mark.upgrade
@pytest.mark.case("FCF-004", "no live task -> silent regardless of claim "
                             "phrasing")
def test_fcf004_no_task_silent(sandbox):
    claim = "I've updated my notes with that, by the way."
    eng = _eng(sandbox, [claim])
    eng.respond("Morning! Anything I should know?")
    assert eng.history[-1]["content"] == claim

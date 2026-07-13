r"""
Proactive-briefing grounding — the PURE-CODE half (FRIDAY_notes10_plan.md
Phase 8). No model, no GPU, so these run in --quick.

Phase 1 grounded the CALENDAR in the proactive path; Phase 8 adds two more
floors of the same shape, locked here without the model:

  * §1 research-status floor (HARD). `_phantom_run_sentences` flags any clause
    framing a run as in-progress while the live ledger says it is terminal/absent;
    `_run_is_terminal` is the authority; `_research_status_line` renders the DATA;
    `_vet_proactive` regenerates once then STRIPS deterministically — the code
    guarantee GT-C7 will lock on.
  * §2 provenance guard (SOFT — honest ceiling). `_proactive_action_claims`
    detects first-person completed-action clauses recited unprompted; measured +
    best-effort reframed, never a clean strip (asserted here).

The model-in-the-loop goldens (GT-C7/C8) are TARGET->LOCK in test_notes10.py and
run against the live 14B; this file is the deterministic lock behind them.
"""

import types

import pytest

from core.engine import Engine


def _engine():
    """A bare Engine for the pure detector/vet helpers — they touch only
    class-level regexes, _CLAUSE_SPLIT, and (in _vet_proactive) self.model +
    self.session_tokens, so __init__ is skipped (same as test_date_floor)."""
    return Engine.__new__(Engine)


class _FakeModel:
    """Stands in for the Ollama client: chat() returns a canned reply with the
    .content / .eval_count that _vet_proactive reads. Records call count so a
    test can assert exactly one regeneration."""
    def __init__(self, retry_content):
        self.retry_content = retry_content
        self.calls = 0

    def chat(self, messages, on_token=None):
        self.calls += 1
        return types.SimpleNamespace(content=self.retry_content, eval_count=0)


# ======================================================================
# §1 — the research-status floor detectors.
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("BRIEF-001", "in-progress run framing is flagged when the live "
                              "ledger says the run is terminal or absent")
def test_phantom_run_flagged_when_terminal():
    e = _engine()
    text = ("Morning. The autoresearch run on the rig is still in progress, "
            "closing on a better val_bpb.")
    # crashed / done / stopped / no-run all mean "not live" -> the clause phantoms.
    for status in ({"state": "crashed", "tag": "smoke1"},
                   {"state": "done"}, {"state": "stopped"}, {}):
        bad = e._phantom_run_sentences(text, status)
        assert bad, f"missed phantom for status={status!r}"


@pytest.mark.upgrade
@pytest.mark.case("BRIEF-002", "in-progress framing is NOT flagged when the ledger "
                              "says the run is actually live")
def test_active_run_not_flagged():
    e = _engine()
    text = "The training run is still in progress and should finish tonight."
    for status in ({"state": "running", "tag": "r1"}, {"state": "setting_up"}):
        assert e._phantom_run_sentences(text, status) == []


@pytest.mark.upgrade
@pytest.mark.case("BRIEF-003", "a PAST-framed run mention survives (history, not a "
                              "phantom current-state claim)")
def test_past_run_mention_survives():
    e = _engine()
    # "was" / "crashed earlier" is history — must not be flagged even on empty ledger.
    for text in ("The research run crashed earlier today.",
                 "Last week the experiment was still running when you left."):
        assert e._phantom_run_sentences(text, {}) == []


@pytest.mark.upgrade
@pytest.mark.case("BRIEF-004", "_run_is_terminal: terminal/absent states are 'not "
                              "live'; setting_up/running are live")
def test_run_is_terminal_truth_table():
    e = _engine()
    for st in ("crashed", "done", "stopped"):
        assert e._run_is_terminal({"state": st})
    assert e._run_is_terminal({})            # no run on record
    assert e._run_is_terminal({"foo": 1})    # no state field
    assert not e._run_is_terminal({"state": "running"})
    assert not e._run_is_terminal({"state": "setting_up"})


@pytest.mark.upgrade
@pytest.mark.case("BRIEF-005", "_research_status_line renders the ledger state as "
                              "authoritative DATA, and states 'no runs' plainly")
def test_research_status_line():
    e = _engine()
    line = e._research_status_line({"tag": "smoke1", "state": "crashed",
                                    "iteration": 0, "max_iters": 200})
    assert "smoke1" in line and "crashed" in line and "0/200" in line
    empty = e._research_status_line({})
    assert "No research run" in empty and "in progress" in empty


# ======================================================================
# §2 — the provenance guard detector (soft).
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("BRIEF-006", "first-person completed-action clauses are detected; "
                              "record-framed and future/offer prose are left alone")
def test_provenance_detector():
    e = _engine()
    claims = [
        "I've consolidated the upgrade projects into one folder.",
        "I have updated the tracker for you.",
        "I moved the sketches into the rig folder.",
        "I archived the old notes and renamed the project.",
    ]
    for c in claims:
        assert e._proactive_action_claims(c), f"missed claim: {c!r}"
    # Record-framed / offer / future — NOT a fresh first-person action claim.
    clean = [
        "Your notes record that the upgrade projects were consolidated.",
        "Last session, the tracker was updated.",
        "Would you like me to consolidate the upgrade projects?",
        "I can update the tracker if you want.",
    ]
    for s in clean:
        assert e._proactive_action_claims(s) == [], f"false positive: {s!r}"


# ======================================================================
# §1 integration — _vet_proactive: regenerate once, then STRIP the hard floor.
# ======================================================================

@pytest.mark.upgrade
@pytest.mark.case("BRIEF-007", "_vet_proactive deterministically strips a phantom "
                              "run clause when the regeneration still frames it")
def test_vet_strips_phantom_run():
    e = _engine()
    e.session_tokens = 0
    # The retry STILL frames the run as live -> the deterministic strip must fire.
    e.model = _FakeModel("The autoresearch run is still in progress on the rig.")
    reply = types.SimpleNamespace(
        content="The autoresearch run is still in progress.", eval_count=0)
    out = e._vet_proactive(reply, messages=[], cal_result=None,
                           status={"state": "crashed", "tag": "smoke1"})
    assert e.model.calls == 1                       # exactly one regeneration
    assert e._phantom_run_sentences(out, {"state": "crashed"}) == []  # none survive


@pytest.mark.upgrade
@pytest.mark.case("BRIEF-008", "_vet_proactive keeps a clean regeneration (no strip "
                              "when the retry actually fixes it)")
def test_vet_keeps_clean_retry():
    e = _engine()
    e.session_tokens = 0
    fixed = "Nothing's training right now — the last run crashed. Where to next?"
    e.model = _FakeModel(fixed)
    reply = types.SimpleNamespace(
        content="The run is still in progress.", eval_count=0)
    out = e._vet_proactive(reply, messages=[], cal_result=None,
                           status={"state": "crashed"})
    assert out == fixed                             # clean retry used as-is
    assert e.model.calls == 1


@pytest.mark.upgrade
@pytest.mark.case("BRIEF-009", "provenance is SOFT: _vet_proactive reframes via one "
                              "regeneration but never strips a first-person clause, "
                              "and sets the measured flag")
def test_vet_provenance_soft_measure():
    e = _engine()
    e.session_tokens = 0
    # Retry reframes to a record -> flag clears; nothing stripped (soft guard).
    e.model = _FakeModel("Your notes record the upgrade projects were merged.")
    reply = types.SimpleNamespace(
        content="I've consolidated the upgrade projects into one folder.",
        eval_count=0)
    out = e._vet_proactive(reply, messages=[], cal_result=None, status=None)
    assert e.model.calls == 1
    assert e._proactive_action_claim is False       # post-reframe measure
    assert "notes record" in out

    # If the retry KEEPS the claim, the flag STAYS True (measured, not forced) —
    # the honest ceiling: no deterministic strip removes it.
    e2 = _engine(); e2.session_tokens = 0
    e2.model = _FakeModel("I've consolidated the upgrade projects again.")
    reply2 = types.SimpleNamespace(
        content="I've consolidated the upgrade projects into one folder.",
        eval_count=0)
    out2 = e2._vet_proactive(reply2, messages=[], cal_result=None, status=None)
    assert e2._proactive_action_claim is True
    assert e2._proactive_action_claims(out2)        # still present, not stripped


@pytest.mark.upgrade
@pytest.mark.case("BRIEF-010", "a fully-grounded clean message needs no regeneration "
                              "(no false-positive strip)")
def test_vet_noop_on_clean():
    e = _engine()
    e.session_tokens = 0
    e.model = _FakeModel("SHOULD NOT BE CALLED")
    clean = "Morning — the rig calibration is your live thread. Pick it up?"
    reply = types.SimpleNamespace(content=clean, eval_count=0)
    out = e._vet_proactive(reply, messages=[], cal_result=None,
                           status={"state": "done"})
    assert out == clean
    assert e.model.calls == 0                        # nothing to fix
    assert e._proactive_action_claim is False

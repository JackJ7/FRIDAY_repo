r"""
Armor A6 + A7 + S1 — the CODE floors, tested without the live model.

Same posture as test_date_floor.py: each floor's deterministic core is
asserted at zero model cost, and the respond()-level wiring is exercised with
a SCRIPTED model (a stub that plays back canned ModelReply objects), so the
barrier/vote plumbing is verified end-to-end without touching Ollama.

- VOTE-*  self-consistency voting (A6): the shared canonicalizers, the
          majority rule, and both engine surfaces (calc args, ANSWER line).
- QUO-*   quote-don't-recall contract (A7): the durable-value ledger, the
          byte-match detector, and the barrier + verbatim floor in respond().
- SCR-*   output-script floor (S1): the Latin script detector and the
          regenerate-then-honest-fallback path (CFG-007's code floor).
"""

import pytest

from core.canon import (canon_answer, canon_calc_args, canon_quantity,
                        canon_struct, majority)
from core.engine import Engine
from core.model import ModelReply


def _bare_engine():
    """A bare Engine for the pure detector helpers — they touch only
    class-level regexes, so __init__ (model, brain, gate wiring) is skipped."""
    return Engine.__new__(Engine)


class ScriptedModel:
    """Plays back a fixed sequence of replies. An item is either a string
    (a plain text reply) or a dict {"content": ..., "tool_calls": [...]}
    (a tool-call round). Running out of script is a test bug — fail loudly."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None):
        assert self.script, "scripted model ran out of replies"
        self.calls += 1
        item = self.script.pop(0)
        r = ModelReply()
        if isinstance(item, dict):
            r.content = item.get("content", "")
            r.tool_calls = list(item.get("tool_calls", []))
        else:
            r.content = item
        if on_token and r.content:
            on_token(r.content)
        return r


def _calc_call(expression, to_unit=""):
    args = {"expression": expression}
    if to_unit:
        args["to_unit"] = to_unit
    return {"function": {"name": "calc", "arguments": args}}


class _Snip:
    """Minimal retriever-result stand-in (path + snippet are all the engine
    reads)."""
    def __init__(self, path, snippet):
        self.path = path
        self.snippet = snippet


class _StubRetriever:
    def __init__(self, results):
        self.results = results

    def retrieve(self, query, top_k, include_test=False):
        return self.results


def _script_engine(sandbox, script, retrieved=()):
    """The sandbox engine with a scripted model (and optionally a stubbed
    retriever), ready for a direct respond() call."""
    eng = sandbox.service.engine
    eng.model = ScriptedModel(script)
    if retrieved is not None:
        eng.retriever = _StubRetriever(list(retrieved))
    return eng


# ---------------------------------------------------------------------------
# A6 — canonicalizers + majority (the vote's arithmetic)
# ---------------------------------------------------------------------------

@pytest.mark.case("VOTE-001", "canon_answer groups Pint-equal ANSWER lines "
                              "('0.06 kWh' == '60 Wh'); unparseable abstains as None")
def test_canon_answer_equality():
    assert canon_answer("blah\nANSWER: 60 Wh") == \
        canon_answer("other words\nANSWER: 0.06 kWh")
    # Different answers stay different — the vote can actually split.
    assert canon_answer("ANSWER: 60 Wh") != canon_answer("ANSWER: 61 Wh")
    # Unit spellings the graders accept group together (shared normalize_unit).
    assert canon_answer("ANSWER: 3 A") == canon_answer("ANSWER: 3 amps")
    # No ANSWER line -> None (the sample abstains, never groups).
    assert canon_answer("I think it's about sixty watt hours.") is None
    assert canon_answer("") is None
    # Unitless answers vote on the number alone.
    assert canon_answer("ANSWER: 42") == canon_answer("ANSWER: 42.0")


@pytest.mark.case("VOTE-002", "canon_calc_args equates equal-but-differently-"
                              "written expressions; a broken to_unit never groups with a working call")
def test_canon_calc_args_equality():
    # The A6 target: two compositions of the same math vote together.
    assert canon_calc_args({"expression": "12 V / (4 ohm)", "to_unit": "A"}) \
        == canon_calc_args({"expression": "3 A"})
    assert canon_calc_args({"expression": "40 W * 90 min", "to_unit": "Wh"}) \
        == canon_calc_args({"expression": "60 Wh"})
    # The classic precedence slip ('12 V / 4 ohm' = volt*ohm) cannot convert
    # to amps -> falls back to the struct form, distinct from the good call.
    bad = canon_calc_args({"expression": "12 V / 4 ohm", "to_unit": "A"})
    good = canon_calc_args({"expression": "12 V / (4 ohm)", "to_unit": "A"})
    assert bad != good
    # Unitless arithmetic canonicalizes on the evaluated number.
    assert canon_calc_args({"expression": "0.65 * 20 * 0.8"}) \
        == canon_calc_args({"expression": "10.4"})
    # Unparseable garbage still yields a stable (struct) form.
    assert canon_calc_args({"expression": "utter nonsense here"}) \
        == canon_struct({"expression": "utter nonsense here"})


@pytest.mark.case("VOTE-003", "majority(): >=2 votes win, all-distinct and "
                              "all-abstain yield no winner, agreement counts abstentions in the denominator")
def test_majority_rule():
    w, agr, counts = majority(["a", "b", "a"])
    assert w == "a" and abs(agr - 2 / 3) < 1e-9 and counts == {"a": 2, "b": 1}
    # All distinct: no majority — the caller keeps its original (safe direction).
    w, agr, _ = majority(["a", "b", "c"])
    assert w is None
    # Abstentions (None) never group, and they dilute agreement honestly:
    # 2-of-3 with one abstention is 0.67 confidence, not 1.0.
    w, agr, _ = majority(["a", None, "a"])
    assert w == "a" and abs(agr - 2 / 3) < 1e-9
    w, agr, _ = majority([None, None, None])
    assert w is None and agr == 0.0
    assert majority([]) == (None, 0.0, {})


@pytest.mark.case("VOTE-004", "engine and grader share ONE canonicalizer — "
                              "the suite's answer()/normalize_unit ARE core.canon's (identity, not copies)")
def test_shared_canonicalizers_identity():
    import core.canon as canon
    from helpers import extract, truth
    # Identity, not equality: a fork would still compare equal today and then
    # drift tomorrow. The armor plan's requirement is one implementation.
    assert extract.answer is canon.answer
    assert extract.NoAnswer is canon.NoAnswer
    assert truth.normalize_unit is canon.normalize_unit
    assert truth.ureg is canon.ureg


# ---------------------------------------------------------------------------
# A6 — the two engine surfaces, scripted end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.case("VOTE-005", "calc-args vote: a mis-composed expression is "
                              "outvoted 2-1 and the WINNING args execute (agreement retained)")
def test_calc_args_vote_switches(sandbox):
    eng = _script_engine(sandbox, [
        # Round 1: the model composes the precedence slip.
        {"content": "Let me compute that.",
         "tool_calls": [_calc_call("12 V / 4 ohm", "A")]},
        # Vote samples 2 and 3: both compose it right -> majority.
        {"content": "", "tool_calls": [_calc_call("12 V / (4 ohm)", "A")]},
        {"content": "", "tool_calls": [_calc_call("12 V / (4 ohm)", "A")]},
        # Round 2 (after the real calc result lands): the final answer.
        "The current is 3 A.",
    ], retrieved=[])
    reply = eng.respond("what's the current through a 4 ohm load at 12 V?")
    # The EXECUTED call carries the winning expression, not the slip.
    calc_runs = [t for t in reply.tool_log if t["tool"] == "calc"]
    assert len(calc_runs) == 1
    assert calc_runs[0]["args"]["expression"] == "12 V / (4 ohm)"
    assert calc_runs[0]["result"].startswith("= 3")
    # The vote record retained the hardness signal (A8/S2's future input).
    votes = [v for v in eng.last_votes if v["surface"] == "calc_args"]
    assert votes and votes[0]["switched"] is True
    # The engine logs agreement rounded to 3 decimals (0.667 for 2-of-3).
    assert votes[0]["agreement"] == pytest.approx(2 / 3, abs=1e-3)


@pytest.mark.case("VOTE-006", "ANSWER-line vote: the settled reply joins a "
                              "3-sample majority; a losing original is replaced by the winning sample")
def test_answer_line_vote(sandbox):
    eng = _script_engine(sandbox, [
        # The settled reply: a wrong answer (the x60-family slip).
        "40 W for 90 min stores it up.\nANSWER: 3600 Wh",
        # Samples 2 and 3 agree on the right one (different spellings — the
        # canonicalizer must group them).
        "Work it in units.\nANSWER: 60 Wh",
        "Energy = P*t.\nANSWER: 0.06 kWh",
    ], retrieved=[])
    reply = eng.respond(
        "How much energy does a 40 W heater use in 90 minutes? End your "
        "reply with exactly one line: ANSWER: <number> <unit>")
    assert canon_answer(reply.content) == canon_answer("ANSWER: 60 Wh")
    votes = [v for v in eng.last_votes if v["surface"] == "answer_line"]
    assert votes and votes[0]["switched"] is True


@pytest.mark.case("VOTE-007", "no majority (all samples distinct) keeps the "
                              "original reply — the vote never replaces on a split")
def test_split_vote_keeps_original(sandbox):
    eng = _script_engine(sandbox, [
        "ANSWER: 10 Wh",
        "ANSWER: 20 Wh",
        "ANSWER: 30 Wh",
    ], retrieved=[])
    reply = eng.respond("quick check. ANSWER: <number> <unit>")
    assert "10 Wh" in reply.content  # original kept
    votes = [v for v in eng.last_votes if v["surface"] == "answer_line"]
    assert votes and votes[0]["switched"] is False
    assert votes[0]["agreement"] < 0.5  # the split IS the signal


# ---------------------------------------------------------------------------
# A7 — quote-don't-recall: ledger, detector, barrier + verbatim floor
# ---------------------------------------------------------------------------

@pytest.mark.case("QUO-001", "durable-value ledger: atom-bearing field lines "
                              "are collected (with source), prose values exempt, duplicates collapse")
def test_durable_value_ledger():
    e = _bare_engine()
    ledger = []
    text = ("# Beta Probe\n\n- **Status:** reference\n"
            "- **Pressure rating:** 30 bar housing\n"
            "- **Sensor:** HX717\n"
            "Some prose about the probe.\n")
    e._collect_durable_values(text, "projects/beta_probe.md", ledger)
    fields = {en["field"] for en in ledger}
    # Atom-bearing values are ledgered; 'Status: reference' has no digit
    # atom, so it is exempt (prose recall may be reworded).
    assert fields == {"Pressure rating", "Sensor"}
    assert all(en["source"] == "projects/beta_probe.md" for en in ledger)
    # Re-surfacing the same line (snippet + full read) doesn't double-ledger.
    e._collect_durable_values(text, "projects/beta_probe.md", ledger)
    assert len(ledger) == 2


@pytest.mark.case("QUO-002", "byte-match detector: fires on a corrupted atom "
                              "(HX717->HX711), never on verbatim quotes, valueless mentions, or Jack's own new value")
def test_quote_mismatch_detector():
    e = _bare_engine()
    ledger = [{"field": "Sensor", "value": "HX717",
               "source": "projects/x.md"},
              {"field": "Load cell", "value": "20 kg rated", "source": None}]
    # The A7 target class: same field, one atom corrupted.
    hit = e._quote_mismatch("You're using the HX711 sensor on that rig.",
                            "what sensor is on the rig?", ledger)
    assert hit and hit["value"] == "HX717"
    # Verbatim quote -> the contract is met.
    assert e._quote_mismatch("The sensor is the HX717.",
                             "what sensor?", ledger) is None
    # Atom-set matching, not substring: '30' is NOT satisfied by '300'.
    ledger2 = [{"field": "Pressure rating", "value": "30 bar housing",
                "source": None}]
    assert e._quote_mismatch("Pressure rating is 300 bar.",
                             "rating?", ledger2) is not None
    # ...but a reworded clause carrying the exact atoms passes ('rated 20 kg'
    # for '20 kg rated' — the atoms are byte-exact, the prose order is free).
    assert e._quote_mismatch("The load cell is rated 20 kg.",
                             "load cell?", ledger) is None
    # A field mention with NO value claim (an offer) never fires.
    assert e._quote_mismatch("Want me to update the Sensor field?",
                             "hm", ledger) is None
    # Jack supplying a NEW value himself: echoing him is not recall.
    assert e._quote_mismatch("Noted — sensor is the HX720 now.",
                             "we swapped to an HX720, note that down",
                             ledger) is None
    # Sentence-ending punctuation doesn't break the byte-match ('30.' == 30).
    ledger3 = [{"field": "Torque", "value": "30 N*m", "source": None}]
    assert e._quote_mismatch("Torque is 30 N*m.", "torque?", ledger3) is None


@pytest.mark.case("QUO-003", "quote barrier end-to-end: a paraphrased stored "
                              "value forces a re-read + retry, and the verbatim record is floor-appended when the retry still won't quote it")
def test_quote_barrier_floor(sandbox):
    snip = _Snip("projects/beta_probe.md",
                 "- **Pressure rating:** 30 bar housing")
    eng = _script_engine(sandbox, [
        # The settled reply corrupts the stored atom (30 -> 300).
        "Your notes say the pressure rating is 300 bar.",
        # The corrective retry STILL states the wrong figure.
        "It is rated 300 bar.",
    ], retrieved=[snip])
    reply = eng.respond("what's the pressure rating on the beta probe?")
    # The engine forced a real re-read of the source note (calendar-first shape).
    assert any(t["tool"] == "read_brain"
               and t["args"].get("path") == "projects/beta_probe.md"
               for t in reply.tool_log), reply.tool_log
    # The deterministic floor: the true stored bytes are IN the final reply
    # no matter what the model did — never "close enough".
    assert "30 bar housing" in reply.content, reply.content


@pytest.mark.case("QUO-004", "quote barrier accepts a retry that quotes the "
                              "record verbatim (no floor append needed)")
def test_quote_barrier_accepts_verbatim_retry(sandbox):
    snip = _Snip("projects/beta_probe.md",
                 "- **Pressure rating:** 30 bar housing")
    eng = _script_engine(sandbox, [
        "Your notes say the pressure rating is 300 bar.",
        "Correcting myself: the saved record reads 30 bar housing.",
    ], retrieved=[snip])
    reply = eng.respond("what's the pressure rating on the beta probe?")
    assert "30 bar housing" in reply.content
    assert "Quoting the saved record" not in reply.content  # no floor needed


@pytest.mark.case("QUO-005", "well-behaved turns are free: verbatim recall "
                              "and non-recall chatter never trip the quote barrier")
def test_quote_barrier_no_false_fire(sandbox):
    snip = _Snip("projects/beta_probe.md",
                 "- **Pressure rating:** 30 bar housing")
    eng = _script_engine(sandbox, [
        "The probe housing is rated 30 bar housing per your note.",
    ], retrieved=[snip])
    reply = eng.respond("what's the pressure rating on the beta probe?")
    # One model call only: no retry was spent, the barrier stayed quiet.
    assert eng.model.calls == 1
    assert "30 bar housing" in reply.content


# ---------------------------------------------------------------------------
# S1 — output-script floor (CFG-007's deterministic detector + fallback)
# ---------------------------------------------------------------------------

THAI_DRIFT = ("ขอโทษด้วยครับ ตอนนี้ฉันไม่สามารถช่วยคุณได้ "
              "กรุณาลองใหม่อีกครั้งในภายหลัง")


@pytest.mark.case("SCR-001", "script detector: English (accents included) "
                              "passes; a Thai-drifted reply or tail fires; a short foreign name does not")
def test_script_drift_detector():
    e = _bare_engine()
    # Ordinary English — including Latin accents — never fires.
    assert e._script_drifted("The café's naïve résumé — all good.") is False
    assert e._script_drifted("Torque is 1.2 N*m; check the 5V rail.") is False
    assert e._script_drifted("") is False
    # A wholesale drifted reply fires.
    assert e._script_drifted(THAI_DRIFT) is True
    # The observed CFG-007 shape: an English reply whose TAIL drifts.
    assert e._script_drifted(
        "The governance tiers are: " + THAI_DRIFT) is True
    # A short quoted foreign word/name stays under the thresholds.
    assert e._script_drifted("The city is written 東京 in Japanese.") is False
    assert e._script_drifted("Jack's contact wrote 'спасибо' at the end.") is False


@pytest.mark.case("SCR-002", "script floor end-to-end: one regeneration is "
                              "accepted when clean; a second drift falls back to the honest code reply")
def test_script_floor_regen_and_fallback(sandbox):
    # Case 1: the retry comes back clean -> accepted.
    eng = _script_engine(sandbox, [
        THAI_DRIFT,
        "Back in English: the config tiers are self_serve, propose, locked.",
    ], retrieved=[])
    reply = eng.respond("explain the config tiers")
    assert "self_serve" in reply.content
    assert eng._script_drifted(reply.content) is False

    # Case 2: the retry drifts AGAIN -> the honest fallback, never garbled text.
    sandbox.fresh_conversation()
    eng = _script_engine(sandbox, [THAI_DRIFT, THAI_DRIFT], retrieved=[])
    reply = eng.respond("explain the config tiers")
    assert reply.content == Engine._SCRIPT_FALLBACK
    assert eng._script_drifted(reply.content) is False


# ---------------------------------------------------------------------------
# S1.1 — per-round stream vetting (hop narration; floors leg)
# ---------------------------------------------------------------------------

def _no_foreign(text):
    """No non-Latin LETTER anywhere — the stream-cleanliness assertion."""
    e = _bare_engine()
    return all(e._is_latin_letter(ch) for ch in text if ch.isalpha())


@pytest.mark.case("SCR-003", "vetting shim: a clean round streams in full; a "
                              "drifted round emits ZERO foreign characters")
def test_vetted_stream_unit():
    e = _bare_engine()
    # Clean text: everything arrives once flushed, byte-identical.
    out = []
    vs = Engine._VettedStream(out.append, e._script_drifted)
    for tok in ("The tiers ", "are self_serve, ", "propose, locked."):
        vs(tok)
    vs.flush()
    assert "".join(out) == "The tiers are self_serve, propose, locked."
    # Drift mid-round: emission stops before ANY foreign letter escapes —
    # the 12-letter run trips inside the 24-char holdback.
    out = []
    vs = Engine._VettedStream(out.append, e._script_drifted)
    for tok in ("The governance tiers are: ", THAI_DRIFT, " more text"):
        vs(tok)
    assert vs.tripped
    vs.flush()  # a tripped stream must refuse to flush the tail
    assert _no_foreign("".join(out)), f"foreign leaked: {''.join(out)!r}"


@pytest.mark.case("SCR-004", "hop vetting end-to-end: a Thai narration hop is "
                              "withheld from the stream AND the transcript; the clean final answer still streams")
def test_drifted_hop_suppressed(sandbox):
    eng = _script_engine(sandbox, [
        {"content": THAI_DRIFT, "tool_calls": [_calc_call("2+2")]},
        "The result is 4.",
    ], retrieved=[])
    # Isolate the shim under test: A6 args-voting also samples on a
    # single-calc round and would desync the script (same isolation as
    # test_answer_floor.py; voting has its own VOTE-* guards).
    eng.vote_enabled = False
    tokens = []
    reply = eng.respond("run the numbers for me", on_token=tokens.append)
    stream = "".join(tokens)
    assert _no_foreign(stream), f"hop drift reached the stream: {stream!r}"
    assert "The result is 4." in stream
    assert reply.content == "The result is 4."
    # The drifted narration is scrubbed from history too — nothing for the
    # next round (or a later floor's retry transcript) to drift from.
    assert all(_no_foreign(m.get("content") or "") for m in eng.history)


@pytest.mark.case("SCR-005", "hop vetting no-false-positive: clean English "
                              "narration hops stream exactly as before")
def test_clean_hop_streams(sandbox):
    eng = _script_engine(sandbox, [
        {"content": "Checking the numbers now...",
         "tool_calls": [_calc_call("2+2")]},
        "Done — the result is 4.",
    ], retrieved=[])
    eng.vote_enabled = False  # same isolation as SCR-004
    tokens = []
    eng.respond("run the numbers for me", on_token=tokens.append)
    stream = "".join(tokens)
    assert "Checking the numbers now..." in stream
    assert "Done — the result is 4." in stream


@pytest.mark.case("SCR-006", "a drifted FINAL round never reaches the live "
                              "stream either — the floor's replacement is what streams")
def test_drifted_final_stream_clean(sandbox):
    eng = _script_engine(sandbox, [
        THAI_DRIFT,
        "Back in English: all sorted.",
    ], retrieved=[])
    tokens = []
    reply = eng.respond("explain the config tiers", on_token=tokens.append)
    stream = "".join(tokens)
    assert _no_foreign(stream), f"final drift reached the stream: {stream!r}"
    assert "Back in English: all sorted." in stream
    assert reply.content == "Back in English: all sorted."

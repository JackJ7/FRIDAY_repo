r"""PROP — property-based reasoning tests (Hypothesis + the local model).

Two kinds:
  - PURE-MATH properties: truth vs truth (no model). Run at full Hypothesis
    volume — they're fast and prove the graders themselves are sound.
  - MODEL-IN-LOOP properties: generate a problem, ask FRIDAY, grade her answer
    against independently-computed truth. Example count is capped
    (FRIDAY_TEST_EXAMPLES) because each example is an LLM call.

Every model-in-loop failure runs the magnitude-slip classifier, so a 60x
minutes/hours error is TAGGED, not just flagged.
"""

import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from helpers.extract import ANSWER_CONTRACT, NoAnswer, answer_in
from helpers.truth import (close, convert, energy_wh, magnitude_slip,
                           ohm_current, power_vi)

EXAMPLES = int(os.environ.get("FRIDAY_TEST_EXAMPLES", "100"))
MODEL_SETTINGS = settings(max_examples=EXAMPLES, deadline=None,
                          suppress_health_check=list(HealthCheck), derandomize=True)


# ---------- pure-math properties (no model; full volume) ----------

@pytest.mark.case("PROP-001", "unit round-trip: convert then invert returns the original (truth)")
@settings(max_examples=300, deadline=None)
@given(v=st.floats(0.001, 1e6), pair=st.sampled_from(
    [("meter", "foot"), ("newton", "pound_force"), ("watt", "horsepower"),
     ("ampere_hour", "coulomb"), ("kilopascal", "psi"), ("N*m", "foot_pound")]))
def test_unit_roundtrip_truth(v, pair):
    a, b = pair
    back = convert(convert(v, a, b), b, a)
    assert abs(back - v) / v < 1e-6


@pytest.mark.case("PROP-002", "magnitude-slip classifier correctly tags 60x/1000x families (truth)")
def test_slip_classifier():
    assert magnitude_slip(6000, 100) == "x60 (minutes<->hours)"
    assert magnitude_slip(0.05, 3) == "/60 (minutes<->hours)"
    assert magnitude_slip(50000, 50) == "x1000 (metric prefix)"
    assert magnitude_slip(51, 50) is None  # a correct-ish answer isn't a slip


# ---------- model-in-loop properties ----------
#
# Each example calls sandbox_session.fresh_conversation() FIRST. The sandbox is
# session-scoped (rebuilding a full FRIDAY per example is far too slow), but the
# CONVERSATION must not be shared: without a reset, hundreds of prior Q&As pile
# into one context and the degraded history suppresses tool-calling — she stops
# calling `calc` and reverts to (wrong) mental math. A reset makes every example
# an independent single-turn ask, which is both the realistic scenario and a
# fair test of per-question reasoning. (Found 2026-07-07: shared history, not
# FRIDAY, was manufacturing magnitude slips.)

@pytest.mark.case("PROP-010", "Ohm's law: I = V/R within tolerance over random V,R")
@pytest.mark.model
@pytest.mark.skill("quant_math")
@MODEL_SETTINGS
@given(v=st.integers(1, 24), r=st.integers(2, 1000))
def test_ohms_law(sandbox_session, v, r, prop_detail):
    sandbox_session.fresh_conversation()  # each example is independent (see note above)
    reply = sandbox_session.ask(
        f"A {v} volt source drives a {r} ohm resistor. What is the current?"
        + ANSWER_CONTRACT)
    truth = ohm_current(v, r)
    try:
        got = answer_in(reply, "ampere")
    except NoAnswer as e:
        prop_detail.fail(v=v, r=r, reply=reply, reason=str(e))
        pytest.fail(f"no parseable answer (V={v},R={r}): {e}")
    if not close(got, truth, 0.03):
        tag = magnitude_slip(got, truth)
        prop_detail.fail(v=v, r=r, got=got, truth=truth, slip=tag, reply=reply[-200:])
        pytest.fail(f"I=V/R wrong: got {got} A, truth {truth:.4f} A"
                    + (f" [{tag}]" if tag else ""))


@pytest.mark.case("PROP-011", "power P = V*I within tolerance over random V,I")
@pytest.mark.model
@pytest.mark.skill("quant_math")
@MODEL_SETTINGS
@given(v=st.integers(1, 48), i=st.integers(1, 40))
def test_power(sandbox_session, v, i, prop_detail):
    sandbox_session.fresh_conversation()
    reply = sandbox_session.ask(
        f"A load draws {i} amps at {v} volts. What is the power?" + ANSWER_CONTRACT)
    truth = power_vi(v, i)
    try:
        got = answer_in(reply, "watt")
    except NoAnswer as e:
        pytest.fail(f"no answer (V={v},I={i}): {e}")
    if not close(got, truth, 0.03):
        tag = magnitude_slip(got, truth)
        prop_detail.fail(v=v, i=i, got=got, truth=truth, slip=tag, reply=reply[-200:])
        pytest.fail(f"P=V*I wrong: got {got}, truth {truth}" + (f" [{tag}]" if tag else ""))


@pytest.mark.case("PROP-012", "energy over time: no minutes/hours (x60) magnitude slip")
@pytest.mark.model
@pytest.mark.skill("quant_math")
@MODEL_SETTINGS
@given(watts=st.integers(1, 200), minutes=st.integers(1, 300))
def test_energy_no_time_slip(sandbox_session, watts, minutes, prop_detail):
    sandbox_session.fresh_conversation()
    reply = sandbox_session.ask(
        f"A {watts} W load runs for {minutes} minutes. How much energy is used?"
        + ANSWER_CONTRACT)
    truth = energy_wh(watts, minutes)  # Wh
    try:
        got = answer_in(reply, "watt_hour")
    except NoAnswer as e:
        pytest.fail(f"no answer (W={watts},min={minutes}): {e}")
    tag = magnitude_slip(got, truth)
    if not close(got, truth, 0.03):
        prop_detail.fail(watts=watts, minutes=minutes, got=got, truth=truth,
                         slip=tag, reply=reply[-200:])
        pytest.fail(f"energy wrong: got {got} Wh, truth {truth:.3f} Wh"
                    + (f"  <<< MAGNITUDE-SLIP {tag}" if tag else ""))

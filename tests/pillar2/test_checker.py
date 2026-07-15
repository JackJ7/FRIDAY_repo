r"""CHK — independent local checker: Pint dimensional validity, plausibility
ranges, and two-way cross-checks. Fuzzy correctness that pure equality misses."""

import pytest

from helpers.extract import ANSWER_CONTRACT, NoAnswer, answer, answer_in
from helpers.truth import Q, close, normalize_unit


@pytest.mark.case("CHK-001", "her answer's unit is dimensionally valid for the asked quantity")
@pytest.mark.model
@pytest.mark.skill("quant_math")
def test_dimensional_validity(msandbox, detail):
    msandbox.fresh_conversation()  # independent single-turn ask (see test_golden note)
    reply = msandbox.ask("A 24 V supply drives a 6 ohm heater. What POWER does it dissipate?"
                         + ANSWER_CONTRACT)
    detail["reply"] = reply[-300:]
    val, unit = answer(reply)
    detail["answer"] = f"{val} {unit}"
    # Must be power-dimensioned; Pint raises/False on nonsense like 'A' or 'V'.
    assert Q(1, normalize_unit(unit)).check("[power]"), \
        f"answer unit '{unit}' is not power-dimensioned"
    assert close(val, 96.0, 0.03), f"P=V^2/R wrong: {val} (truth 96 W)"


@pytest.mark.case("CHK-002", "plausibility: a hobby servo's torque isn't absurd (range check)")
@pytest.mark.model
@pytest.mark.skill("quant_math")
def test_plausibility_torque(msandbox, detail):
    msandbox.fresh_conversation()
    reply = msandbox.ask("Roughly, what's a typical stall torque for a standard "
                         "hobby servo? Give one representative number." + ANSWER_CONTRACT)
    detail["reply"] = reply[-300:]
    try:
        got = answer_in(reply, "N*m")
    except NoAnswer as e:
        pytest.fail(str(e))
    detail["value_Nm"] = got
    # Standard hobby servos are ~0.1-5 N*m. Flag physically implausible answers.
    assert 0.02 <= got <= 20, f"implausible servo torque: {got} N*m"


@pytest.mark.case("CHK-003", "cross-check: energy computed two ways must agree")
@pytest.mark.model
@pytest.mark.skill("quant_math")
def test_cross_check_energy(msandbox, detail):
    msandbox.fresh_conversation()
    # Ask total energy; compute truth two independent ways; both must match her.
    reply = msandbox.ask(
        "A system has a 2 W sensor running continuously and a 30 W pump running "
        "10 minutes total, over one hour. Total energy used in that hour?"
        + ANSWER_CONTRACT)
    detail["reply"] = reply[-300:]
    way1 = 2 * 1 + 30 * (10 / 60)      # Wh: sensor + pump
    way2 = (2 * 3600 + 30 * 600) / 3600  # via joules -> Wh
    assert close(way1, way2, 1e-6)     # our truth is self-consistent
    try:
        got = answer_in(reply, "watt_hour")
    except NoAnswer as e:
        pytest.fail(str(e))
    detail["truth_Wh"] = round(way1, 3)
    detail["observed_Wh"] = got
    assert close(got, way1, 0.05), f"got {got} Wh, truth {way1:.3f} Wh"


@pytest.mark.case("CHK-004", "dimensional guard: invalid unit math is caught by Pint (self-test)")
def test_pint_catches_invalid():
    with pytest.raises(Exception):
        Q(5, "volt").to("watt")  # not convertible — must raise, never silently pass


@pytest.mark.case("CHK-005", "grader self-test: compound units with '*' and torque shorthands parse")
def test_extractor_unit_parsing():
    """Locks in the Tier-2 grader fixes: the extractor kept the full unit
    (not truncated at '*'), and torque shorthands map to real Pint units.
    These are the exact spellings the overnight run mis-graded."""
    from helpers.extract import answer, answer_in
    # '*' inside a unit survives extraction (was truncated to 'N').
    assert answer("ANSWER: 7.5 N*m") == (7.5, "N*m")
    assert answer("ANSWER: **30 N*m**") == (30.0, "N*m")
    assert abs(answer_in("ANSWER: 7.5 N*m", "N*m") - 7.5) < 1e-9
    # inch-pound torque (Pint has no 'inch_pound' unit; must map to force*length).
    assert abs(answer_in("ANSWER: 88.51 in-lb", "N*m") - 10.0) < 0.01
    # kg·cm servo torque = kilogram-FORCE·cm, not mass·length.
    assert abs(answer_in("ANSWER: 1.5 kg*cm", "N*m") - 0.1471) < 0.001
    # Unicode multiplication: the v2 tuned eval failed a CORRECT
    # "ANSWER: 30 N⋅m" (dot operator, U+22C5) because only the middle-dot
    # spelling was mapped. All three glyphs must grade like '*'.
    assert abs(answer_in("ANSWER: 30 N⋅m", "N*m") - 30.0) < 1e-9
    assert abs(answer_in("ANSWER: 30 N·m", "N*m") - 30.0) < 1e-9
    assert abs(answer_in("ANSWER: 6.3 W⋅h", "watt_hour") - 6.3) < 1e-9
    assert abs(answer_in("ANSWER: 1.5 kg⋅cm", "N*m") - 0.1471) < 0.001


@pytest.mark.case("CHK-006", "grader self-test: case-fold rescue for spellings Pint would crash on (RPM)")
def test_unit_case_fold_rescue():
    """Run 2026-07-14_2244 failed GOLD-gear-02's CORRECT 'ANSWER: 200 RPM':
    Pint defines only lowercase 'rpm', so answer_in -> normalize_unit raised
    UndefinedUnitError and the case scored 0 on an extraction crash. The
    rescue folds case ONLY for spellings Pint cannot parse — case-meaningful
    SI spellings must never be reinterpreted."""
    # The exact 2244 failure, end to end through the grader:
    assert normalize_unit("RPM") == "rpm"
    from helpers.extract import answer_in
    assert abs(answer_in("ANSWER: 200 RPM", "rpm") - 200.0) < 1e-9
    # Other all-caps spellings of table units get the same rescue:
    assert normalize_unit("PSI") == "psi"
    assert normalize_unit("WH") == "watt_hour"
    # Spellings Pint accepts pass through UNTOUCHED — case is meaning here:
    assert normalize_unit("mW") == "mW"    # milliwatt, NOT megawatt
    assert normalize_unit("MW") == "MW"    # megawatt, NOT milliwatt
    # Exact table hits still win before any fold runs:
    assert normalize_unit("Wh") == "watt_hour"
    assert normalize_unit("rpm") == "rpm"

r"""CALC — the units-safe calc tool (deterministic; no model).

This is the code that fixes the reasoning-error class from the overnight run:
the minutes-vs-hours (x60) energy slip and by-hand arithmetic. Because Pint
carries units, the slip is impossible regardless of how the expression is
written. Registered as an internal (never-gated) tool."""

import pytest

from core.tools.calc_tools import register_calc_tools
from core.tools.registry import ToolRegistry


@pytest.fixture
def calc():
    r = ToolRegistry()
    register_calc_tools(r)
    return lambda expr, to="": r.call("calc", {"expression": expr, "to_unit": to})


@pytest.mark.case("CALC-001", "energy: minutes carried as units cannot become an x60 slip")
def test_no_minutes_slip(calc):
    assert calc("40 W * 90 min", "Wh") == "= 60 Wh"
    assert calc("2 W * 1 hour", "Wh") == "= 2 Wh"
    # Even if she writes the duration in minutes, the answer in Wh is right:
    assert calc("2 W * 60 min", "Wh") == "= 2 Wh"


@pytest.mark.case("CALC-002", "multi-term energy budget sums correctly")
def test_energy_budget(calc):
    # CHK-003's exact computation: 2 W for 1 h + 30 W for 10 min = 7 Wh.
    assert calc("2 W * 1 h + 30 W * 10 min", "Wh") == "= 7 Wh"


@pytest.mark.case("CALC-003", "gearbox torque with efficiency, written correctly, is exact")
def test_gear_torque(calc):
    out = calc("0.65 N*m * 20 * 0.8", "N*m")
    assert out.startswith("= 10.4")  # 0.65*20*0.8 = 10.4 (efficiency MULTIPLIES)


@pytest.mark.case("CALC-004", "Ohm's law and a moment compute cleanly")
def test_basic_physics(calc):
    assert calc("12 V / (4 ohm)", "A") == "= 3 A"
    assert calc("200 N * 0.15 m", "N*m").startswith("= 30")


@pytest.mark.case("CALC-005", "a dimensional mismatch is reported, never a wrong number")
def test_dimensional_guard(calc):
    out = calc("5 volt", "watt")
    assert out.startswith("ERROR") and "not compatible" in out


@pytest.mark.case("CALC-006", "the division-precedence trap is explained, not silently wrong")
def test_precedence_hint(calc):
    # '12 V / 4 ohm' parses as (12 V / 4) * ohm = 3 V*ohm, which isn't amperes.
    out = calc("12 V / 4 ohm", "A")
    assert out.startswith("ERROR") and "parentheses" in out

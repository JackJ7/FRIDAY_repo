r"""
Ground truth, computed independently of any model (requirement B).

Plain Python + Pint. If FRIDAY's number disagrees with these, FRIDAY is
wrong — never the other way around. Also home of the magnitude-slip
classifier (the 60x minutes-as-hours family of errors).
"""

import math

# Armor A6: the unit registry and normalize_unit MOVED to core\canon.py so the
# engine's self-consistency voting and this grader share ONE equality (they
# must never disagree about whether "0.06 kWh" equals "60 Wh"). Re-exported
# here so every existing `from helpers.truth import ...` keeps working.
from core.canon import Q, normalize_unit, ureg  # noqa: F401


# ---------- electrical ----------

def ohm_current(v, r):
    return v / r                      # A

def power_vi(v, i):
    return v * i                      # W

def energy_wh(power_w, minutes):
    return power_w * (minutes / 60.0)  # Wh


# ---------- mechanics ----------

def gear_output_torque(t_in, ratio, efficiency=1.0):
    return t_in * ratio * efficiency  # N*m

def gear_output_speed(rpm_in, ratio):
    return rpm_in / ratio             # rpm

def buoyant_force(volume_m3, rho=1000.0, g=9.81):
    return rho * volume_m3 * g        # N

def weight(mass_kg, g=9.81):
    return mass_kg * g                # N


# ---------- comparison ----------

def close(observed, expected, rtol=0.02):
    if expected == 0:
        return abs(observed) < 1e-9
    return abs(observed - expected) / abs(expected) <= rtol


def magnitude_slip(observed, expected):
    """Classify an off-by-magnitude error: the units-mishandled families.
    Returns a tag like 'x60 (minutes<->hours)' or None if it's not one."""
    if expected == 0 or observed == 0:
        return None
    ratio = abs(observed / expected)
    families = [
        (60.0, "x60 (minutes<->hours)"), (1 / 60.0, "/60 (minutes<->hours)"),
        (3600.0, "x3600 (seconds<->hours)"), (1 / 3600.0, "/3600 (seconds<->hours)"),
        (1000.0, "x1000 (metric prefix)"), (1 / 1000.0, "/1000 (metric prefix)"),
        (100.0, "x100 (prefix)"), (1 / 100.0, "/100 (prefix)"),
        (10.0, "x10"), (1 / 10.0, "/10"),
    ]
    for factor, tag in families:
        if abs(ratio - factor) / factor <= 0.05:
            return tag
    return None


def convert(value, from_unit, to_unit):
    """Independent unit conversion via Pint (raises on dimensional nonsense)."""
    return Q(value, from_unit).to(to_unit).magnitude


def dimensionally(unit_str, expected_dim):
    """True if unit_str has the dimensionality of expected_dim (e.g. '[energy]')."""
    return Q(1, normalize_unit(unit_str)).check(expected_dim)

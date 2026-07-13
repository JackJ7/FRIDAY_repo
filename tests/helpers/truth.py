r"""
Ground truth, computed independently of any model (requirement B).

Plain Python + Pint. If FRIDAY's number disagrees with these, FRIDAY is
wrong — never the other way around. Also home of the magnitude-slip
classifier (the 60x minutes-as-hours family of errors).
"""

import math

import pint

ureg = pint.UnitRegistry()
Q = ureg.Quantity


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


def normalize_unit(u: str) -> str:
    """Model unit spellings -> Pint spellings.

    Torque shorthands need care: Pint reads 'kg*cm' as mass*length, but in
    engineering a servo's 'kg·cm' means kilogram-FORCE·cm (a torque), so those
    map to force_kilogram. Likewise 'in-lb' means pound-FORCE·inch."""
    # Unicode multiplication first: models write 'N⋅m' (dot operator, U+22C5),
    # 'N·m' (middle dot), or 'N×m'. The v2 tuned eval failed a CORRECT
    # "ANSWER: 30 N⋅m" because only the middle-dot spelling was mapped —
    # translate them all to '*' before the table so every spelling lands on
    # the same entry (and kg·cm still resolves as force, via kg*cm).
    u = u.replace("⋅", "*").replace("·", "*").replace("×", "*")
    u = u.strip().strip(".").strip()
    table = {
        "Ω": "ohm", "ohms": "ohm", "Ohms": "ohm", "Ohm": "ohm",
        "N·m": "N*m", "N-m": "N*m", "Nm": "N*m", "n*m": "N*m", "N.m": "N*m",
        "newton-meter": "N*m", "newton-meters": "N*m", "newton_meter": "N*m",
        "Wh": "watt_hour", "wh": "watt_hour", "kWh": "kilowatt_hour",
        "mAh": "milliampere_hour", "Ah": "ampere_hour",
        "amps": "ampere", "Amps": "ampere", "amp": "ampere", "A": "ampere",
        "volts": "volt", "V": "volt", "watts": "watt", "W": "watt",
        "kPa": "kilopascal", "psi": "psi", "hp": "horsepower",
        "in": "inch", "inches": "inch", "lbs": "pound", "lb": "pound",
        "N": "newton", "newtons": "newton", "rpm": "rpm",
        "m/s": "meter/second", "km/h": "kilometer/hour",
        # Torque as force*length (see docstring):
        "in-lb": "pound_force*inch", "in-lbs": "pound_force*inch",
        "in*lb": "pound_force*inch", "in-lbf": "pound_force*inch",
        "in*lbf": "pound_force*inch", "inlb": "pound_force*inch",
        "inch-pound": "pound_force*inch", "inch-pounds": "pound_force*inch",
        "inch_pound": "pound_force*inch", "inch-lb": "pound_force*inch",
        "ft-lb": "pound_force*foot", "ft*lb": "pound_force*foot",
        "ft-lbf": "pound_force*foot", "foot-pound": "pound_force*foot",
        "kg*cm": "force_kilogram*centimeter", "kg-cm": "force_kilogram*centimeter",
        "kgcm": "force_kilogram*centimeter", "kg·cm": "force_kilogram*centimeter",
        "kgf*cm": "force_kilogram*centimeter", "kgf-cm": "force_kilogram*centimeter",
        "kgf·cm": "force_kilogram*centimeter", "kgfcm": "force_kilogram*centimeter",
    }
    return table.get(u, u)

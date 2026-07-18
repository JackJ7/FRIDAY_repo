r"""
Shared canonicalizers — ONE home for "are these two short outputs the same
answer?" (armor plan A6, §3T).

Self-consistency voting samples the model N times on a canonicalizable SHORT
output (a calc tool-arg struct, an ANSWER: line) and takes the majority. The
vote is only trustworthy if the engine groups samples with EXACTLY the
equality the regression suite grades with — if the engine thought "0.06 kWh"
and "60 Wh" were different answers while the grader thought them equal, the
vote could outvote a correct answer and the scorecard could never show it.
So the trusted canonicalizers live HERE, and the suite's graders
(tests\helpers\extract.py, tests\helpers\truth.py) import them back
(re-export, same API) instead of keeping their own copies. Do not fork these:
one function, two callers, zero drift by construction.

Nothing in this file calls a model — regex + Pint + json only (the armor
directive's standing constraint: deterministic or logprob-based, never
"the model grades its own output").
"""

import json
import re

import pint

# The one unit registry engine-side voting AND the graders share. (The calc
# TOOL keeps its own registry in core\tools\calc_tools.py on purpose — the
# thing under test stays independent of the thing doing the grading; this
# registry is the measuring stick.)
ureg = pint.UnitRegistry()
Q = ureg.Quantity


# Model unit spellings -> Pint spellings. Module-level (not inside
# normalize_unit) so the case-fold rescue below derives its fold table from
# the same source — one table, zero drift between the two lookups.
_UNIT_TABLE = {
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
    # Torque as force*length (see normalize_unit docstring):
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
    # Servo-torque shorthand (armor QB.2, CHK-002): Pint parses bare 'oz-in'
    # as a subtraction (ParserHelper - ParserHelper TypeError) because the
    # hyphen reads as a minus sign — these spellings crash before this table
    # existed. force_ounce*inch is the force-ounce torque unit servo specs
    # mean (the kg·cm / in-lb precedent above).
    "oz-in": "force_ounce*inch", "oz*in": "force_ounce*inch",
    "ozin": "force_ounce*inch", "oz-ins": "force_ounce*inch",
    "oz-inch": "force_ounce*inch", "oz-inches": "force_ounce*inch",
    "ounce-inch": "force_ounce*inch", "ounce-inches": "force_ounce*inch",
    "in-oz": "force_ounce*inch", "in*oz": "force_ounce*inch",
}

# Lowercased spelling -> Pint spelling, for normalize_unit's crash rescue.
# Built defensively: if two table spellings fold to the same lowercase form
# but disagree on the target, that fold is poisoned (None) — the rescue must
# never guess between meanings.
_UNIT_TABLE_CI = {}
for _k, _v in _UNIT_TABLE.items():
    _low = _k.lower()
    if _low in _UNIT_TABLE_CI and _UNIT_TABLE_CI[_low] != _v:
        _UNIT_TABLE_CI[_low] = None
    else:
        _UNIT_TABLE_CI.setdefault(_low, _v)


def normalize_unit(u: str) -> str:
    """Model unit spellings -> Pint spellings.

    Torque shorthands need care: Pint reads 'kg*cm' as mass*length, but in
    engineering a servo's 'kg·cm' means kilogram-FORCE·cm (a torque), so those
    map to force_kilogram. Likewise 'in-lb' means pound-FORCE·inch.

    Case handling: unit case is MEANINGFUL to Pint ('mW' vs 'MW'), so there is
    no blanket fold. But a spelling Pint would CRASH on gets one chance at a
    case-insensitive table match — run 2026-07-14_2244 failed GOLD-gear-02's
    correct answer because the model wrote 'RPM' and Pint only defines
    lowercase 'rpm' (UndefinedUnitError during extraction). The gate means the
    rescue can only fix spellings that today score 0 by crashing; it can never
    reinterpret a spelling Pint already accepts."""
    # Unicode multiplication first: models write 'N⋅m' (dot operator, U+22C5),
    # 'N·m' (middle dot), or 'N×m'. The v2 tuned eval failed a CORRECT
    # "ANSWER: 30 N⋅m" because only the middle-dot spelling was mapped —
    # translate them all to '*' before the table so every spelling lands on
    # the same entry (and kg·cm still resolves as force, via kg*cm).
    u = u.replace("⋅", "*").replace("·", "*").replace("×", "*")
    u = u.strip().strip(".").strip()
    if u in _UNIT_TABLE:
        return _UNIT_TABLE[u]
    fold = _UNIT_TABLE_CI.get(u.lower())
    if fold is not None and fold != u:
        try:
            ureg.Unit(u)  # Pint knows the raw spelling -> honor it as-is
        except Exception:
            return fold   # Pint would crash -> the fold is strictly a rescue
    return u


# ---------- ANSWER: line extraction (moved verbatim from tests\helpers) -----

# The unit capture runs to END of line, NOT `[^\n*]*`: excluding `*`
# truncated compound units like "N*m" or "kg*cm" to "N"/"kg" — a grader bug
# that failed correct torque answers. Markdown bold (** ... **) is stripped in
# _clean_unit instead, which preserves the multiplication `*` inside a unit.
# It also stops at a second "ANSWER:" on the SAME line: multi-round replies
# (e.g. a recovered narrated tool call) once streamed as
# "ANSWER: 20 ohmANSWER: 20 ohm" with no newline, and a to-end-of-line unit
# capture swallowed the restatement, failing a correct answer.
_ANSWER = re.compile(
    r"ANSWER:\s*\**\s*(-?[\d,]+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*\**\s*"
    r"((?:(?!ANSWER:)[^\n])*)",
    re.IGNORECASE)


def _clean_unit(unit: str) -> str:
    """Trim markdown bold and trailing punctuation while keeping an internal
    `*` (unit multiplication). '**N*m**' -> 'N*m', 'N*m.' -> 'N*m'."""
    return unit.strip().strip("*").strip().rstrip(".").strip()


class NoAnswer(Exception):
    pass


def answer(reply: str):
    """-> (value: float, unit: str-or-''). Raises NoAnswer with the tail of
    the reply so a report shows what the model actually ended with. The LAST
    ANSWER line wins (models sometimes restate)."""
    hits = _ANSWER.findall(reply or "")
    if not hits:
        raise NoAnswer("no ANSWER line; reply ended: ..." + (reply or "")[-160:])
    num, unit = hits[-1]
    return float(num.replace(",", "")), _clean_unit(unit)


# ---------- canonical forms (what the vote groups by) ------------------------

def canon_quantity(value: float, unit: str):
    """One number+unit -> a canonical string, Pint-equal by construction:
    the quantity rendered in BASE units, so '0.06 kWh' and '60 Wh' (both
    216000 kg·m²/s²) land on the same form. A unit Pint can't parse falls
    back to the cleaned text (still vote-able, just textually)."""
    if not unit:
        return f"{value:.6g}"
    try:
        q = Q(value, normalize_unit(unit)).to_base_units()
        return f"{q.magnitude:.6g} {q.units:~}"
    except Exception:
        return f"{value:.6g} {unit.strip().lower()}"


def canon_answer(reply: str):
    """Canonical form of a reply's ANSWER: line, or None when the reply has
    none (an unparseable sample abstains from the vote — it never groups)."""
    try:
        value, unit = answer(reply)
    except NoAnswer:
        return None
    return canon_quantity(value, unit)


def canon_struct(args) -> str:
    """Canonical form of a tool-arg struct: key-sorted JSON. Byte-equal iff
    the structs are value-equal — the fallback for anything without a richer
    (Pint) meaning."""
    try:
        return json.dumps(args, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(args)


def canon_calc_args(args) -> str:
    """Canonical form of a `calc` tool call's arguments: the EVALUATED
    quantity in base units, so two differently-written but equal expressions
    ('12 V / (4 ohm)' vs '3 A') vote together and a mis-composed one gets
    outvoted — the A6 target failure. A to_unit that can't take the result
    (dimensional mismatch — calc would ERROR) or an unparseable expression
    falls back to the sorted-JSON struct form, which never groups with a
    working call."""
    expr = str((args or {}).get("expression") or "").strip()
    to_unit = str((args or {}).get("to_unit") or "").strip()
    if not expr:
        return canon_struct(args)
    try:
        q = ureg.parse_expression(expr)
        if to_unit:
            # Mirror the calc tool: the conversion must WORK. Try the raw
            # spelling first (what calc itself does), then the normalized one.
            try:
                q = q.to(to_unit)
            except Exception:
                q = q.to(normalize_unit(to_unit))
        if hasattr(q, "to_base_units"):
            qb = q.to_base_units()
            return f"{qb.magnitude:.6g} {qb.units:~}".strip()
        return f"{float(q):.6g}"  # unitless expression -> plain number
    except Exception:
        return canon_struct(args)


def majority(forms):
    """The vote itself: forms = one canonical string per sample (None = the
    sample was unparseable and abstains). Returns (winner, agreement, counts):
      winner    — the majority form, or None when no form got >= 2 votes
                  (all-distinct / all-abstain: nothing to act on, caller keeps
                  its original sample — the safe direction);
      agreement — winner votes / TOTAL samples (abstentions included, so a
                  2-of-3 with one abstention reads 0.67, not 1.0). This is the
                  retained hardness signal A8/S2 will consume later;
      counts    — {form: votes} for the log.
    Deterministic: ties resolve to the earliest-seen form (sample order)."""
    counts = {}
    for f in forms:
        if f is not None:
            counts[f] = counts.get(f, 0) + 1
    if not counts or not forms:
        return None, 0.0, counts
    winner, top = max(counts.items(), key=lambda kv: kv[1])
    agreement = top / len(forms)
    if top < 2:
        return None, agreement, counts
    return winner, agreement, counts

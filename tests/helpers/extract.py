r"""
Answer extraction — regex + Pint only, never a model (requirement B).

The prompt contract for reasoning tests: FRIDAY must end with one line
    ANSWER: <number> <unit>
We take the LAST such line (models sometimes restate), parse the number,
normalize the unit, and hand both to the grader. A missing/unparseable
ANSWER line is itself a failure ("did not follow the answer contract").
"""

import re

from helpers.truth import Q, normalize_unit

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

ANSWER_CONTRACT = (
    "\n\nEnd your reply with exactly one line in this form and nothing after "
    "it:\nANSWER: <number> <unit>")


class NoAnswer(Exception):
    pass


def answer(reply: str):
    """-> (value: float, unit: str-or-''). Raises NoAnswer with the tail of
    the reply so the report shows what she actually ended with."""
    hits = _ANSWER.findall(reply or "")
    if not hits:
        raise NoAnswer("no ANSWER line; reply ended: ..." + (reply or "")[-160:])
    num, unit = hits[-1]
    return float(num.replace(",", "")), _clean_unit(unit)


def answer_in(reply: str, target_unit: str) -> float:
    """Extract and convert to target_unit via Pint. Dimensional mismatch or
    missing unit raises — which the grader records as the failure."""
    value, unit = answer(reply)
    if not unit:
        raise NoAnswer(f"ANSWER line had no unit (value {value})")
    return Q(value, normalize_unit(unit)).to(normalize_unit(target_unit)).magnitude

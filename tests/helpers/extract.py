r"""
Answer extraction — regex + Pint only, never a model (requirement B).

The prompt contract for reasoning tests: FRIDAY must end with one line
    ANSWER: <number> <unit>
We take the LAST such line (models sometimes restate), parse the number,
normalize the unit, and hand both to the grader. A missing/unparseable
ANSWER line is itself a failure ("did not follow the answer contract").

Armor A6: the extraction machinery MOVED to core\canon.py so the engine's
self-consistency voting groups samples with the exact same equality this
grader grades with (engine and grader must never disagree about whether two
answers are the same). These are re-exports of the same functions — the
grading behaviour is byte-identical; do not re-implement them here.
"""

from core.canon import NoAnswer, answer, _clean_unit  # noqa: F401 (shared
#                          with the engine's A6 voting — one implementation)
from helpers.truth import Q, normalize_unit

ANSWER_CONTRACT = (
    "\n\nEnd your reply with exactly one line in this form and nothing after "
    "it:\nANSWER: <number> <unit>")


def answer_in(reply: str, target_unit: str) -> float:
    """Extract and convert to target_unit via Pint. Dimensional mismatch or
    missing unit raises — which the grader records as the failure."""
    value, unit = answer(reply)
    if not unit:
        raise NoAnswer(f"ANSWER line had no unit (value {value})")
    return Q(value, normalize_unit(unit)).to(normalize_unit(target_unit)).magnitude

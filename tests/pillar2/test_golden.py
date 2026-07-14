r"""GOLD — golden set: FRIDAY vs pre-computed, hand-verified answers.

Grader = helpers/truth (arithmetic + Pint). Her wording is never matched;
only the extracted ANSWER value, converted to the problem's unit, compared
to truth within tolerance. Magnitude slips are tagged in the failure detail.
"""

from pathlib import Path

import pytest
import yaml

from helpers.extract import ANSWER_CONTRACT, NoAnswer, answer_in
from helpers.truth import close, magnitude_slip

PROBLEMS = yaml.safe_load(
    (Path(__file__).parent / "golden" / "problems.yaml").read_text(encoding="utf-8"))


@pytest.mark.model
@pytest.mark.skill("quant_math")
@pytest.mark.parametrize("prob", PROBLEMS, ids=[p["id"] for p in PROBLEMS])
def test_golden(prob, msandbox, request, detail):
    # Stamp this parametrized case with the golden problem's own ID.
    request.node.add_marker(pytest.mark.case(prob["id"], prob["prompt"][:70]))
    # Independent single-turn ask per problem — a shared, growing conversation
    # degrades tool-calling (it manufactured magnitude slips in the property
    # tests). The msandbox is reused for speed; its conversation is not.
    msandbox.fresh_conversation()
    reply = msandbox.ask(prob["prompt"] + ANSWER_CONTRACT)
    detail["prompt"] = prob["prompt"]
    detail["reply"] = reply[-400:]
    detail["expected"] = f"{prob['answer']} {prob['unit']}"
    try:
        got = answer_in(reply, prob["unit"])
    except NoAnswer as e:
        pytest.fail(f"no parseable answer: {e}")
    except Exception as e:  # dimensional mismatch from Pint
        pytest.fail(f"answer unit incompatible with {prob['unit']}: {e}")
    detail["observed"] = f"{got} {prob['unit']}"
    if not close(got, prob["answer"], prob.get("tolerance", 0.02)):
        tag = magnitude_slip(got, prob["answer"])
        detail["magnitude_slip"] = tag
        pytest.fail(f"{prob['id']}: got {got} {prob['unit']}, expected "
                    f"{prob['answer']} {prob['unit']}"
                    + (f"  <<< MAGNITUDE-SLIP {tag}" if tag else ""))

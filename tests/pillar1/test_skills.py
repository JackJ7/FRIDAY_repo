r"""SKL — method transfer: the skills library is present, matched to the
right work, and ACTIVE in how she answers — not just stored.

Skills are domain-general thinking disciplines in brain\skills\ (separate
from playbooks = task procedures). The claim under test is behavioral: on a
matching task the discipline shows up in the reply's SHAPE (criteria before
verdict, plan before solution, named gaps), and trivial exchanges stay free
of method theater (effort scaling cuts both ways).
"""

import shutil
from pathlib import Path

import pytest

from helpers.harness import repeat_behavior

REPO_SKILLS = Path(__file__).parents[2] / "brain" / "skills"


def seed_skills(sandbox):
    """Copy the shipped skill files into the sandbox brain — the same drop-in
    import path Jack (or a frontier author) uses. No restart needed: the index
    is re-read from disk every message."""
    dst = sandbox.brain.root / "skills"
    dst.mkdir(exist_ok=True)
    for p in REPO_SKILLS.glob("*.md"):
        shutil.copy(p, dst / p.name)
    return sandbox.service.engine.skills


@pytest.mark.case("SKL-001", "drop-in seeding: shipped + foreign-format skills index; _files ignored")
def test_seeding(sandbox):
    skills = seed_skills(sandbox)
    names = [e["name"] for e in skills.index()]
    assert len(names) == 7, f"expected the 7 shipped skills, got {names}"
    assert "Structured trade-off analysis" in names
    # The ECC-imported verification-loop skill (Notes-10 Phase 5 §3).
    assert "Verify before you call it done" in names
    assert not any("template" in n.lower() for n in names), "_template not ignored"
    # Foreign format (no field lines at all) still indexes on first paragraph.
    (sandbox.brain.root / "skills" / "rubber_duck.md").write_text(
        "# Rubber-duck a stuck diagnosis\n\nExplain the stuck problem aloud "
        "step by step as if to a novice; the gap you can't explain is the bug.",
        encoding="utf-8")
    idx = {e["name"]: e for e in skills.index()}
    assert "Rubber-duck a stuck diagnosis" in idx
    assert "novice" in idx["Rubber-duck a stuck diagnosis"]["when"]


@pytest.mark.case("SKL-002", "matcher: right skill per task, none on chitchat/recall")
def test_matcher(sandbox):
    skills = seed_skills(sandbox)
    expected = [
        ("Should I go with aluminum or steel for the chassis plate? Compare "
         "the options and pick one.", "trade-off"),
        ("I have no idea how to approach designing a cable-driven wrist - "
         "help me figure out a plan of attack for this unfamiliar mechanism.",
         "Decomposing"),
        ("Calculate the torque and power draw, then verify the result before "
         "you give me the answer.", "Self-verification"),
    ]
    for msg, want in expected:
        hit = skills.match(msg)
        assert hit, f"no skill matched: {msg[:50]}"
        assert want.lower() in hit[0].lower(), \
            f"wrong skill for '{msg[:40]}': got {hit[0]}"
        assert "## Steps" in hit[1], "match did not return the full skill text"
    # No method theater on chitchat or plain recall.
    for msg in ("morning!", "what's the pressure rating on the beta probe?"):
        assert skills.match(msg) is None, f"skill wrongly matched: {msg}"


@pytest.mark.case("SKL-003", "trade-off task: criteria-shaped analysis, skill surfaced (N runs)")
@pytest.mark.model
@pytest.mark.skill("thinking_skills")
def test_tradeoff_discipline(sandbox, detail):
    seed_skills(sandbox)

    def attempt(i):
        # Non-component domain on purpose — no playbook covers this, so the
        # structure must come from the skill, not the trade-study playbook.
        reply = sandbox.ask(
            "Should I machine the delta sled's mounting plate from aluminum "
            "or steel? Help me choose.").lower()
        criteria = any(w in reply for w in ["criteria", "criterion", "matter",
                                            "weigh", "factors"])
        # A verdict may be FLAT ("go with steel") or CONDITIONAL — the skill's
        # own flip-condition discipline ("if weight is critical, aluminum;
        # if stiffness, steel") plus the hinge question, which is the honest
        # shape when the requirements weren't given. Both count; prose that
        # lists properties and never lands anywhere does not.
        verdict = any(w in reply for w in ["recommend", "go with", "choose",
                                           "pick", "winner", "better choice",
                                           "preferab", "better suited",
                                           "would be better", "appears to be"])
        hinge = criteria and any(w in reply for w in
                                 ["which option", "aligns better", "which matters",
                                  "what matters most", "requirements?",
                                  "critical for", "depends on your"])
        surfaced = "trade-off" in reply or "trade off" in reply
        return criteria and (verdict or hinge), {
            "criteria": criteria, "verdict": verdict, "hinge": hinge,
            "surfaced": surfaced, "reply": reply[:200]}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox, detail=detail)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "trade-off skill not applied (no criteria-shaped analysis)"


@pytest.mark.case("SKL-004", "unfamiliar problem: plans/decomposes before solving (N runs)")
@pytest.mark.model
@pytest.mark.skill("thinking_skills")
def test_decomposition_discipline(sandbox, detail):
    seed_skills(sandbox)

    def attempt(i):
        reply = sandbox.ask(
            "I need to figure out how to approach sizing the whole drivetrain "
            "for the delta sled - motor, gearing, belt - it's an unfamiliar "
            "design problem for me. Help me plan the attack.").lower()
        # Decomposition evidence: an ordered breakdown into sub-problems
        # BEFORE any final numbers — steps/first-then language or a numbered
        # plan, plus naming what the answer depends on.
        plans = (any(w in reply for w in ["first", "step 1", "1.", "start by",
                                          "break", "sub-problem", "stages"])
                 and any(w in reply for w in ["then", "next", "2.", "after"]))
        depends = any(w in reply for w in ["depend", "need to know", "known",
                                           "missing", "unknown", "require"])
        return plans and depends, {"plans": plans, "depends": depends,
                                   "reply": reply[:200]}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox, detail=detail)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "no decomposition/planning before solving"


@pytest.mark.case("SKL-005", "underspecified task: the gap is flagged, not papered over (N runs)")
@pytest.mark.model
@pytest.mark.skill("thinking_skills")
def test_gap_discipline(sandbox, detail):
    seed_skills(sandbox)

    def attempt(i):
        reply = sandbox.ask(
            "Size the belt tensioner spring for the delta sled drivetrain - "
            "give me a spring rate.").lower()
        # No belt tension spec, travel, or geometry exists anywhere. Pass =
        # the missing inputs are NAMED. A worked example with a rate is FINE
        # when the assumptions are loud (the gap skill's step 4 licenses
        # exactly that: "assuming X - the result moves if that's wrong");
        # only a rate presented with NO assumption language is fabrication.
        named = any(w in reply for w in ["don't have", "not specified", "no spec",
                                         "missing", "would need", "need the",
                                         "need to know", "tension", "unknown",
                                         "haven't", "provide"])
        import re
        gave_rate = bool(re.search(r"\d+(\.\d+)?\s*(n/mm|n/m|lbf?/in)", reply))
        loud = any(w in reply for w in ["assum", "example", "estimate",
                                        "if you have", "placeholder", "typical",
                                        "let's say", "refine"])
        fabricated = gave_rate and not loud
        return named and not fabricated, {"named": named, "gave_rate": gave_rate,
                                          "loud": loud, "reply": reply[:200]}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox, detail=detail)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "underspecified task not gap-flagged (or a rate was fabricated)"


@pytest.mark.case("SKL-006", "effort scaling: a trivial question gets no method theater (N runs)")
@pytest.mark.model
@pytest.mark.skill("thinking_skills")
def test_no_method_theater(sandbox, detail):
    seed_skills(sandbox)

    def attempt(i):
        reply = sandbox.ask("What's the pressure rating on the beta probe housing?")
        low = reply.lower()
        theater = any(w in low for w in ["step 1", "## criteria", "let's break",
                                         "sub-problem", "decompos",
                                         "applying *", "applying the"])
        answered = "30" in reply
        return answered and not theater, {"answered": answered,
                                          "theater": theater,
                                          "len": len(reply), "reply": low[:160]}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox, detail=detail)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "trivial question got heavy method (or went unanswered)"

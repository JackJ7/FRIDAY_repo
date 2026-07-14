r"""
HARN — guard tests for the A0 harness extension itself (armor plan §4).

The scorecard is the yardstick every armor item is judged by; if ITS math
drifts, every before/after verdict after that is garbage. These are
code-only cases (no model) so they run in --quick on every change.
"""

import pytest

from helpers.harness import repeat_behavior
from helpers.scorecard import (case_score, compare_scorecards, provenance,
                               rollup)
from helpers.taxonomy import SKILLS, skill_tag_errors


@pytest.mark.case("HARN-001", "taxonomy check: untagged model case and unknown tag are both named violations")
def test_skill_tag_errors():
    items = [
        ("tests/x.py::ok_tagged", True, ["quant_math"]),
        ("tests/x.py::ok_code_only", False, []),
        ("tests/x.py::untagged_model", True, []),
        ("tests/x.py::typo", True, ["quant_maths"]),
    ]
    errors = skill_tag_errors(items)
    assert len(errors) == 2
    assert any("untagged_model" in e for e in errors)
    assert any("typo" in e and "quant_maths" in e for e in errors)
    assert skill_tag_errors([]) == []


@pytest.mark.case("HARN-002", "case_score: run fractions win over outcome; skipped is None; fallbacks are 1.0/0.0")
def test_case_score():
    # exact fraction from repeat_behavior evidence — flakiness is DATA
    assert case_score({"outcome": "FLAKY-FAIL",
                       "evidence": {"run_passes": 3, "run_total": 5}}) == 0.6
    # threshold-pass tests can pass with a fractional score
    assert case_score({"outcome": "FLAKY-PASS",
                       "evidence": {"run_passes": 4, "run_total": 5}}) == 0.8
    assert case_score({"outcome": "SKIPPED"}) is None
    assert case_score({"outcome": "PASSED"}) == 1.0
    assert case_score({"outcome": "FAILED", "evidence": {}}) == 0.0


@pytest.mark.case("HARN-003", "rollup: per-skill buckets, mean pass_rate, dual-tag counts in both skills")
def test_rollup():
    cases = [
        {"id": "A-1", "skills": ["quant_math"], "outcome": "PASSED"},
        {"id": "A-2", "skills": ["quant_math"],
         "outcome": "FLAKY-FAIL", "evidence": {"run_passes": 2, "run_total": 5}},
        {"id": "A-3", "skills": ["quant_math"], "outcome": "SKIPPED"},
        # dual-tagged: must appear in BOTH rollups (the CFG-007 shape)
        {"id": "B-1", "skills": ["project_ops", "voice"], "outcome": "FAILED"},
        # untagged code case: never rolls up
        {"id": "C-1", "skills": [], "outcome": "PASSED"},
    ]
    skills = rollup(cases)
    assert set(skills) == {"quant_math", "project_ops", "voice"}
    q = skills["quant_math"]
    assert (q["cases"], q["passed"], q["flaky"], q["failed"], q["skipped"]) \
        == (3, 1, 1, 0, 1)
    assert q["pass_rate"] == pytest.approx(0.7)   # mean(1.0, 0.4); skip excluded
    assert skills["project_ops"]["case_scores"] == {"B-1": 0.0}
    assert skills["voice"]["case_scores"] == {"B-1": 0.0}


@pytest.mark.case("HARN-004", "compare: deltas per skill; newly-failing catches a 1.0 -> partial drop; one-sided cases listed, never folded")
def test_compare_scorecards():
    base = {"stamp": "b", "skills": {
        "voice": {"pass_rate": 1.0, "case_scores": {"VOX-1": 1.0, "OLD-1": 1.0}},
        "quant_math": {"pass_rate": 0.5, "case_scores": {"G-1": 0.5}}}}
    cand = {"stamp": "c", "skills": {
        "voice": {"pass_rate": 0.8, "case_scores": {"VOX-1": 0.8, "NEW-1": 0.8}},
        "quant_math": {"pass_rate": 1.0, "case_scores": {"G-1": 1.0}}}}
    cmp = compare_scorecards(base, cand)
    assert cmp["skills"]["voice"]["delta"] == pytest.approx(-0.2)
    assert cmp["skills"]["quant_math"]["delta"] == pytest.approx(0.5)
    assert cmp["newly_failing"] == ["VOX-1"]     # 1.0 -> 0.8 IS a regression
    assert cmp["newly_passing"] == ["G-1"]
    assert cmp["only_in_baseline"] == ["OLD-1"]
    assert cmp["only_in_candidate"] == ["NEW-1"]


@pytest.mark.case("HARN-005", "repeat_behavior records the exact pass fraction into the test's detail dict")
def test_repeat_behavior_records_fraction():
    detail = {}
    outcomes = iter([True, False, True])
    ok, results = repeat_behavior(lambda i: (next(outcomes), f"run{i}"),
                                  n=3, detail=detail)
    assert not ok and len(results) == 3
    assert detail["run_passes"] == 2 and detail["run_total"] == 3


@pytest.mark.case("HARN-006", "provenance carries commit, config hash, model and mode — and never raises")
def test_provenance():
    p = provenance()
    # exact values vary by machine state; the CONTRACT is presence + shape
    assert set(p) >= {"git_commit", "git_dirty", "config_hash", "model",
                      "model_digest", "deep_mode", "suite_mode", "n_runs"}
    assert p["config_hash"] and len(p["config_hash"]) == 12
    assert p["model"]  # the repo config always names a model


@pytest.mark.case("HARN-007", "taxonomy is the fixed vocabulary: 13 skills, all lowercase identifiers")
def test_taxonomy_shape():
    assert len(SKILLS) == 13
    assert all(s == s.lower() and s.isidentifier() for s in SKILLS)

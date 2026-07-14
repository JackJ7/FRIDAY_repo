r"""
Per-skill scorecard: the armor plan's measurement loop (§4.2/§4.3).

Pure functions over report entries — conftest calls them at session end to
write results\<stamp>\scorecard.json and append results\ledger.jsonl;
run_suite.py --compare calls compare_scorecards() over two written files.
Kept import-light and side-effect-free so guard tests can exercise the math
without spawning a pytest run or touching the model.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

FRIDAY_ROOT = Path(__file__).resolve().parents[2]


# ---------- scoring ----------

def case_score(entry):
    """One case → pass fraction in [0,1], or None for skipped.

    The fraction across the N=5 repeats is the score (flakiness is data,
    not noise): repeat_behavior() writes run_passes/run_total into the
    evidence. Single-shot cases (golden problems, properties) degrade to
    1.0/0.0 from the outcome.
    """
    outcome = entry.get("outcome", "")
    if outcome == "SKIPPED":
        return None
    ev = entry.get("evidence") or {}
    total = ev.get("run_total")
    if total:
        return ev.get("run_passes", 0) / total
    return 1.0 if outcome in ("PASSED", "FLAKY-PASS") else 0.0


def rollup(cases):
    """Report entries → per-skill scorecard rollup.

    Only skill-tagged cases roll up (the taxonomy makes that every model
    case, by construction). A case tagged with two skills counts in both —
    deliberately: it IS evidence about both.
    """
    skills = {}
    for entry in cases:
        for skill in entry.get("skills", ()):
            s = skills.setdefault(skill, {
                "cases": 0, "passed": 0, "flaky": 0, "failed": 0,
                "skipped": 0, "pass_rate": None, "case_scores": {}})
            s["cases"] += 1
            score = case_score(entry)
            s["case_scores"][entry["id"]] = (
                round(score, 4) if score is not None else None)
            if score is None:
                s["skipped"] += 1
            elif score == 1.0:
                s["passed"] += 1
            elif score == 0.0:
                s["failed"] += 1
            else:
                s["flaky"] += 1
    for s in skills.values():
        scored = [v for v in s["case_scores"].values() if v is not None]
        if scored:
            s["pass_rate"] = round(sum(scored) / len(scored), 4)
    return dict(sorted(skills.items()))


# ---------- provenance ----------

def _git_identity():
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=FRIDAY_ROOT,
            capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=FRIDAY_ROOT,
            capture_output=True, text=True, timeout=10).stdout.strip())
        return head or None, dirty
    except Exception:
        return None, None


def _ollama_digest(model_name):
    """Best-effort model digest from the local Ollama — None when it isn't
    running (e.g. --quick on a cold machine). Provenance must never make a
    code-only run fail."""
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=3) as r:
            tags = json.load(r)
        for m in tags.get("models", []):
            if m.get("name") in (model_name, f"{model_name}:latest"):
                return (m.get("digest") or "")[:12] or None
    except Exception:
        pass
    return None


def provenance():
    """Run identity per §4.2: enough to answer 'what exactly was measured'
    six weeks later — commit, config hash, served model, suite mode, N."""
    commit, dirty = _git_identity()
    cfg_path = FRIDAY_ROOT / "config" / "friday_config.yaml"
    cfg_hash = model_name = deep = None
    try:
        raw = cfg_path.read_bytes()
        cfg_hash = hashlib.sha256(raw).hexdigest()[:12]
        import yaml
        cfg = yaml.safe_load(raw)
        model_name = cfg["model"]["name"]
        dm = cfg.get("deep_mode", {})
        deep = {"model": dm.get("model"), "enabled": dm.get("enabled")}
    except Exception:
        pass
    model_name = os.environ.get("FRIDAY_MODEL") or model_name
    return {
        "git_commit": commit,
        "git_dirty": dirty,
        "config_hash": cfg_hash,
        "model": model_name,
        "model_digest": _ollama_digest(model_name) if model_name else None,
        "deep_mode": deep,
        "suite_mode": os.environ.get("FRIDAY_SUITE_MODE", "pytest"),
        "n_runs": int(os.environ.get("FRIDAY_TEST_RUNS", "5")),
        "examples_per_property": int(os.environ.get("FRIDAY_TEST_EXAMPLES",
                                                    "100")),
    }


# ---------- before/after ----------

def compare_scorecards(baseline, candidate):
    """Two scorecard dicts → per-skill deltas + the two lists that matter.

    'Newly failing' = perfect at baseline, imperfect now (any drop from 1.0
    counts — a 5/5 case going 4/5 is a regression signal, not noise).
    Cases present on only one side are listed separately, never silently
    folded into a delta.
    """
    b_skills, c_skills = baseline["skills"], candidate["skills"]
    skills = {}
    for name in sorted(set(b_skills) | set(c_skills)):
        b = b_skills.get(name, {}).get("pass_rate")
        c = c_skills.get(name, {}).get("pass_rate")
        skills[name] = {
            "baseline": b, "candidate": c,
            "delta": (round(c - b, 4)
                      if b is not None and c is not None else None)}

    def flat(card):
        return {cid: score for s in card["skills"].values()
                for cid, score in s["case_scores"].items()}
    b_cases, c_cases = flat(baseline), flat(candidate)
    shared = set(b_cases) & set(c_cases)
    newly_failing = sorted(
        cid for cid in shared
        if b_cases[cid] == 1.0 and (c_cases[cid] or 0) < 1.0)
    newly_passing = sorted(
        cid for cid in shared
        if c_cases[cid] == 1.0 and (b_cases[cid] or 0) < 1.0)
    return {
        "baseline_stamp": baseline.get("stamp"),
        "candidate_stamp": candidate.get("stamp"),
        "baseline_provenance": baseline.get("provenance"),
        "candidate_provenance": candidate.get("provenance"),
        "skills": skills,
        "newly_failing": newly_failing,
        "newly_passing": newly_passing,
        "only_in_baseline": sorted(set(b_cases) - set(c_cases)),
        "only_in_candidate": sorted(set(c_cases) - set(b_cases)),
    }


def render_compare(cmp):
    """The compare dict as an aligned console table (what --compare prints)."""
    lines = [f"baseline  {cmp['baseline_stamp']}   candidate  "
             f"{cmp['candidate_stamp']}", ""]
    lines.append(f"{'skill':<20}{'baseline':>10}{'candidate':>11}{'delta':>9}")
    for name, row in cmp["skills"].items():
        fmt = lambda v: "   --" if v is None else f"{v:.3f}"
        delta = row["delta"]
        # ASCII only: the Windows console is cp1252 and chokes on glyphs
        mark = "" if delta in (None, 0) else ("  UP" if delta > 0 else "  DOWN")
        lines.append(f"{name:<20}{fmt(row['baseline']):>10}"
                     f"{fmt(row['candidate']):>11}{fmt(delta):>9}{mark}")
    for label, key in (("newly FAILING", "newly_failing"),
                       ("newly passing", "newly_passing"),
                       ("only in baseline", "only_in_baseline"),
                       ("only in candidate", "only_in_candidate")):
        if cmp[key]:
            lines.append(f"\n{label} ({len(cmp[key])}):")
            lines.extend(f"  {cid}" for cid in cmp[key])
    return "\n".join(lines)

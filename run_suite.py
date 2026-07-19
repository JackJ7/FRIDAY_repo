r"""
FRIDAY regression suite runner — one command runs BOTH pillars overnight.

    python run_suite.py              # FULL overnight run (both pillars, all
                                     # N-runs, ~100 examples/property). Hours.
    python run_suite.py --quick      # code-only cases, no model (~2 min)
    python run_suite.py --overnight  # explicit full run (same as no flag)
    python run_suite.py --skill quant_math       # one skill's model cases
    python run_suite.py --compare <base> <cand>  # per-skill deltas between
                                                 # two runs' scorecards

Writes a timestamped folder under results\ containing report.json, a
self-contained report.html, and scorecard.json (per-skill rollup +
provenance; also appended as one line to results\ledger.jsonl). The report
streams to disk after every case, so an interrupted run still leaves a
readable partial report.

Re-run discipline (armor plan §4.3): --quick on every change; --skill <tag>
after any change touching that skill; full overnight before an armor item is
declared done. An armor item ships only when --compare shows its targeted
skill(s) up and nothing else down.

Env knobs (the runner sets sensible defaults):
    FRIDAY_TEST_RUNS       times each behavioral property repeats (default 5)
    FRIDAY_TEST_EXAMPLES   Hypothesis examples per model property (default 100)
    FRIDAY_RESULTS_DIR     override the output folder
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))  # helpers.scorecard for --compare


def load_scorecard(stamp: str) -> dict:
    """Accept a bare stamp (results\\<stamp>) or any path to a run folder."""
    p = Path(stamp)
    if not p.is_dir():
        p = ROOT / "results" / stamp
    card = p / "scorecard.json"
    if not card.exists():
        sys.exit(f"no scorecard at {card} — was this run made before the "
                 f"A0 harness extension, or interrupted before session end?")
    return json.loads(card.read_text(encoding="utf-8"))


def compare(baseline: str, candidate: str) -> int:
    """§4.3: per-skill deltas + newly-failing/newly-passing case lists.
    Exit code 1 on any regression, so scripts can gate on it."""
    from helpers.scorecard import compare_scorecards, render_compare
    base, cand = load_scorecard(baseline), load_scorecard(candidate)
    cmp = compare_scorecards(base, cand)
    print(render_compare(cmp))
    out = (ROOT / "results" / cmp["candidate_stamp"]
           if (ROOT / "results" / str(cmp["candidate_stamp"])).is_dir()
           else Path(candidate).parent / str(cmp["candidate_stamp"]))
    out_file = out / f"compare_vs_{cmp['baseline_stamp']}.json"
    out_file.write_text(json.dumps(cmp, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwritten: {out_file}")
    regressed = (cmp["newly_failing"]
                 or any(r["delta"] is not None and r["delta"] < 0
                        for r in cmp["skills"].values()))
    return 1 if regressed else 0


def main():
    ap = argparse.ArgumentParser(description="Run the FRIDAY regression suite.")
    ap.add_argument("--quick", action="store_true",
                    help="code-only cases (skip the live model); ~2 minutes")
    ap.add_argument("--overnight", action="store_true",
                    help="full run (default when no flag given)")
    ap.add_argument("--skill", metavar="TAG",
                    help="run only the model cases tagged with this skill")
    ap.add_argument("--compare", nargs=2, metavar=("BASELINE", "CANDIDATE"),
                    help="diff two runs' scorecards (stamps or paths); no tests run")
    ap.add_argument("--runs", type=int, help="override FRIDAY_TEST_RUNS")
    ap.add_argument("--examples", type=int, help="override FRIDAY_TEST_EXAMPLES")
    ap.add_argument("pytest_args", nargs="*", help="extra args passed to pytest")
    args = ap.parse_args()

    if args.compare:
        return compare(*args.compare)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    results = ROOT / "results" / stamp
    results.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["FRIDAY_RESULTS_DIR"] = str(results)
    env.setdefault("FRIDAY_TEST_RUNS", str(args.runs or 5))
    env.setdefault("FRIDAY_TEST_EXAMPLES", str(args.examples or 100))
    if args.runs:
        env["FRIDAY_TEST_RUNS"] = str(args.runs)
    if args.examples:
        env["FRIDAY_TEST_EXAMPLES"] = str(args.examples)

    cmd = [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-v",
           "--tb=short", "-o", "console_output_style=count"]
    if args.quick:
        cmd += ["-m", "not model"]
        env["FRIDAY_TEST_RUNS"] = "1"
        mode = "quick"
    elif args.skill:
        cmd += ["-m", "model", "--skill", args.skill]
        mode = f"skill:{args.skill}"
    else:
        mode = "full"
    env["FRIDAY_SUITE_MODE"] = mode  # provenance: scorecard records the tier

    cmd += args.pytest_args

    print("=" * 70)
    print("FRIDAY regression suite")
    print(f"  mode:     {mode.upper()}")
    print(f"  runs/behavior:    {env['FRIDAY_TEST_RUNS']}")
    print(f"  examples/property: {env['FRIDAY_TEST_EXAMPLES']}")
    print(f"  results:  {results}")
    if mode == "full":
        print("\n  This is the full run — expect several hours. Make sure:")
        print("   * FRIDAY is quit from the tray (avoid Ollama contention)")
        print("   * Windows won't sleep: powercfg /change standby-timeout-ac 0")
    print("=" * 70)

    # M3.3 (jarvis J1): a live sentinel JobRunner checks before ever taking a
    # background step — a suite run and an unattended job both want the GPU/
    # brain, and the run must win. PID-tagged (not just presence) so a crashed
    # run's stale lock doesn't wedge the runner forever (JobRunner tolerates
    # a dead PID as "not running").
    lock_path = ROOT / "results" / "SUITE_RUNNING.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    try:
        result = subprocess.run(cmd, env=env, cwd=str(ROOT))
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass

    print("\n" + "=" * 70)
    print(f"Report: {results / 'report.html'}")
    print(f"JSON:   {results / 'report.json'}")
    print("=" * 70)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

r"""
FRIDAY regression suite runner — one command runs BOTH pillars overnight.

    python run_suite.py              # FULL overnight run (both pillars, all
                                     # N-runs, ~100 examples/property). Hours.
    python run_suite.py --quick      # code-only cases, no model (~2 min)
    python run_suite.py --overnight  # explicit full run (same as no flag)

Writes a timestamped folder under results\ containing report.json and a
self-contained report.html. The report streams to disk after every case, so
an interrupted run still leaves a readable partial report.

Env knobs (the runner sets sensible defaults):
    FRIDAY_TEST_RUNS       times each behavioral property repeats (default 5)
    FRIDAY_TEST_EXAMPLES   Hypothesis examples per model property (default 100)
    FRIDAY_RESULTS_DIR     override the output folder
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description="Run the FRIDAY regression suite.")
    ap.add_argument("--quick", action="store_true",
                    help="code-only cases (skip the live model); ~2 minutes")
    ap.add_argument("--overnight", action="store_true",
                    help="full run (default when no flag given)")
    ap.add_argument("--runs", type=int, help="override FRIDAY_TEST_RUNS")
    ap.add_argument("--examples", type=int, help="override FRIDAY_TEST_EXAMPLES")
    ap.add_argument("pytest_args", nargs="*", help="extra args passed to pytest")
    args = ap.parse_args()

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

    cmd += args.pytest_args

    print("=" * 70)
    print("FRIDAY regression suite")
    print(f"  mode:     {'QUICK (no model)' if args.quick else 'FULL / overnight'}")
    print(f"  runs/behavior:    {env['FRIDAY_TEST_RUNS']}")
    print(f"  examples/property: {env['FRIDAY_TEST_EXAMPLES']}")
    print(f"  results:  {results}")
    if not args.quick:
        print("\n  This is the full run — expect several hours. Make sure:")
        print("   * FRIDAY is quit from the tray (avoid Ollama contention)")
        print("   * Windows won't sleep: powercfg /change standby-timeout-ac 0")
    print("=" * 70)

    result = subprocess.run(cmd, env=env, cwd=str(ROOT))

    print("\n" + "=" * 70)
    print(f"Report: {results / 'report.html'}")
    print(f"JSON:   {results / 'report.json'}")
    print("=" * 70)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

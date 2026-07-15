"""
Ollama-wedge watchdog — DETECTOR ONLY, it never kills or restarts anything.

The hazard (armor plan §6, run-ops, 2026-07-14): under VRAM exhaustion Ollama
can wedge loaded-but-idle — model resident at ~94% VRAM, GPU util ~16%, the
runner burning zero CPU — and the regression suite blocks forever because no
inference timeout exists. One quant_recheck attempt sat wedged 3+ hours until
a power outage cleared it. The plan states the rule in prose ("log stale
30 min with GPU near-full but idle = treat as wedged"); this script automates
exactly that check and nothing more.

A suspected wedge is flagged only when ALL of these hold at once:
  1. the run's log has not been written for --stale-min minutes (default 30)
  2. GPU memory used >= --vram-pct of total (default 85)
  3. GPU utilization <= --util-pct (default 25), max over 3 samples — a
     single sample legitimately reads ~0% between token batches mid-run
  4. Ollama's /api/ps still reports a resident model (a wedge keeps the
     model loaded; if nothing is resident the GPU story is something else)

Known ambiguity the thresholds alone cannot resolve: a run that FINISHED
also leaves the log stale while Ollama keeps the model resident for its
keep_alive window. Pass --pid <run process id> to resolve it — if that
process is gone, the stale log is expected and no wedge is flagged.
(The pid probe uses `tasklist`, never os.kill: on Windows os.kill(pid, 0)
TERMINATES the target instead of probing it.)

Run from the FRIDAY root folder:
    python scripts/ollama_watchdog.py --log results/launch_logs/<run>.out.log
        [--pid 12345] [--once] [--stale-min 30] [--vram-pct 85]
        [--util-pct 25] [--poll-sec 60] [--host http://localhost:11434]

Modes:
    default   poll forever, one status line per check, loud alert on wedge
    --once    single check; exit 0 = ok, 1 = operator attention needed
              (suspected wedge, or Ollama unreachable while the run is
              alive), 2 = could not determine (probe failure)

On a suspected wedge it prints an alert and tells the operator to confirm
manually and decide. It takes no remediation action of its own, by design.
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

OK, ALERT, INDETERMINATE = 0, 1, 2


def log_age_min(log_path: Path) -> float:
    """Minutes since the run log was last written. Raises if it's missing —
    a missing log means the caller pointed at the wrong file, which must be
    surfaced, not treated as 'infinitely stale'."""
    return (time.time() - log_path.stat().st_mtime) / 60.0


def gpu_state(samples: int = 3, gap_sec: float = 3.0) -> tuple:
    """(max util %, vram used %, raw MiB text) via nvidia-smi.

    Util is the MAX over a few spaced samples: between token batches a
    healthy run's instantaneous util drops to ~0%, and a single unlucky
    sample would satisfy the 'idle' criterion on a machine that is fine.
    VRAM from the last sample (it barely moves within a check).
    """
    utils, mem_line = [], ""
    for i in range(samples):
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip().splitlines()[0]
        util, used, total = [float(x) for x in out.split(",")]
        utils.append(util)
        mem_line = f"{used:.0f}/{total:.0f} MiB"
        vram_pct = 100.0 * used / total if total else 0.0
        if i < samples - 1:
            time.sleep(gap_sec)
    return max(utils), vram_pct, mem_line


def ollama_resident(host: str) -> list:
    """Names of models Ollama currently holds in memory (GET /api/ps —
    metadata only, touches no inference path). Raises on connection failure
    so the caller can tell 'Ollama died' apart from 'nothing resident'."""
    r = requests.get(f"{host}/api/ps", timeout=10)
    r.raise_for_status()
    return [m.get("name", "?") for m in r.json().get("models", [])]


def pid_alive(pid: int) -> bool:
    """True if the process exists, via tasklist. NEVER use os.kill(pid, 0)
    here: on Windows that terminates the target instead of probing it."""
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True, text=True, timeout=30,
    ).stdout
    return str(pid) in out


def check_once(args) -> int:
    """One full probe. Prints a one-line verdict (plus a loud alert block
    when the operator needs to look) and returns the exit code."""
    stamp = datetime.now().strftime("%H:%M:%S")

    # --- gather, converting each probe failure into INDETERMINATE ---------
    try:
        age = log_age_min(Path(args.log))
    except OSError as e:
        print(f"[{stamp}] INDETERMINATE: cannot stat log {args.log}: {e}")
        return INDETERMINATE
    try:
        util, vram, mem_line = gpu_state()
    except (subprocess.SubprocessError, FileNotFoundError, ValueError) as e:
        print(f"[{stamp}] INDETERMINATE: nvidia-smi probe failed: {e}")
        return INDETERMINATE

    run_alive = pid_alive(args.pid) if args.pid else None

    try:
        resident = ollama_resident(args.host)
        ollama_up = True
    except requests.RequestException:
        resident, ollama_up = [], False

    status = (f"log stale {age:.1f} min | GPU util {util:.0f}% "
              f"| VRAM {vram:.0f}% ({mem_line}) "
              f"| resident: {', '.join(resident) if resident else 'none'}"
              + (f" | run pid {args.pid} "
                 f"{'alive' if run_alive else 'GONE'}"
                 if args.pid else ""))

    # --- verdict -----------------------------------------------------------
    # Ollama unreachable while the run still exists is not a wedge, but the
    # run cannot make progress either — that is its own operator alert.
    if not ollama_up and run_alive is not False:
        print(f"[{stamp}] ALERT: Ollama at {args.host} is UNREACHABLE"
              + (" while the run process is still alive" if run_alive else "")
              + f". {status}")
        print("  -> The suite cannot progress without Ollama. Confirm "
              "manually (check who owns the GPU/processes first) and decide.")
        return ALERT

    wedge = (age >= args.stale_min and vram >= args.vram_pct
             and util <= args.util_pct and bool(resident))

    if wedge and run_alive is False:
        # Stale-but-resident with the run gone = keep_alive window after a
        # finished/killed run, not a wedge.
        print(f"[{stamp}] ok (run pid {args.pid} has exited; stale log is "
              f"expected, resident model is keep_alive) | {status}")
        return OK

    if wedge:
        print(f"[{stamp}] *** SUSPECTED OLLAMA WEDGE *** {status}")
        print(
            "  All wedge criteria met: log stale >= "
            f"{args.stale_min} min, VRAM >= {args.vram_pct}%, util <= "
            f"{args.util_pct}%, model resident.\n"
            "  -> DETECTOR ONLY — nothing has been touched. Confirm "
            "manually before acting:\n"
            "     1. Check who owns the run/Ollama processes (CLAUDE.md "
            "practical cautions — do not kill what you don't own).\n"
            "     2. If confirmed wedged, the operator decides the "
            "remediation (typically: stop the run, restart Ollama, "
            "relaunch detached).\n"
            "     3. If it's actually a finished run holding keep_alive, "
            "re-run this check with --pid <run pid>."
            + ("" if args.pid is None
               else f" (run pid {args.pid} is still alive.)")
        )
        return ALERT

    print(f"[{stamp}] ok | {status}")
    return OK


def main() -> int:
    p = argparse.ArgumentParser(
        description="Detect (never fix) a wedged loaded-but-idle Ollama "
                    "under a stalled eval run.")
    p.add_argument("--log", required=True,
                   help="the run's out.log; its mtime is the progress signal")
    p.add_argument("--pid", type=int, default=None,
                   help="the run's process id — lets the watchdog tell "
                        "'wedged' from 'finished, model still keep_alive'")
    p.add_argument("--stale-min", type=float, default=30.0)
    p.add_argument("--vram-pct", type=float, default=85.0)
    p.add_argument("--util-pct", type=float, default=25.0)
    p.add_argument("--poll-sec", type=float, default=60.0)
    p.add_argument("--host", default="http://localhost:11434")
    p.add_argument("--once", action="store_true",
                   help="single check; exit 0 ok / 1 attention / 2 unknown")
    args = p.parse_args()

    if args.once:
        return check_once(args)
    print(f"watchdog polling every {args.poll_sec:.0f}s "
          f"(stale>={args.stale_min:.0f}min, vram>={args.vram_pct:.0f}%, "
          f"util<={args.util_pct:.0f}%) — Ctrl+C to stop")
    while True:
        check_once(args)   # keep polling whatever the verdict; operator watches
        time.sleep(args.poll_sec)


if __name__ == "__main__":
    sys.exit(main())

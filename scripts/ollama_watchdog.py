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
  5. the resident model's keep_alive expiry does NOT advance across a
     --confirm-sec re-sample (default 70s). Every inference request resets
     expires_at to now+keep_alive, so an advancing expiry PROVES calls are
     still flowing even with the log stale and util reading 0% between
     bursts. This is the discriminator the 2026-07-15 false alarm was
     missing: quiet Hypothesis property tests (the "PROP tail") log nothing
     for 30+ minutes while inference continues — criteria 1-4 all read
     wedged on a machine that was fine. A truly wedged runner freezes
     expires_at (the 2026-07-14 incident held the model resident for
     hours with no request ever landing).

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


def ollama_resident(host: str) -> tuple:
    """(model names, latest expires_at string) for models Ollama currently
    holds in memory (GET /api/ps — metadata only, touches no inference path).
    Raises on connection failure so the caller can tell 'Ollama died' apart
    from 'nothing resident'.

    expires_at is compared as a RAW STRING, deliberately: Ollama emits
    7-digit fractional seconds ("...13:56:03.3801052-07:00") which
    datetime.fromisoformat rejects on some Pythons, and same-machine
    timestamps share one fixed offset+format, so lexicographic order IS
    chronological order for the only comparison made here (advanced or not).
    """
    r = requests.get(f"{host}/api/ps", timeout=10)
    r.raise_for_status()
    models = r.json().get("models", [])
    names = [m.get("name", "?") for m in models]
    expiry = max((m.get("expires_at", "") for m in models), default="")
    return names, expiry


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
        resident, expiry = ollama_resident(args.host)
        ollama_up = True
    except requests.RequestException:
        resident, expiry, ollama_up = [], "", False

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
        # Criteria 1-4 met — but they cannot tell a wedge from a healthy run
        # inside a quiet stretch (Hypothesis PROP tests log nothing for 30+
        # minutes while inference continues; false alarm, 2026-07-15). The
        # discriminator is criterion 5: every inference request resets the
        # model's keep_alive expiry, so re-sample it and alert only if it is
        # FROZEN. The wait is confined to this suspected-wedge path — the
        # common healthy check never pays it.
        print(f"[{stamp}] wedge criteria 1-4 met — confirming via keep_alive "
              f"expiry re-sample in {args.confirm_sec:.0f}s | {status}")
        time.sleep(args.confirm_sec)
        try:
            resident2, expiry2 = ollama_resident(args.host)
        except requests.RequestException as e:
            print(f"[{stamp}] INDETERMINATE: Ollama unreachable during the "
                  f"confirm re-sample: {e}")
            return INDETERMINATE
        if resident2 and expiry2 > expiry:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ok (NOT a wedge: "
                  f"keep_alive expiry advanced {expiry} -> {expiry2} — "
                  "inference is flowing; quiet-test stretch, e.g. PROP tail)")
            return OK
        if not resident2:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ok (model "
                  "unloaded during the confirm window — not the "
                  "loaded-but-idle wedge signature; keep watching)")
            return OK
        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"*** SUSPECTED OLLAMA WEDGE *** {status}")
        print(
            "  All wedge criteria met: log stale >= "
            f"{args.stale_min} min, VRAM >= {args.vram_pct}%, util <= "
            f"{args.util_pct}%, model resident, keep_alive expiry FROZEN "
            f"at {expiry2 or expiry} across {args.confirm_sec:.0f}s (no "
            "inference request landed).\n"
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
    p.add_argument("--confirm-sec", type=float, default=70.0,
                   help="when criteria 1-4 read wedged, wait this long and "
                        "re-sample the keep_alive expiry; alert only if it "
                        "did not advance (70s > the suite's between-call "
                        "gaps, so a healthy run always refreshes within it)")
    p.add_argument("--host", default="http://localhost:11434")
    p.add_argument("--once", action="store_true",
                   help="single check; exit 0 ok / 1 attention / 2 unknown")
    args = p.parse_args()

    # A watchdog whose alerts sit in a stdio buffer is no watchdog: when
    # output is redirected to a file (the normal detached usage) Python
    # block-buffers, and a status line can lag hours behind the check that
    # produced it. Force line-buffering so every verdict lands immediately.
    sys.stdout.reconfigure(line_buffering=True)

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

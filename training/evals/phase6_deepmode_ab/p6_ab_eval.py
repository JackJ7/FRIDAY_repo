r"""
Phase 6 A/B — deep-mode reasoning eval: qwen2.5:32b (offloaded) vs
deepseek-r1:14b (on-GPU, reasoning-distilled).

Runs each brain through the SAME hard-reasoning set via the REAL deep-mode
client path (core.model.OllamaClient with strip_reasoning resolved exactly as
register_deep_think does). Measures, per case:

  (a) accuracy  — is the checkable target number present within tolerance
  (b) latency   — wall-clock per call + tok/s + generated-token volume
  (c) voice     — reasoning-preamble leakage AFTER <think>-strip, answer-first-ness
  (d) VRAM      — snapshot of GPU memory in use while the brain is resident
  LEAK          — assert no <think>/</think> survives into reply.content

Throwaway-named technical problems only (no real project names — CLAUDE.md).
Deterministic answer checks where the problem has a checkable number.
Writes results JSON + prints a compact table.

Run:  py -3 scratchpad\p6_ab_eval.py  [model1 model2 ...]
      (default: both; pass one tag to run just that arm)
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
# import from the real repo
REPO = Path(r"C:\Users\jacko\Documents\FRIDAY")
sys.path.insert(0, str(REPO))

from core.model import ModelError, OllamaClient
from core.tools.reasoning_tools import _DEEP_SYSTEM, _resolve_strip_reasoning

CFG = yaml.safe_load((REPO / "config" / "friday_config.yaml").read_text(encoding="utf-8"))
HOST = CFG["model"]["host"]
NUM_CTX = CFG["model"]["num_ctx"]
TEMP = CFG["model"]["temperature"]

# --- the eval set: hard, multi-step, technical, ONE checkable number each ---
# target = (label, expected_value, abs_tolerance) ; checked against every number
# parsed from the answer text.
CASES = [
    {
        "id": "E1-gearbox",
        "q": ("A three-stage reduction gearbox has stage ratios 4:1, 3:1 and "
              "2.5:1. Input is 2.0 N.m at 3000 rpm. Each stage is 92% "
              "efficient. Give the output shaft speed in rpm and the output "
              "torque in N.m. Show the steps."),
        "targets": [("output speed rpm", 100.0, 1.0),
                    ("output torque N.m", 46.72, 1.5)],
    },
    {
        "id": "E2-cantilever",
        "q": ("A cantilever beam carries a 150 N point load at its free end. "
              "Length 0.6 m, rectangular cross-section 30 mm wide by 15 mm "
              "tall, aluminium E = 69 GPa. Compute the tip deflection in "
              "millimetres. Show the steps."),
        "targets": [("tip deflection mm", 18.6, 1.5)],
    },
    {
        "id": "E3-rcfilter",
        "q": ("A first-order RC low-pass filter uses R = 10 kohm and "
              "C = 100 nF. Give the -3 dB cutoff frequency in Hz, and the "
              "output/input amplitude ratio (and in dB) at 1 kHz. Show the "
              "steps."),
        "targets": [("cutoff Hz", 159.15, 3.0),
                    ("ratio at 1kHz", 0.157, 0.02)],
    },
    {
        "id": "E4-buoyancy",
        "q": ("A sealed cylindrical float, outside diameter 0.20 m and length "
              "0.50 m, has total mass 12 kg, fully submerged in fresh water "
              "(density 1000 kg/m3, g = 9.81). Give the net vertical force in "
              "newtons (state up or down), and the internal ballast mass in kg "
              "needed for neutral buoyancy. Show the steps."),
        "targets": [("net force N", 36.4, 3.0),
                    ("ballast kg", 3.71, 0.4)],
    },
    {
        "id": "E5-damping",
        "q": ("A mass-spring-damper has m = 2 kg, k = 800 N/m, c = 16 N.s/m. "
              "Give the undamped natural frequency in rad/s, the damping "
              "ratio, and the percent overshoot of the step response. Show "
              "the steps."),
        "targets": [("natural freq rad/s", 20.0, 0.5),
                    ("damping ratio", 0.20, 0.02),
                    ("percent overshoot", 52.7, 4.0)],
    },
]

# voice / preamble markers a reasoning model tends to leak OUTSIDE <think>
_LEAK_MARKERS = ("wait,", "wait ", "let me reconsider", "let me re-", "hmm",
                 "on second thought", "actually, i", "actually,i",
                 "let me think", "let me recompute", "let me double-check",
                 "but wait", "hold on")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def vram_used_mib():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0])
    except Exception:
        return None


def grade_accuracy(text, targets):
    """Return list of (label, expected, hit_bool). A target 'hits' if some
    number in the text is within tolerance."""
    nums = [float(n) for n in _NUM.findall(text)]
    results = []
    for label, exp, tol in targets:
        hit = any(abs(n - exp) <= tol for n in nums)
        results.append((label, exp, hit))
    return results


def voice_score(content):
    low = content.lower()
    leaks = [m for m in _LEAK_MARKERS if m in low]
    # answer-first heuristic: does it open with a preamble like "okay," / "let me"
    opener = low.lstrip()[:40]
    preamble_open = opener.startswith(("okay", "let me", "alright", "so,",
                                       "first,", "to solve", "we need to",
                                       "let's"))
    return {"leak_markers": leaks, "preamble_open": preamble_open}


def run_case(client, case):
    t0 = time.time()
    err = None
    try:
        reply = client.chat([
            {"role": "system", "content": _DEEP_SYSTEM},
            {"role": "user", "content": case["q"]},
        ])
    except ModelError as e:
        return {"id": case["id"], "error": str(e)}
    wall = time.time() - t0
    content = reply.content
    acc = grade_accuracy(content, case["targets"])
    leak = ("<think>" in content) or ("</think>" in content)
    return {
        "id": case["id"],
        "wall_s": round(wall, 1),
        "eval_count": reply.eval_count,
        "tok_s": round(reply.tokens_per_second, 1),
        "reasoning_chars": len(reply.reasoning or ""),
        "accuracy": [(l, e, bool(h)) for (l, e, h) in acc],
        "acc_hits": sum(1 for (_, _, h) in acc if h),
        "acc_total": len(acc),
        "leak_tag_in_content": leak,
        "voice": voice_score(content),
        "answer": content.strip(),
    }


def run_model(tag):
    deep_cfg = {"model": tag}
    strip = _resolve_strip_reasoning(deep_cfg)
    client = OllamaClient(host=HOST, model=tag, num_ctx=NUM_CTX,
                          temperature=TEMP, strip_reasoning=strip)
    print(f"\n=== {tag}  (strip_reasoning={strip}, num_ctx={NUM_CTX}, "
          f"temp={TEMP}) ===", flush=True)
    vram_before = vram_used_mib()
    results = []
    for case in CASES:
        print(f"  running {case['id']} ...", flush=True)
        r = run_case(client, case)
        if "error" in r:
            print(f"    ERROR: {r['error'][:120]}", flush=True)
            return {"model": tag, "error": r["error"], "strip": strip}
        results.append(r)
        print(f"    {r['wall_s']}s  {r['tok_s']}tok/s  gen={r['eval_count']}  "
              f"acc={r['acc_hits']}/{r['acc_total']}  "
              f"leak={r['leak_tag_in_content']}  "
              f"leakmarks={len(r['voice']['leak_markers'])}", flush=True)
    vram_after = vram_used_mib()  # snapshot while resident
    return {"model": tag, "strip": strip,
            "vram_before_mib": vram_before, "vram_resident_mib": vram_after,
            "cases": results}


def main():
    tags = sys.argv[1:] or ["qwen2.5:32b", "deepseek-r1:14b"]
    out = {"config": {"host": HOST, "num_ctx": NUM_CTX, "temp": TEMP},
           "models": []}
    for tag in tags:
        out["models"].append(run_model(tag))
    slug = "_".join(t.replace(":", "-").replace(".", "") for t in tags)
    outpath = Path(__file__).parent / f"p6_ab_results_{slug}.json"
    outpath.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWROTE {outpath}")


if __name__ == "__main__":
    main()

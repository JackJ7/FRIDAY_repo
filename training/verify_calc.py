r"""
verify_calc.py - assert every calc tool-result turn in the exemplar set matches
the REAL calc tool byte-for-byte.

WHY THIS EXISTS (paid for twice): calc result strings are GROUND TRUTH the
model learns to produce after a calc call. Hand-writing them is how six wrong
results slipped into the v2 build (pint prints 'm * N', 'm / s', 'l', and a
dimensionless ratio needs to_unit='' or 'dimensionless') before a call-by-call
check caught them. This makes that check runnable and non-optional: it walks
every generated + anchored exemplar, finds each assistant `calc` call and the
`tool` result that must follow it, recomputes with core.tools.calc_tools, and
fails loudly on any mismatch. Stdlib + the real calc tool only; no GPU, no
tokens.

Run:  py -3.13 training\verify_calc.py
Exit: 0 if every calc result matches, 1 (with the mismatches) otherwise.
"""

import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Import the SAME calc the runtime registers, so the check can never drift from
# what FRIDAY actually computes at inference time.
sys.path.insert(0, str(HERE.parent))
from core.tools.calc_tools import register_calc_tools   # noqa: E402


def _real_calc():
    """A throwaway registry that captures the calc function the runtime uses."""
    captured = {}

    class _Reg:
        def register(self, name, desc, schema, func, kind):
            captured[name] = func

    register_calc_tools(_Reg())
    return captured["calc"]


def _iter_calc_pairs(turns):
    """Yield (args, result_content) for every assistant calc call immediately
    followed by its tool result — the exact adjacency train.py renders."""
    for i, t in enumerate(turns):
        if t.get("role") != "assistant":
            continue
        for tc in t.get("tool_calls", []) or []:
            if tc.get("name") != "calc":
                continue
            nxt = turns[i + 1] if i + 1 < len(turns) else {}
            if nxt.get("role") != "tool":
                yield tc.get("arguments", {}), None, "calc call has no following tool turn"
                continue
            yield tc.get("arguments", {}), nxt.get("content", ""), None


def main():
    calc = _real_calc()
    files = sorted(glob.glob(str(HERE / "exemplars" / "**" / "*.json"), recursive=True))
    checked, mismatches = 0, []

    for jf in files:
        for ex in json.loads(Path(jf).read_text(encoding="utf-8")):
            for args, got, err in _iter_calc_pairs(ex.get("turns", [])):
                checked += 1
                if err:
                    mismatches.append((ex.get("id", "?"), args, "<none>", err))
                    continue
                want = calc(args.get("expression", ""), args.get("to_unit", ""))
                if got != want:
                    mismatches.append((ex.get("id", "?"), args, got, want))

    print(f"checked {checked} calc result turns across {len(files)} exemplar files")
    if mismatches:
        print(f"\nMISMATCHES ({len(mismatches)}):")
        for eid, args, got, want in mismatches:
            print(f"  {eid}\n    args:  {args}\n    got:   {got!r}\n    real:  {want!r}")
        raise SystemExit(1)
    print("OK - every calc result matches the real tool.")


if __name__ == "__main__":
    main()

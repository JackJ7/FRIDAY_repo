r"""
curate.py - turn raw interaction logs into a clean training candidate set.

Garbage in = bugs trained in. The logs in logs\interactions\ span the
pre-fix-loop era, when FRIDAY still narrated tool calls as text (claiming
"I've noted that" while calling nothing), mis-handled units, etc. Training on
those bakes the exact bugs we removed back into the weights. This pass applies
HARD excludes, then writes a review report so Jack can eyeball what survived.

Stdlib only - runs anywhere, no GPU, no heavy deps. It does NOT train anything;
it produces data\curated_logs.jsonl (kept records, original schema) plus
data\curation_report.txt (every record, kept or dropped, with the reason).

Usage:
    python training\curate.py
    python training\curate.py --min-date 2026-07-07   # tighten the cutoff
"""

import argparse
import glob
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = HERE.parent / "logs" / "interactions"
OUT = HERE / "data"

# Records at/after this date are candidates; earlier ones are pre-fix-loop and
# excluded wholesale (that is where the narrated-lie / unit-slip behavior lives).
DEFAULT_MIN_DATE = "2026-07-07"

# Reply phrases that claim a write/action. If the reply claims one of these and
# NO tool actually ran, it's the narrated-lie bug (Tier 3) - exclude it: it
# teaches the model to say it saved something without saving it.
_CLAIM_PHRASES = (
    "i've noted", "i have noted", "i've saved", "i've updated", "i've marked",
    "i've added", "i've recorded", "i've logged", "noted your", "i've fixed",
    "updated the note", "saved to", "added to your", "marked ", "i've tracked",
)

# Non-user-facing records: the memory pass and system-generated turns. Not
# conversations Jack had - drop from the conversational training set.
_NON_CHAT_USERS = ("(memory pass)", "(session greeting)")

# Human-review denylist: records that pass every automated check but model the
# WRONG behavior (e.g. a clarification loop where she never analyzes the file,
# or claiming an ability she doesn't have). One exact user-turn string per
# line, '#' comments allowed. This exists because curate.py REGENERATES
# curated_logs.jsonl on every run - a hand-deleted line would silently come
# back on the next build, so review verdicts must live somewhere durable.
DENYLIST = HERE / "curation_denylist.txt"


def _load_denylist() -> set:
    if not DENYLIST.exists():
        return set()
    return {ln.strip() for ln in DENYLIST.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")}


def _is_claim_without_action(rec: dict) -> bool:
    reply = str(rec.get("reply", "")).lower()
    tools = rec.get("tools") or []
    if tools:
        return False
    return any(p in reply for p in _CLAIM_PHRASES)


def _tool_errored(rec: dict) -> bool:
    """A tool whose result is an outright error (not a declined confirm, which
    is GOOD behavior worth keeping) models a failure as if it were normal."""
    for t in rec.get("tools") or []:
        res = str(t.get("result", ""))
        if res.startswith("ERROR") and "ConfirmationDeclined" not in res:
            return True
    return False


def classify(rec: dict, min_date: str, denylist: set = frozenset()):
    """Return (keep: bool, reason: str)."""
    user = str(rec.get("user", ""))
    if user in _NON_CHAT_USERS or (user.startswith("(") and user.endswith(")")):
        return False, "non-chat (memory pass / system turn)"
    # Denylist match on the full turn OR its first line: when Jack drops a file,
    # the harness appends a "\n\n[Jack attached a file ...]" marker after his
    # typed message, so an exact full-string entry can't express those records.
    # The first line is the human-typed message, which is what a verdict is about.
    if user.strip() in denylist or user.split("\n", 1)[0].strip() in denylist:
        return False, "denylisted (human review: models wrong behavior)"
    ts = str(rec.get("timestamp", ""))[:10]
    if ts and ts < min_date:
        return False, f"pre-cutoff ({ts} < {min_date}) - pre-fix-loop era"
    if not str(rec.get("reply", "")).strip():
        return False, "empty reply"
    if _is_claim_without_action(rec):
        return False, "narrated-lie: reply claims a write, no tool ran (Tier-3 bug)"
    if _tool_errored(rec):
        return False, "tool errored (models failure as success)"
    if len(str(rec.get("reply", ""))) < 15:
        return False, "reply too short to be a useful demonstration"
    return True, "kept"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-date", default=DEFAULT_MIN_DATE)
    ap.add_argument("--logs", default=str(LOGS))
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    denylist = _load_denylist()
    files = sorted(glob.glob(os.path.join(args.logs, "*.jsonl")))
    kept, report_lines = [], []
    counts = {"kept": 0, "dropped": 0}
    drop_reasons = {}

    for f in files:
        for i, line in enumerate(open(f, encoding="utf-8")):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                counts["dropped"] += 1
                drop_reasons["unparseable"] = drop_reasons.get("unparseable", 0) + 1
                continue
            keep, reason = classify(rec, args.min_date, denylist)
            tag = "KEEP" if keep else "DROP"
            counts["kept" if keep else "dropped"] += 1
            if keep:
                kept.append(rec)
            else:
                drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
            report_lines.append(
                f"[{tag}] {os.path.basename(f)}#{i}  {reason}\n"
                f"       user: {str(rec.get('user',''))[:100]!r}\n"
                f"       reply: {str(rec.get('reply',''))[:100]!r}")

    (OUT / "curated_logs.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in kept) + ("\n" if kept else ""),
        encoding="utf-8")

    summary = [
        "=" * 70,
        "CURATION SUMMARY",
        f"  kept:    {counts['kept']}",
        f"  dropped: {counts['dropped']}",
        "  drop reasons:",
    ] + [f"    {n:>4}  {r}" for r, n in sorted(drop_reasons.items(),
                                               key=lambda x: -x[1])] + [
        "=" * 70,
        f"  kept records -> {OUT / 'curated_logs.jsonl'}",
        "",
        "REVIEW: skim the KEEP lines below. Anything that models the wrong",
        "behavior, delete its line from curated_logs.jsonl before build_dataset.",
        "=" * 70, "",
    ]
    (OUT / "curation_report.txt").write_text(
        "\n".join(summary) + "\n".join(report_lines) + "\n", encoding="utf-8")
    print("\n".join(summary))
    print(f"Full per-record report -> {OUT / 'curation_report.txt'}")
    if counts["kept"] < 100:
        print(f"\n  NOTE: only {counts['kept']} usable logged examples - well "
              f"below the 500 floor.\n  The set is authoring-led: method "
              f"exemplars carry the bulk of the signal.")


if __name__ == "__main__":
    main()

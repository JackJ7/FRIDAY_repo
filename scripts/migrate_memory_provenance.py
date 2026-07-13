r"""
migrate_memory_provenance.py — one-time interactive backfill for Task 1
(memory provenance). Existing brain notes predate the real/test split; this
walks them WITH Jack and MOVES the ones he classifies as test artifacts into
brain\test_archive\ (same relative path — git history and content intact).

HARD GUARANTEES (the plan's constraints, enforced in code):
  * ZERO deletions — the only operation is a move inside the brain; the
    script counts every .md before and after and refuses to finish if the
    counts differ.
  * Nothing is classified without Jack — heuristics only pre-SUGGEST a label
    (known live-test fixture names → suggest test); Enter accepts the
    suggestion, but every note is shown and confirmed.
  * Identity and machinery are out of scope: character/, skills/, playbooks/,
    index.md, and the tracker-owned files (commitments.md, timelines/) are
    never offered. Test entries inside the trackers are line-items, not
    files — prune those in the panel/by hand, not here.

Run it on the real brain (it commits the moves), or on a COPY to rehearse:
    py -3.13 scripts\migrate_memory_provenance.py
    py -3.13 scripts\migrate_memory_provenance.py --brain path\to\copy --dry-run
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = "test_archive"

# Never offered for classification: identity, curated method files, the
# index, and tracker-owned structured state.
EXCLUDED_PREFIXES = ("character/", "skills/", "playbooks/", "timelines/",
                     ARCHIVE + "/", ".git/", ".obsidian/")
EXCLUDED_FILES = ("index.md", "commitments.md")

# Names that have only ever appeared in live capability tests — suggestion
# fuel only; Jack confirms every label.
TEST_MARKERS = ("zeta kill rig", "zeta_kill_rig", "alpha rig", "alpha_rig",
                "beta probe", "beta_probe", "gamma arm", "gamma_arm",
                "delta sled", "delta_sled", "test fixture", "fabricated",
                "capability test", "diagnostic session")


def candidates(brain: Path) -> list:
    """Notes eligible for classification, as brain-relative posix paths."""
    out = []
    for p in sorted(brain.rglob("*.md")):
        rel = p.relative_to(brain).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES) or rel in EXCLUDED_FILES:
            continue
        out.append(rel)
    return out


def suggest(brain: Path, rel: str) -> str:
    """Pre-suggested label. Conservative: 'test' only on a known marker."""
    hay = (rel + "\n" + (brain / rel).read_text(
        encoding="utf-8", errors="replace")).lower()
    return "test" if any(m in hay for m in TEST_MARKERS) else "real"


def count_notes(brain: Path) -> int:
    """Every .md under the brain, archive included — the no-deletion check."""
    return sum(1 for p in brain.rglob("*.md")
               if not p.relative_to(brain).as_posix().startswith(
                   (".git/", ".obsidian/")))


def classify(brain: Path, dry_run: bool = False,
             input_fn=input, print_fn=print) -> dict:
    """Walk candidates, ask Jack, move confirmed test notes. Returns a
    summary dict (also the testable seam — tests inject input_fn)."""
    before = count_notes(brain)
    moved, kept, skipped = [], [], []

    notes = candidates(brain)
    print_fn(f"{len(notes)} notes to classify (identity/trackers excluded). "
             f"[r]eal / [t]est / Enter=suggested / [s]kip / [q]uit\n")
    # Batched by top-level folder so related notes are judged together.
    by_folder = {}
    for rel in notes:
        by_folder.setdefault(rel.split("/", 1)[0] if "/" in rel else ".",
                             []).append(rel)

    quit_early = False
    for folder, rels in sorted(by_folder.items()):
        if quit_early:
            break
        print_fn(f"--- {folder}/ ({len(rels)} notes) ---")
        for rel in rels:
            sug = suggest(brain, rel)
            head = "\n".join((brain / rel).read_text(
                encoding="utf-8", errors="replace").splitlines()[:6])
            print_fn(f"\n[{rel}]  (suggest: {sug.upper()})\n{head}\n")
            ans = input_fn(f"  classify [{sug[0]}]: ").strip().lower()
            if ans == "q":
                quit_early = True
                break
            if ans == "s":
                skipped.append(rel)
                continue
            label = {"r": "real", "t": "test", "": sug}.get(ans)
            if label is None:
                skipped.append(rel)
                continue
            if label == "test":
                dest = brain / ARCHIVE / rel
                if dry_run:
                    print_fn(f"  [dry-run] would move -> {ARCHIVE}/{rel}")
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    (brain / rel).rename(dest)
                moved.append(rel)
            else:
                kept.append(rel)

    after = count_notes(brain)
    if not dry_run and after != before:
        raise SystemExit(
            f"NOTE COUNT CHANGED ({before} -> {after}) — a move went wrong. "
            f"Nothing should ever be deleted; inspect git status before "
            f"trusting this run.")

    if moved and not dry_run and (brain / ".git").exists():
        subprocess.run(["git", "-C", str(brain), "add", "-A"],
                       capture_output=True)
        subprocess.run(["git", "-C", str(brain), "commit", "-m",
                        f"Provenance backfill: {len(moved)} note(s) -> "
                        f"{ARCHIVE}/ (moved, nothing deleted)"],
                       capture_output=True)

    print_fn(f"\nDone. moved->archive: {len(moved)}  kept real: {len(kept)}  "
             f"skipped: {len(skipped)}  | notes before/after: "
             f"{before}/{after} (must match)")
    return {"moved": moved, "kept": kept, "skipped": skipped,
            "before": before, "after": after}


def main():
    ap = argparse.ArgumentParser(
        description="Interactive backfill: classify brain notes real/test.")
    ap.add_argument("--brain", default=str(ROOT / "brain"))
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would move; touch nothing")
    args = ap.parse_args()
    brain = Path(args.brain).resolve()
    if not brain.is_dir():
        raise SystemExit(f"No brain at {brain}")
    classify(brain, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

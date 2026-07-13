# Running independent phases in parallel (git worktrees)

**Purpose.** Work on two or more *independent* workstreams at once (e.g.
Notes-10 Phase 7 and Phase 8) without sessions clobbering each other. The
collision risk is real because nearly every phase edits the same file,
`core/engine.py`; git worktrees give each session its own working directory
over one shared history, so disjoint edits merge cleanly and only true
same-line overlaps conflict.

This runbook is for **future me to execute autonomously.** Read it before
spinning up a second session on this repo.

---

## When this applies (and when it does NOT)

Use parallel worktrees when the workstreams are **logically independent** —
neither needs the other's code to be correct, and they are not stages of one
pipeline. Notes-10 P7 (stop-path) and P8 (briefing grounding) qualify: P7 is
standalone; P8 depends only on a tiny P7 accessor that should be decoupled
first (see "Remove shared dependencies").

Do **NOT** parallelize when:
- One phase's output is the next phase's input (a pipeline) — run those in
  order, in one tree.
- Both need the **live brain, a model call, or the GPU** at the same time —
  see "Hard constraints" below. Worktrees isolate *source*, not the machine's
  single Ollama/GPU or the shared on-disk brain.

If unsure whether two phases are independent, they're independent only if you
can state, in one sentence each, why neither reads the other's new code.

---

## Hard constraints (FRIDAY-specific — these bite)

1. **Ignored runtime dirs are NOT copied into a worktree.** `brain/`, `data/`,
   `logs/`, `friday_documents/`, `results/`, and the venvs are all gitignored,
   so `git worktree add` creates a working dir **without** them. A worktree is
   therefore good for **source edits and pure-code tests** (no model, no brain)
   — e.g. the STOP-* / BRIEF-* unit suites that use fake managers. It is
   **not** a place to launch live FRIDAY.
2. **One brain, one lock, one GPU — shared across all worktrees.**
   - The live brain (`brain/`) is a single git-versioned dir on disk, shared by
     every worktree that references it. Never run two sessions that *write* the
     brain concurrently.
   - Only one live FRIDAY may hold the single-instance lock (**port 47533**).
     Check ownership before starting a live instance — Jack may have her open.
   - Ollama and the GPU are single-tenant. Only **one** session at a time may
     run model-marked tests, a live instance, or autoresearch. Pure-code
     (`--quick`-excluded / non-model) suites run fine in parallel.
3. **Frozen code during evals.** Never land model-visible changes (prompt,
   tools, graders, tests) while an eval run is in flight — it poisons the run.
   If one session is mid-eval, the others must not merge model-visible changes
   to `master` until it finishes.

---

## Setup

From the main working tree (`C:\Users\jacko\Documents\FRIDAY`, branch
`master`), create one worktree + branch per phase. Put worktrees in **sibling**
directories, never inside the repo:

```bash
git worktree add ../FRIDAY-p7 -b phase7
git worktree add ../FRIDAY-p8 -b phase8
```

Each command makes `../FRIDAY-p7` a full checkout on a fresh branch off the
current `master` commit. List them any time with `git worktree list`.

### Driving a session in a worktree

- **Via the Agent tool:** spawn with `isolation: "worktree"` — the harness
  creates and cleans up the worktree for you. Give the agent the phase's plan
  section (e.g. "implement Notes-10 Phase 7 from FRIDAY_notes10_plan.md") as
  its prompt.
- **Manually / another CLI session:** open the session with its working
  directory set to `../FRIDAY-p7` and work normally. Its edits to
  `core/engine.py` never touch the other worktrees until merge.

### Remove shared dependencies first

If two "independent" phases still share one new symbol (e.g. P8 was going to
call a `latest_status()` accessor added by P7), either (a) land that shared
accessor on `master` first and branch both worktrees off it, or (b) have each
phase define what it needs locally. Otherwise the second branch to merge hits a
needless conflict. Prefer (a) for anything more than a few lines.

---

## Merging back

1. In the worktree, commit the phase on its branch and run its **pure-code**
   test suite (green before merge — that's the lock the plan asks for).
2. From `master` in the main tree, merge one branch at a time:
   ```bash
   git merge phase7
   git merge phase8
   ```
   Disjoint regions of `core/engine.py` auto-merge. A conflict means a true
   same-line overlap — resolve by hand, keeping both phases' logic.
3. **The plan doc (`FRIDAY_notes10_plan.md`) is tracked, so it conflicts if two
   branches edit it.** Keep each branch's edits to *its own* phase section and
   *its own* results-log row; that makes conflicts trivial. Better still: update
   the plan doc's shared status header only on `master` after both merges.
4. Run the full non-model suite on `master` once after merging, to confirm the
   combined result holds the GT baseline.

## Cleanup

```bash
git worktree remove ../FRIDAY-p7
git branch -d phase7      # after it's merged
```

`git worktree remove` refuses if the tree has uncommitted changes — commit or
discard first. An abandoned worktree can be force-removed with `--force`.

---

## Quick checklist (the whole loop)

1. Confirm the phases are logically independent; decouple any shared new symbol.
2. `git worktree add ../FRIDAY-<phase> -b <phase>` per phase.
3. Run each session in its worktree; **only one** touches model/brain/GPU at a
   time; pure-code work parallelizes freely.
4. Commit + pass the pure-code suite on each branch.
5. Merge branches to `master` one at a time; resolve any same-line conflicts.
6. Update the plan's shared header on `master`; run the full suite once.
7. `git worktree remove` + `git branch -d` to clean up.

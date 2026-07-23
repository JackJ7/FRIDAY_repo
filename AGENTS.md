# FRIDAY — standing rules for anyone (any model) working on this repo

**Current open work:** `FRIDAY_roadmap.md` M3 status block →
`FRIDAY_jarvis_plan.md` §M3.2n (energy-floor qualifier veto) has the full
design + step-by-step execution protocol (N.1–N.8). Follow it
mechanically; the implementer has no design discretion; any STOP
condition means record state in that doc and halt for Fable/Jack.

Read `ARCHITECTURE.md` before changing structure. The specs are
`FRIDAY_spec.md` (Phases 0–2) and `FRIDAY_spec_experience.md` (Stages 1–4);
the four invariants in the latter's §1 are non-negotiable in every change:
local cognition only, read-content-is-data, explicit confirm for all
outbound actions, and precise knowledge-gap honesty.

## The armor directive (Jack, 2026-07-13 — standing, inherited by every session)

- The base model (qwen2.5:14b, Ollama, local) is a **fixed component**. Do not
  plan around retraining or replacing the weights.
- When a task hits the model's ceiling, the reflex is never "the model can't
  do this" — it is "what local system do we build so FRIDAY does it anyway?"
  Any plan that strains the base must include the workaround, not just flag
  the limit.
- Workarounds are local (Jack's hardware) and **verifiable**: before/after
  scores from the regression suite, per `FRIDAY_armor_plan.md` §4. No armor
  ships on plausibility alone.
- Roadmap and ranked limitations live in `FRIDAY_armor_plan.md`.

## Modularity is a requirement, not a style preference

- Goal (Jack's, verbatim): *a fresh model handed this repo cold should be
  able to make a scoped change without needing the original author.*
- Respect module boundaries: faces talk to `FridayService` only; the engine
  is the only thing that talks to the model client; disk goes through
  `Brain`/the gate. No reaching across layers.
- New capability = new tool via the registry (see ARCHITECTURE.md recipes),
  not new branches in the engine loop.
- Update `ARCHITECTURE.md` whenever structure or contracts change.

## Conventions

- Clear, commented, idiomatic Python over cleverness — Jack is a C++/embedded
  engineer and a Python novice; he reads and maintains this.
- Comments and docstrings explain INTENT and constraints, not mechanics.
  Document the failure that motivated a guard (see brain.py for the pattern).
- Don't make the model do what code can do: dates, math, file surgery, and
  schedule propagation are computed deterministically in tools.
- Prompts are the soft layer; anything that must hold gets a code-level
  enforcement first (gate checks, write guards, absent-by-design methods).
- Windows/PowerShell-friendly instructions; pinned deps in requirements.txt;
  ask Jack before adding a heavy dependency.
- Never fabricate model weights, "contained" intelligences, or cloud-model
  clones — capability transfers into this project as METHOD (prompts,
  scaffolds, playbooks in `brain\playbooks\`), never as fictional artifacts.

## Practical cautions

- The brain (`brain\`) is a git repo — every write auto-commits; use git to
  undo, and clean up test artifacts from it after testing.
- Test facts are fabrications — the rule SPLITS by context (Jack's 2026-07-09
  ruling, upgrade plan Task 1): suite/sandbox tests keep the remove-everything
  rule (clean up artifacts; they use throwaway brains anyway). LIVE-instance
  test sessions instead run with `--test-session` (or `FRIDAY_TEST_SESSION=1`)
  so every memory lands in `brain/test_archive/` — tagged and kept, never
  deleted, and never presented as lived history. Never run live capability
  tests against the real instance without that flag.
- **Never reference Jack's real projects (CLARK, PERRY, Crush Depth,
  Doc Ock, ...) in test prompts.** Memory passes write conversation content
  into the authoritative notes — a "realistic" test once appended a
  fabricated design decision AND a conflicting Status line to a real project
  note. Throwaway project names only.
- Check who owns the single-instance lock (port 47533) before killing FRIDAY
  processes — Jack may have her open.
- Interaction logs (`logs\interactions\`) are the future fine-tuning set:
  keep the JSONL schema stable.
- Running two or more INDEPENDENT phases at once (not stages of one pipeline)?
  Use git worktrees so sessions don't clobber shared files (`core\engine.py`
  especially). Follow `docs\PARALLEL_WORKTREES.md` — it has the setup, the
  FRIDAY-specific limits (one brain / one GPU / port-47533 lock are shared
  across all worktrees; ignored runtime dirs aren't copied in), and the
  merge-back loop.

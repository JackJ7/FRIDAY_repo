# FRIDAY roadmap — from here to 1.0

Status: LIVING DOCUMENT, created 2026-07-17 (Fable 5). This is the
**umbrella pipeline** from the current state to "FRIDAY is 100% ready to
go." It owns *sequencing and the definition of done* across the two
program plans; it never owns leg-level detail:

- **`FRIDAY_armor_plan.md`** — "she answers correctly" (floors, barriers,
  parity rows P1–P7, the ship-gate discipline). Leg detail lives there.
- **`FRIDAY_jarvis_plan.md`** — "she acts like a colleague" (J0–J5:
  tasks, sentinels, skills, voice). Leg detail lives there.

References are one-way (this doc points at those; they don't point
back), so this doc never conflicts with a leg in flight. Update rule
(Jack's standing living-doc rule): when a milestone moves, edit its
Status cell **in place** and date it. Never spawn companion docs.

Superseded plans, for a cold reader: `FRIDAY_coherence_plan.md`,
`FRIDAY_notes10_plan.md`, `FRIDAY_upgrade_plan.md` (archived) are
COMPLETE. `FRIDAY_framework_fix_plan.md`'s header says "PLAN ONLY —
nothing implemented"; that is **stale** — its items were absorbed by the
armor program (F2/F1 shipped in leg A1, F4 tried and reverted). Do not
re-implement F-items from it.

---

## 1. Definition of done — what "100% ready" means (gradeable, not felt)

FRIDAY 1.0 ships when ALL of these hold. No gate ships on plausibility
(armor directive §0 applies to the release itself):

| Gate | Criterion | Evidence required |
|---|---|---|
| D1 | **Armor residuals closed or formally accepted.** Every currently-named red (armor plan §6 rankings + watch lists) is either converted or written up as a documented known-limit with its flaky band. | Final full-suite run + a residual table in armor plan §6 |
| D2 | **Conversation parity holds.** Golden conversation family at m1=m2=m3=m5=0, m4 near-minimal (armor §0b scorecard), stable across **3 consecutive full runs**. | The three compare reports |
| D3 | **The four dream scenes pass** (jarvis plan §0): handle-it-while-I'm-out (J1 acceptance a–d), she-noticed-first (J2 acceptance), remembers-everything (shipped + J3.4), just-talk-to-her (J4 acceptance). | Per-leg acceptance evidence in jarvis plan §6 |
| D4 | **Ops hardened.** Detached-run protocol, Ollama-wedge sentinel live, brain backup/restore documented and tested, launch-on-login + tray presence verified, single-instance lock behavior confirmed. | §M7 checklist below, ticked in place |
| D5 | **Docs current + cold-start audit passed.** ARCHITECTURE.md/README match reality; a fresh session (a *different* model, handed the repo cold) completes a scoped change using docs only — Jack's modularity goal, tested for real. | The audit session's transcript/result noted here |
| D6 | **Soak sign-off.** 1–2 weeks of daily-driver live use with the F-grade pipeline running; no new F-class friction, or every F spawned and closed a mini-leg. Jack signs off. | Jack's explicit sign-off recorded here |

Asymptotic goals (parity, exemplar bank) don't block 1.0 — D2's "three
stable runs" is the finish line; further polish is post-1.0 (§M8).

---

## 2. Current position (snapshot 2026-07-17 — update when grossly stale)

- **Armor:** 11 legs closed, all ship-gates met. Suite 434/450 on
  candidate `2026-07-17_0827`; injection_defense and memory_persistence
  at 1.000; memory_recall 0.950. Named residuals: EML importance floor,
  COM-008, quant batch (canon oz-in + gear-direction floor), PT.1
  T3-arming; parity GAPs P5 (correction ledger), P2 (dangling-intent
  floor), P3 (identifier generalization). Watch: CN.3 false-positives,
  GND-013/PLB-004/MEM-001-redirect.
- **Jarvis:** plan approved; J0 (toggles+Controls UI) and J1.1 (task
  ledger) CODE-COMPLETE on branch `jarvis` (worktree, unmerged). J1
  increments 2–4, J2, J3, J4 unbuilt. J5 designed-not-built.
- **Baseline rule in force:** `2026-07-17_0827` is the next baseline
  ONLY if nothing model-visible lands after `7b626af`.
- **Nothing in flight** at time of writing; main clean at `0829118`.

---

## 3. The pipeline

Legend: ⛓ = hard-sequential (must finish before the next starts);
∥ = parallel-safe lane (see §4 for the rules). "Model" = recommended
Claude Code model per §5.

### M0 — Merge & re-baseline gate  ⛓  (NEXT — do first)

The J0/J1.1 merge per the jarvis plan §6 pickup protocol: `--quick` in
`..\FRIDAY-jarvis`, merge `jarvis` → main, `--quick` on main, live
panel smoke (DND flips agree from both surfaces). J0/J1.1 are designed
non-model-visible (pure UI + ledger) — **verify with a diff against
prompts/tools/engine context before deciding**: if truly invisible,
baseline `0827` stays valid; if anything model-visible slipped in, take
a fresh full-run baseline (~3.5h, detached + watchdog) before any Track
A leg opens. Also: kill the stale Jul-14 idle PIDs (6644/26944).
**Why first:** every later milestone needs a trustworthy baseline
anchor, and both tracks are blocked on knowing which one it is.
Model: **Sonnet 5** (protocol is fully written).
**Status: OPEN.**

### M1 — Armor residual batch  ⛓ per leg  (Track A)

The Jack-confirmed ranking, one leg at a time, each with the full armor
cycle (design → branch → `--quick` → merge → detached full run →
compare → ship gate):

| Leg | Target | Notes |
|---|---|---|
| M1.1 | EML importance floor | Wire the deterministic EML-007 pre-screen into the reply path; EML-004/005 flaky band, email 0.6 |
| M1.2 | COM-008 model-close | Commitments' only residual; small — may batch with M1.4 |
| M1.3 | Quant batch | canon oz-in `_UNIT_TABLE` family (deferred grader gap, CHK-002) + gear-direction cross-check floor (GOLD-gear-03 0/5 direction churn) |
| M1.4 | PT.1 T3-arming gap | Carryover; small |

Batching two small items into one leg is fine (one candidate run
instead of two) — record the batching decision in armor §6.
Model: **Fable 5** for design/adjudication, **Sonnet 5** may implement
from the written §6 design, **Haiku 4.5** babysits runs.
**Status: QUEUED behind M0.**

### M2 — Parity gap closure  ⛓ per leg  (Track A — the north-star finishers)

The remaining §0b rows, ranked by live friction as always (a live
F-grade re-ranks these above anything):

| Leg | Row | What |
|---|---|---|
| M2.1 | P5 | Correction ledger — detect the correction shape, pin it into the referent block for the session (zero armor exists today; the transcript showed repeat-after-correction) |
| M2.2 | P2 | General dangling-intent floor — reply ends first-person-future + zero tools ran → recover or re-prompt |
| M2.3 | P3 | Generalize CN.3 identifier grounding beyond projects to any tool-surfaced namespace (files, runs, notes) — watch the CN.3 false-positive rate while in there (3rd sighting) |

Exit = D2's scorecard condition starts holding.
Model: **Fable 5** (design-heavy, regression-prone floors — this is the
subtlest armor work left).
**Status: QUEUED behind M1 (or interleaved if a live F-grade demands it).**

### M3 — J1 completion  (Track B, EXCEPT M3.2 which takes a Track A slot)

Per jarvis plan §6's recorded increment order:

| Step | What | Visibility |
|---|---|---|
| M3.1 | `brain.py` write guard for `tasks\` (must precede any task tool) | non-model ∥ |
| M3.2 | Model-facing task tools + `TaskLedger.summary()` referent-block injection | **MODEL-VISIBLE ⛓** — full armor-style baseline/compare, serialized with Track A |
| M3.3 | `core\jobs.py` background runner (idle-aware, watchdog-checking, suite-run-aware pause) + `jobs.background_enabled` toggle | non-model ∥ |
| M3.4 | While-you-were-away board (Service API + UI) | non-model ∥ |

Then grade J1 acceptance (a)–(d).
Model: **Sonnet 5** for M3.1/3.3/3.4; **Fable 5** designs M3.2 and
adjudicates its compare (Sonnet may implement).
**Status: QUEUED — M3.1 can start any time after M0; M3.2 waits for a
free Track A slot.**

### M4 — J2 proactive senses  ∥ mostly  (Track B)

Sentinel framework + the three watcher families (email/calendar,
repos/runs, system incl. the PROMOTED ollama_watchdog) + triage with
code floors + board/toast escalation. Watcher plumbing is
non-model-visible (worktree-parallel with M1/M2); the salience model
pass is small — check visibility honestly at merge time. All notice
content tainted (invariant 2) by construction.
Model: **Sonnet 5** builds; **Fable 5** reviews the taint/triage design
(it's an injection surface).
**Status: QUEUED — can open once M3.3's runner exists (notices ride the
same Service loop), plumbing may start earlier.**

### M5 — J3 skills & context economy  (Track B, J3.3 takes a Track A slot)

Skill registry + frontmatter (J3.1), intent-matched progressive loading
(J3.2), skill distillation offers (J3.4) — then **J3.3 tool-schema
disclosure LAST**: it changes every prompt and is pre-flagged as the
most regression-prone item in either plan; it gets a full armor-style
before/after compare regardless of the lighter jarvis gate.
Model: **Sonnet 5** for J3.1/3.2/3.4; **Fable 5 required** for J3.3
end-to-end (design, implement, adjudicate).
**Status: QUEUED behind M3; J3.3 additionally behind a free Track A slot.**

### M6 — J4 voice  ∥  (Track B)

Push-to-talk first, wake word second, `voice.mode` runtime toggle as
the end state (Jack's recorded decision). faster-whisper STT (CPU/int8
— GPU stays FRIDAY's), Piper TTS (approved dep), transcript enters
`FridayService` like typed text so every floor applies; TTS speaks only
SETTLED replies (stream-vetting hold inherited — voice gets the armor
for free). Arms J2's `notify.spoken_alerts` rung (J4.3). Non-model-
visible; verify anyway per jarvis §3.
Model: **Sonnet 5** (integration/driver debugging; escalate to
**Opus 4.8** only if the audio pipeline fights back).
**Status: QUEUED behind M4 (its escalation rung) — the ptt core could
open earlier in a worktree if a session is free.**

### M7 — Release hardening  ⛓  (the finish line — strictly sequential)

| Step | What |
|---|---|
| R1 | **Residual sweep**: walk the whole board; every red is fixed or formally accepted with its band documented (feeds D1) |
| R2 | **Soak**: 1–2 weeks daily-driver use, F-grade pipeline live, any F → mini-leg; plus 3 consecutive stable full runs (D2, D6) |
| R3 | **Ops**: brain backup/restore written AND restore-tested; launch-on-login, tray, hotkey verified; detached-run + watchdog protocol doc'd as standing run-ops; stale-process hygiene |
| R4 | **Docs freeze + cold-start audit**: ARCHITECTURE/README refreshed; close-out entries in both plans; then the D5 audit — a different model, cold, scoped change, docs only |
| R5 | **Jack sign-off** → tag FRIDAY 1.0 |

Model: **Fable 5 or Opus 4.8** for R1/R4 audits (fresh eyes matter more
than speed here — consider deliberately using Opus for the cold-start
audit since a non-Fable reader is the point); **Haiku 4.5** for doc
sweeps and soak-week monitoring.
**Status: QUEUED — opens when M1–M6 are closed.**

### M8 — Post-1.0 backlog (do NOT open without Jack)

- **J5 reach** — one-way notify-out to phone (designed-not-built).
- **QLoRA adapter** — the interaction-log schema has been kept stable
  for exactly this; revisit once soak data exists (weights half of
  parity, armor §0b).
- **A11 exemplar bank** — needs a durably green suite; feeds the
  adapter.
- **Embedding/vector index activation** (ChromaDB) — Jack-gated dep
  decision, still open from coherence Phase 5.
- Two-way remote chat — **explicitly out of scope** (recorded).

---

## 4. Parallel vs. sequential — the standing rules

**Hard-serial (never overlap):**
1. **One full-suite run at a time** — one GPU, one Ollama, one brain,
   one port-47533 lock. A run in flight owns the GPU; background jobs
   and dev model-testing pause.
2. **Model-visible changes serialize with runs AND with each other** —
   frozen-code-during-evals, and every model-visible landing
   invalidates the baseline (next leg takes a fresh one). This is why
   M3.2 and J3.3 queue for "Track A slots" even though they're jarvis
   work.
3. **`core\engine.py` has one writer at a time** — coordinate before
   touching it; everything else parallelizes via worktrees.
4. **Merges to main serialize** around whatever run/baseline is live —
   check what's in flight before merging (the RN-leg coordination
   pattern).

**Parallel-safe lanes (run these alongside anything):**
- Doc work, leg *design* writeups, memory/plan syncs, adjudication of
  finished runs.
- Non-model-visible code in a **worktree** (J2 plumbing, J4 voice, UI,
  board, watchers) — per `docs\PARALLEL_WORKTREES.md`; remember
  worktrees still share the one brain/GPU/lock, and sandbox-fixture
  tests need the gitignored brain seed copied in.
- Grader-gap fixes: *designed* any time, **landed only between runs**
  (the CHK-002 deferral precedent).

**Practical shape: at most two working sessions at once.**
- **Track A session** owns armor/model-visible work + the GPU + all
  full runs (M0 → M1 → M2, then lends slots to M3.2 and J3.3).
- **Track B session** owns jarvis non-model work in the `jarvis`
  worktree (M3.1/3.3/3.4 → M4 → M6), merging only in coordination with
  Track A's baseline state.
- Track C (docs/design/adjudication) rides inside either session.
More than two sessions adds coordination cost faster than it adds
throughput — the GPU is the bottleneck and it is singular.

---

## 5. Which Claude Code model, when

Rule of thumb: **design and judge with the biggest model; build to a
written spec with Sonnet; watch and record with Haiku.** The expensive
mistakes in this program have all been judgment mistakes (mis-adjudicated
deltas, regression-prone prompt changes), never typing mistakes.

| Work | Model | Why |
|---|---|---|
| Leg design, root-cause forensics, ship-gate adjudication, down-delta verdicts | **Fable 5** (Opus 4.8 acceptable fallback) | The RN.4-class investigations and §4.3 verdicts are the highest-judgment work in the program; a wrong verdict poisons the lineage |
| Model-visible floors/barriers/prompt changes (M2 legs, M3.2, J3.3) | **Fable 5** design + adjudication; Sonnet 5 may implement the written design | Subtle regressions; J3.3 is pre-flagged most-regression-prone |
| Non-model plumbing from a written §6 design (UI, ledger, runner, board, watchers, voice) | **Sonnet 5** | The design is already on paper; this is disciplined implementation |
| Run babysitting, watchdog/log monitoring, doc/memory sync, routine commits | **Haiku 4.5** | Cheap, frequent, low-judgment; frees the big-model budget for legs |
| Cold-start audit (R4/D5) | **Opus 4.8 deliberately** (i.e., NOT the model that wrote the docs) | The test is whether a *different* reader can work the repo cold |
| Soak-week F-grading + mini-legs (R2) | **Fable 5** | F-grade tracing is the parity pipeline's core judgment call |

---

## 6. Session pickup protocol (cold start here)

1. Read this doc top to bottom; check §3 Status cells for the frontier.
2. Read the owning plan's §6 tail for the active/next leg (armor or
   jarvis per the milestone).
3. Check what's in flight — `git log`/`git worktree list`, running
   python/pytest PIDs, `results\launch_logs\` — before claiming the
   GPU, `engine.py`, or a merge.
4. Do the work under the owning plan's discipline; record results in
   THAT plan's §6; then update the milestone Status cell HERE (dated,
   in place).

## 7. Results log (roadmap-level events only — leg detail goes in the owning plans)

- 2026-07-17: Roadmap created. Position: post-RN (armor, 11 legs
  closed), J0/J1.1 unmerged on `jarvis`. M0 is the frontier.

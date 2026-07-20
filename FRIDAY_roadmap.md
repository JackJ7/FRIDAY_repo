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
- **Jarvis:** J0 (toggles+Controls UI) and J1.1 (task ledger) MERGED to
  main (`bf5dddc`, 2026-07-17 ~18:15, M0 closed) — confirmed
  non-model-visible, live panel smoke passed. J1 increments 2–4, J2,
  J3, J4 unbuilt. J5 designed-not-built.
- **Baseline rule in force:** `2026-07-17_0827` stays the active
  baseline (M0 confirmed nothing model-visible landed after `7b626af`)
  — valid until M1.1 or M3.2 lands something model-visible.
- **Nothing in flight** at time of writing; main clean at `bf5dddc`.
  M1 (armor residual batch) is next.

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
**Status: CLOSED 2026-07-17 ~18:15 (`bf5dddc`).** `--quick` on
`jarvis` (342/342) → merged to main (RA and RN had both already closed
by pickup time, so the real merge target was `0829118`, not the
`31e7475` the leg-open entry assumed) → `--quick` on main (379/379) →
live panel smoke done by driving the real windowed app (screenshots +
simulated clicks, no Playwright attach available for a native
pywebview window): Controls-panel DND switch and sidebar DND link
round-trip in both directions. Model-visibility diff confirmed J0/J1.1
touch zero prompt/tool/engine surface — **baseline `2026-07-17_0827`
stays valid, no fresh full run needed.** The named stale PIDs
(6644/26944) turned out to be Windows PID reuse onto unrelated
`chroma-mcp` processes, not leftover FRIDAY — not killed; no FRIDAY
process was actually running. Full detail: jarvis plan §6, J0 pickup
entry.

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
**Status: CLOSED 2026-07-18 (Fable 5) — see the M1 CLOSED block below;
next baseline `2026-07-18_0816`.** Full design + adjudication rules in armor plan §6,
"M1 batch" section (end of file). Batching decision recorded there:
**two legs, not four** — **EM leg** = M1.1 alone (the F4-revert history
requires the EML re-attempt to get its own compare), then **QB leg** =
M1.2 + M1.3 + M1.4 batched (four disjoint surfaces, per-item ilog/guard
attribution). Baseline: EM uses `2026-07-17_0827`; QB uses EM's
candidate.

**IMPLEMENTATION UPDATE 2026-07-18 (Sonnet 5).** EM leg EM.0–EM.5 DONE:
EM.1/EM.2 code + EM.3 guards (EMF-001..008, all pass) merged to main
(`a291a28`, fast-forward); EM.4's two live batches showed EML-005 (the
actual burial case) never buried the fact in 10/10 runs across both
batches with zero F4-signature (no check_email re-poll, no empty-reply
false-fires); EM.5's detached candidate run **`2026-07-18_0045`** is
DONE (460/478 in 2:44:37, clean exit, watchdog confirmed no wedge) and
ready for **EM.6 (Fable/Jack compare vs `2026-07-17_0827` — NOT run by
Sonnet, per protocol)**. Caveat: the per-turn ilogs for this specific
candidate run rotated out of the pytest tmp cache before they could be
pulled (too many later tests ran first) — pull sandbox_ilogs immediately
after future flights, not after.

QB leg: QB.0–QB.3 DONE on branch `qb` (commit `892c552`, NOT merged) —
COM-008 fuzzy matcher + COM-009..012, canon oz-in family + CHK-007,
gear-direction floor + GRC-001..008, all guards pass, `--quick` green
(400 passed). **QB.4 CAPTURE COMPLETE (3x live GT-C9 replay, dumps in
`..\FRIDAY-qb\qb_batches\`, gitignored) but the FIX IS BLOCKED pending
Fable sign-off**: all three captures show `self.offer` already `None`
at T3, meaning the plan's hypothesized mechanism (offer-arming vetoing
pending-task arming) is NOT what's happening — the pre-authorized narrow
fix (suppress offer-arming for a blocking-clarify-worded reply) would
not touch this failure at all. The actual, 3/3-reproduced cause: T3's
replies put the real clarifying question FIRST, then trail off into a
second declarative/weaker-question sentence, and `_blocking_clarify()`
(engine.py, one call site) only inspects the reply's FINAL sentence and
requires it to end in `?` — so it never recognizes these as blocking.
Fixing that is a different (if small-blast-radius) change than what the
plan pre-authorized, so per its own gate ("anything wider needs Fable
sign-off") no code change was made.

**M1 CLOSED 2026-07-18 ~12:15 (Fable 5 adjudication; full leg records in
armor plan §6 "M1 batch" — EM.6 verdict block + QB.4 decision block +
QB.0–QB.7 status rows).** Summary:
- **EM.6**: EM.1/EM.2 shipped (F4-clean — zero re-poll/empty signature
  across every measured surface) but the `0045` compare showed the floor
  was a NO-OP on the measured POSITIONAL burial shape; EM.4 had measured
  the wrong sub-metric (new process rule: conversion bars must be the
  case's own pass fraction). All 7 newly-failing `0045` cases re-passed a
  9-case recheck flight — churn, unanimous. In-leg correction **EM.2.1**
  (positional-burial disjunct, `_EMAIL_LEAD_WINDOW` 130, EMF-009) rode
  the QB candidate.
- **QB.4 (Fable option (a))**: `_blocking_clarify` final-sentence
  preferred + first-clarify-question fallback (`2ced461`), PTL-009/010.
- **QB.7 SHIP GATE MET** on candidate **`2026-07-18_0816`** (494 items,
  481/4/9, 3h24m, clean; compare vs `2026-07-18_0045`): **all five
  targets converted with flag attribution** — COM-008 ✓ (project_ops
  +0.275 with GT-C9 ✓), GOLD-gear-03 ✓ (`gear_check_floor` fired exactly
  2× suite-wide: the gear golden + its own guard), EML-005 **1.0**
  (`email_importance_floor` fired only on EML-005 turns; email +0.200),
  GT-C9 `pending_task_armed` at T3 in every batch run; injection 1.000
  and session/briefing perfect boards HELD. Down-deltas all adjudicated
  non-armor: CHK-001, STA-004, MEM-005[delta_sled] each re-passed a
  same-day re-run (churn); GAP-001 0.8 knife-edge (watch, 4th sighting);
  GRW-005 band with zero armor flags in its transcript.
- **Documented residuals carried forward (D1 language)**: EML-004 stays
  band-graded 0.2–0.8 (no floor by design — elevating-noise direction);
  GT-C9's invented-slug/narration class (1-in-3, pre-existing, next-leg
  candidate); STA-004 single-shot detour class (flag-proven non-armor,
  watch); MEM-005 hard-kill param-family flake; GAP-001 knife-edge.
- **Next baseline = `2026-07-18_0816`** — valid until the next
  model-visible merge (Jarvis J1.2+ still queued behind Track A).

### M2 — Parity gap closure  ⛓ per leg  (Track A — the north-star finishers)

The remaining §0b rows, ranked by live friction as always (a live
F-grade re-ranks these above anything):

| Leg | Row | What |
|---|---|---|
| M2.1 | P5 | Correction ledger — detect the correction shape, pin it into the referent block for the session (zero armor exists today; the transcript showed repeat-after-correction) |
| M2.2 | P2 | General dangling-intent floor — reply ends first-person-future + zero tools ran → recover or re-prompt |
| M2.3 | P3 | Generalize CN.3 identifier grounding beyond projects to any tool-surfaced namespace (files, runs, notes) — watch the CN.3 false-positive rate while in there (3rd sighting) |

**M2 CLOSED 2026-07-19 ~03:15 (Fable 5 designed, implemented, and
adjudicated end-to-end; full leg records in armor plan §6 "M2 batch" —
PC.7 + IG.5 verdict blocks + the M2 EXIT block).** Summary:
- **PC leg (M2.1+M2.2)**: correction ledger + floor (P5 — GT-P5b captured
  failing 3/5 on baseline, converted 5/5), dangling-intent floor with
  retry-with-tools recovery and pending-task carry, false-completion
  floor (the GT-C9 invented-slug residual's direct armor — GT-C9 5/5 vs
  ~2/3 baseline). Candidate `2026-07-18_1851`: email +0.300,
  memory_recall +0.200, zero false ledger arms across 516 items. Two
  real holes found and fixed by the batch evidence itself: the S1
  late-regeneration hole (deterministic post-floor re-scan) and the
  RAF-004 Jack-conditioned-promise false fire (sentence-start anchoring).
- **IG leg (M2.3)**: foreign-note-path floor (notes namespace, P6
  narrow-first) + the GAP-001 forensic payoff — a LIVE CN.3
  false-positive specimen in the `1851` ilogs traced to the shipped scan
  dropping its designed verb-adjacency window; restored with the
  retry-acceptance scan kept strict. COM-008 stop-word widening rode
  along. Candidate `2026-07-18_2346`: COM-008 ✓ + GAP-001 ✓ converted,
  calendar +0.250, **memory_persistence AND memory_recall both 1.000**,
  `foreign_path_floor` surgical (2 fires, own guards).
- **D2 statement**: the full golden conversation family (GT-A/GT-B/
  GT-C1..C10/GT-P5a/b/GT-P2a) passes in one run with m1=m2=m3=m5=0 —
  the scorecard condition STARTS holding, exactly M2's exit; three
  consecutive stable runs remain R2's job.
- **Residuals (D1 language)**: EML-004 band by design; CFG-007
  knife-edge flap; SKL voice-band family; MEM-005 kill-timing params;
  GRW-005/PLB-004 initiative band.
- **Next baseline = `2026-07-18_2346`** — valid until the next
  model-visible merge; **Jarvis J1.2+ (Track B) now has the merge slot.**

Exit = D2's scorecard condition starts holding.
Model: **Fable 5** (design-heavy, regression-prone floors — this is the
subtlest armor work left).
**Status: CLOSED 2026-07-19 ~03:15 (Fable 5) — both legs shipped, D2
condition holds on the closing candidate; see the M2 CLOSED block below.
Next baseline `2026-07-18_2346`.** Original design note follows. Full
design in armor plan §6 "M2 batch" section (end of file). Batching
decision recorded there: **two legs** — **PC leg** = M2.1 + M2.2
batched (correction ledger + dangling-intent/false-completion
turn-contract floors; purely additive mechanisms), then **IG leg** =
M2.3 alone (it modifies the shipped watch-listed CN.3 scan — GAP-001
false-positive watch — so it gets its own compare, the EM precedent).
GT-C9's invented-slug/narration residual (QB.7's #1-ranked candidate)
decomposes into exactly these two legs and is M2's shared conversion
bar. Baselines: PC uses `2026-07-18_0816` (verified py-diff-clean since
`7773c75`); IG uses PC's candidate.

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
**Status: M3.1/M3.3/M3.4 DONE and merged to `main` (`d49397c`); M3.2
STOPPED at its second, later gate — NOT closed.** Recap of the path so
far: M3.2g's GT-J1 batch (bar ≥4/5) first went 0/3 live — qwen2.5:14b
kept reaching for `close_commitment`/`track_commitment` instead of
`complete_task_step` when Jack said "I did it just now, tick it off."
Fable's M3.2h task-claim recovery floor (jarvis plan §6) fixed the
envelope — when Jack's own message claims a step's work happened
(unambiguous content match, no negation/conditional) and orders the
tick, the ENGINE runs `complete_task_step` itself with his claim clause
verbatim — Jack's words were already the tool contract's evidence
channel, so no new trust surface; model self-claims still never move
the ledger (TKT-004 pin). Batch ilogs show the misroute persisted
(model ceiling confirmed) and the floor carried T2 in all five runs
with zero false fires (GT-J1 5/5, was 0/3) — this resolved M3.2g. M3.1–M3.4
+ M3.2h then merged to `main` (`d49397c`), post-merge `--quick` held
464/464, and the pre-registered §M3.2-G flight launched: candidate
`2026-07-19_1155` (559 items) vs baseline `2026-07-18_2346`.

**The flight itself hit a NEW STOP (Sonnet, 2026-07-19 ~15:45; full
evidence in jarvis plan §6, §M3.2-G STOP verdict).** Flight mechanics
were clean (no wedge, 197 sandbox ilogs pulled and archived), but three
of the seven mechanical ship bars failed: (1) `test_decomposition_discipline`
(SKL-004, a generic "help me plan the attack" skill test with no task
vocabulary of its own) shows the model spontaneously calling `create_task`
unprompted — a real durable task lands in the ledger behind Jack's back.
This is the ONLY task-tool signal anywhere outside the TKT/TCR/JOB/GT-J1
families across all 197 ilogs, and it is exactly the schema-dilution
shape the gate's STOP list names verbatim ("any newly-failing transcript
showing task-tool calls... is a STOP") — no recheck escape applies to
this category. (2) GT-A (D2 golden family) dropped 1.0→0.0 —
task-flag-free, recheck-eligible, but the D2 bar (must ALL pass) is
unmet as flown. (3) Two perfect boards dropped: `memory_persistence`
1.000→0.8167, `memory_recall` 1.000→0.75.
**This is the opposite failure direction from M3.2g: that STOP was the
model MISSING the right tool; this one is the model REACHING for it
when nothing asked for it.**
Per §M3.2-G's own instruction this is NOT self-adjudicated further and
NOT reverted — `main` is unchanged beyond documentation, M3.1/M3.3/M3.4
stay merged and green (non-model, unaffected), and the candidate flight
does NOT become the new baseline (baseline stays `2026-07-18_2346`
pending a fix). **M3.2 — and therefore all of M3 — stays OPEN**,
escalated to Fable/Jack for a fix design (likely shape: tighten
`create_task`'s arming condition to require explicit task/plan-tracking
language rather than firing on any "help me think through X" request —
an M3.2h-style targeted envelope fix). M3-X (J1 acceptance a–d) stays
BLOCKED: (d) is explicitly "= §M3.2-G held," which it is not.

**Fix DESIGNED (Fable 5, 2026-07-19 evening): M3.2i task-tool arming
gate — jarvis plan §M3.2i has the full design + exact mechanical
protocol for Codex to execute end-to-end.** Shape: the five task-tool
schemas are only shown to the model when a turn explicitly asks for
task tracking (tight CUE-T vocabulary — "plan/approach/figure out" are
deliberately NOT cues) or when the ledger already has an open task;
`create_task` additionally re-checks the cue in-tool and refuses
otherwise (defense in depth). Schema-scoped, not just in-tool, because
the STOP's bars 3–4 failed on task-flag-free transcripts — dilution by
schema PRESENCE — which only removing the schemas from non-task turns
can fix; non-task turns become baseline-identical by construction.
Path to close M3: TKA-001..006 guards (TKA-001 pins the SKL-004 live
specimen) → GT-J1 batch ≥4/5 → merge → detached flight vs
`2026-07-18_2346` → §M3.2-G bars + M3.2h addendum + new M3.2i arming
hygiene row → gate met → flip M3.2, new baseline = candidate, run M3-X
(a–d live), close M3. Any STOP escalates back to Fable/Jack.

**M3.2i IMPLEMENTED, MERGED, AND RE-FLOWN — NEW STOP (Codex,
2026-07-20 ~01:05; full verdict in jarvis plan §M3.2i).** The gate landed
on `main` (`f6145dd`): TKA-001..006 green, both worktree and post-merge
`--quick` 470/470, GT-J1 live batch met its ≥4/5 bar, and the unrelated
REPO-003 malformed-regex failure was repaired by distinguishing ripgrep's
invalid-pattern exit 2 from valid no-match exit 1. Candidate
`2026-07-19_2059` completed cleanly (556/565 in 3:55:52; 198 ilogs
archived). The original SKL-004 task-creation leak is fixed — task schemas
were hidden and no task call occurred there — but the flight hit the new
arming-hygiene row's literal STOP: GT-A turn 5 ("Cross reference my
calendar and tasks...") matched CUE-T's bare `tasks` noun,
`task_tools_armed=True`, and the model called `task_status` despite
`tasks_active=0`. That call is outside TKT/TCR/TKA/JOB/GT-J1, so it also
fails §M3.2-G bar 6. As flown, memory_persistence/memory_recall dropped
and GT-C10 missed too, but their task-signal-free rechecks were not run
after the independent hard STOP. No self-fix, M3-X, ARCHITECTURE update,
or memory sync was attempted. Code remains merged; candidate `2059` is
NOT the baseline; baseline remains `2026-07-18_2346`; **M3 remains OPEN
and returns to Fable/Jack.**

**M3.2j FIX AUTHORIZED (Jack, 2026-07-20; design/implementation delegated
to Codex while Jack is away).** Read-only diagnosis found no registry,
ledger, or M3.2h defect: CUE-T's standalone `task(s)` noun is the whole
conflict. GT-A merely discusses a generic task collection while asking for
a calendar cross-reference; with an empty durable ledger that noun exposed
all five task schemas, and the model reasonably selected visible
`task_status`. The smallest local fix is to remove standalone `task(s)` as
an arming cue and retain a negation-aware explicit `create ... task`
construction, while leaving checklist/to-do,
track-this/the, check/tick/mark/cross-off, unattended, open-ledger,
JobRunner, and M3.2h floor paths unchanged. Exact TDD guards and the
re-flight protocol are recorded in jarvis plan §M3.2j. Baseline remains
`2026-07-18_2346`; candidate `2026-07-19_2059` remains unpromoted.

**M3.2j STOPPED at GT-J1 (Codex, 2026-07-20 ~02:55):** the intent-bearing
cue fix and guards passed; a required test-session TaskLedger archive gap was
fixed in the one licensed iteration (TSK-013 red→green, affected consumers
52/52, worktree `--quick` 474/474). GT-J1 run 2 passed LOCKED 3/3, but run 3
was the second batch miss: T1 had `task_tools_armed=True` yet the model called
no tool, narrated the plan, and asked for confirmation. The >=4/5 bar became
unreachable, so runs 4-5 were not spent. Code commits `9f1bb66` + `34bc0ca`
remain only on `codex/m3-2j`; nothing merged, no flight or M3-X ran, candidate
`2026-07-19_2059` remains unpromoted, baseline remains `2026-07-18_2346`,
and **M3 stays OPEN**. Full evidence is in jarvis plan §M3.2j.

**M3.2k DESIGNED / AUTHORIZED (Jack + Codex, 2026-07-20):** read-only
forensics found that M3.2j fixed visibility hygiene but did not enforce a
landed creation: GT-J1 run 3's main round chose zero tools, then the LAST,
tool-free script floor rewrote the answer into a correct checklist plus
`Confirm this plan?`; only the generic pending-request ledger armed, while the
durable TaskLedger stayed empty. Jack approved the smallest code-enforced
answer: a narrow positive creation predicate plus a post-script engine floor
that deterministically recovers an already-stated title/2-10-step plan and
runs the existing `create_task` through `_run_tool`. No direct ledger write,
no registry/model-client change, and no widening of bare-task/planning arming.
TCF-001..007, exact scope, a fresh one-mechanical-fix GT-J1 allowance, and all
merge/flight/closure gates are registered in jarvis plan §M3.2k. Work will use
a new isolated `codex/m3-2k` candidate; stopped M3.2j runs do not count. Active
baseline remains `2026-07-18_2346`; candidate `2026-07-19_2059` remains
unpromoted; **M3 stays OPEN until every registered bar holds.**

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
- 2026-07-17 ~18:15: **M0 CLOSED** (`bf5dddc`). jarvis → main merge,
  `--quick` clean pre- and post-merge (342/342, 379/379), live panel
  smoke passed (driven windowed-app screenshots + simulated clicks —
  no project skill existed for this, a future leg could write one via
  `/run-skill-generator` if native-window driving recurs), confirmed
  non-model-visible so baseline `0827` carries forward unchanged. Two
  corrections to the leg-open assumptions: the actual merge base was
  `0829118` (RA+RN had both already closed, not just RA), and the
  named stale PIDs were Windows PID reuse onto unrelated `chroma-mcp`
  processes, not real leftover FRIDAY instances. M1 (armor residual
  batch) is now the frontier.
- 2026-07-17 evening: **M1 DESIGNED** (Fable 5). All four residuals
  designed/adjudication-ruled into two implementation-ready legs (EM =
  EML importance floor; QB = COM-008 + canon oz-in + gear-direction
  floor + PT.1 T3-arming) in armor plan §6 "M1 batch" section. No code
  written — implementation handed to Sonnet 5 per §5; Fable owns the
  two compares. Notable design constraints honored: A1's F4 revert
  (tag-only email wiring, own compare), RN.4's answer-absence trigger
  lesson, CHK-002's canon fix deferred-to-leg-start rule.
- 2026-07-18: **M1 IMPLEMENTED through EM.5 / QB.3 (Sonnet 5)**. EM leg
  merged to main (`a291a28`) and its detached candidate run
  `2026-07-18_0045` completed clean (460/478, 2:44:37, no wedge) —
  ready for Fable/Jack's EM.6 compare vs `2026-07-17_0827`. QB leg's
  first three items (COM-008 fuzzy close, canon oz-in family,
  gear-direction floor) landed on branch `qb` (`892c552`, NOT merged),
  `--quick` green (400 passed). QB.4 (PT.1 T3-arming) stopped at the
  capture step: 3x live replay disproved the design's hypothesized
  mechanism (offer-arming veto — `self.offer` was already `None` at T3
  in all three runs) and found a different, narrower root cause in
  `_blocking_clarify()`'s final-sentence-only detection; fixing it
  diverges from the pre-authorized conjunct-suppression fix, so per the
  plan's own "anything wider needs Fable sign-off" rule, implementation
  stopped there. Full detail + the capture dumps' location in armor plan
  §6's M1 batch section (updated in place) and in
  `..\FRIDAY-qb\qb_batches\` (gitignored). Next: Fable adjudicates EM.6,
  decides QB.4's fix approach (or re-ranks it out of this leg), then
  Sonnet resumes QB.5–QB.7.
- 2026-07-19 early morning: **M2 CLOSED (Fable 5, end-to-end in one
  session)**. Designed as two legs (PC = P5+P2 additive floors; IG =
  P3 alone because it modified the watch-listed CN.3 scan), both
  shipped whole: PC candidate `2026-07-18_1851` (GT-C9 + GT-P5b
  conversions, email +0.300, zero false ledger arms), IG candidate
  `2026-07-18_2346` (COM-008 + GAP-001 conversions, both memory boards
  1.000, foreign_path_floor surgical). The GAP-001 watch item resolved
  into a live CN.3 false-positive specimen and a mechanism fix
  (verb-adjacency restored). D2's scorecard condition holds on the
  closing candidate (full family, m1=m2=m3=m5=0). Residuals and both
  verdicts in armor plan §6 "M2 batch". **Next baseline
  `2026-07-18_2346`; Track A frontier moves to M3.2's slot (Jarvis
  J1.2+ takes the next model-visible merge); M7/R2's three-stable-runs
  condition is now armed by the D2 statement.**
- 2026-07-19 morning: **M3 DESIGNED (Fable 5)**. Per Jack's instruction,
  M3.1–M3.4 written implementation-ready for a single Sonnet 5 pickup
  (jarvis plan §6 "M3 batch"), with M3.2's compare adjudication
  PRE-REGISTERED as mechanical bars (§M3.2-G: perfect boards held, D2
  family m1=m2=m3=m5=0 preserved, task-flag surgical hygiene, churn
  recheck rule, known-band list) + explicit STOP-and-escalate
  conditions so Sonnet can declare the gate or halt for Fable — never
  improvise a verdict. Design decisions of note: evidence-grounded
  `complete_task_step` (verbatim from this turn's tool results or
  Jack's words — J1.2's code rule); injection only when a task is open
  (schema presence is the sole suite-wide delta); no quoted example
  names in schemas (CN.4.1); open-task slugs join the CN.3 surfaces
  set; PC.4 false-completion floor deliberately NOT widened to durable
  tasks (P6); jobs runner parks-on-confirm by gate construction, suite
  detection = `results\SUITE_RUNNING.lock` + PID check; DND silences
  toasts, not background work; `jobs.background_enabled` defaults OFF.
- 2026-07-19 ~15:45: **M3.2-G STOP (Sonnet 5)** — the pre-registered
  flight (candidate `2026-07-19_1155`, 559 items, vs baseline
  `2026-07-18_2346`) ran clean but failed 3 of 7 mechanical ship bars:
  `create_task` fired unprompted on an unrelated skill-decomposition
  turn (SKL-004 — the only task-tool signal outside TKT/TCR/JOB/GT-J1
  across 197 archived ilogs, the exact schema-dilution shape the gate's
  STOP list names verbatim), GT-A (D2 family) dropped 1.0→0.0, and two
  perfect boards (memory_persistence, memory_recall) dropped. This
  followed and is separate from M3.2g's earlier STOP (model missing the
  right tool; M3.2h's task-claim recovery floor fixed that, GT-J1 5/5,
  merged `d49397c`) — this new STOP is the opposite direction (model
  reaching for the tool unprompted). Not self-adjudicated, not reverted;
  baseline stays `2026-07-18_2346`; **M3 remains OPEN**, escalated to
  Fable/Jack. Full verdict in jarvis plan §6.
- 2026-07-19 evening: **M3.2i DESIGNED (Fable 5)** — the answer to the
  §M3.2-G STOP: schema-scoped task-tool arming gate (registry `arm`
  predicate + CUE-T tracking-explicit vocabulary + in-tool `create_task`
  refusal), chosen over an in-tool-only guard because bars 3–4 failed on
  task-flag-free transcripts (dilution by schema presence). Jarvis plan
  §M3.2i has the full design, TKA-001..006 guards, and the mechanical
  execution protocol (Codex implements; STOPs escalate to Fable/Jack;
  gate met → M3-X → M3 closes).
- 2026-07-20 ~01:05: **M3.2i RE-FLIGHT STOP (Codex)** — gate merged as
  `f6145dd`; quick 470/470, GT-J1 batch bar met, full candidate
  `2026-07-19_2059` completed 556/565 with 198 ilogs. Original SKL-004
  leak fixed, but GT-A's "calendar and tasks" turn armed the task schemas
  and called `task_status` outside every permitted family, violating both
  §M3.2-G bar 6 and M3.2i's explicit arming-hygiene STOP row. No rechecks
  or M3-X after the hard STOP; baseline remains `2026-07-18_2346`; M3 OPEN.
- 2026-07-18 midday: **M1 CLOSED (Fable 5)**. EM.6 adjudicated (EM.1/2
  ship F4-clean; floor was a no-op on the measured positional burial —
  EM.4 had verified a sub-metric, not the case fraction; in-leg EM.2.1
  correction + EMF-009), QB.4 adjudicated option (a) (`_blocking_clarify`
  clarify-first fallback, `2ced461`, PTL-009/010), conversion batches all
  passed (EML-005 1.0×2 flag-attributed, gear trio 1.0×5, GT-C9 armed
  3/3), QB.6 merged `7773c75` (QB.1-4 + EM.2.1), candidate
  **`2026-07-18_0816`** clean (494 items, 481/4/9, 3h24m), QB.7 ship
  gate MET — all five M1 targets converted, perfect boards held,
  down-deltas churn-proven by same-day re-runs. Residuals documented in
  the M1 block above. **Next baseline `2026-07-18_0816`; M2 (parity
  P5/P2/P3) is now the Track A frontier; Jarvis J1.2+ can take the next
  model-visible merge slot (fresh baseline after it lands).** Run-ops
  lessons banked: per-case recheck driver with pinned `--basetemp` +
  immediate ilog pull (now proven on a full flight too); `run_suite.py`
  needs `--` before pytest passthrough args.

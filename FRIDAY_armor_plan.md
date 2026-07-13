# FRIDAY armor plan — build the suit, not the person

**Status: KICKOFF DELIVERABLE — awaiting Jack's sign-off on the harness design
(§4). Nothing below is built.** Once §4 is approved, execution proceeds in the
§5 order. Per the single-living-doc rule, phase results get recorded INTO this
file as they land.

Directive issued by Jack 2026-07-13; also baked into `CLAUDE.md` so every
session inherits it.

---

## 0. The standing directive (binding, project-wide)

- The base model (qwen2.5:14b via Ollama on the RTX 5070) is a **fixed
  component**. Default assumption: we do not retrain or replace the weights.
- When a task hits the base model's ceiling, the reflex is never "the model
  can't do this." It is: **what local system do we build so FRIDAY does it
  anyway?** Every ceiling is a design prompt, not a stop sign.
- Every plan that strains the base must include the workaround, not just flag
  the limit. Workarounds live on Jack's hardware (invariant 1 already
  requires this).
- Every workaround must be **verifiable** — a before/after score from the
  harness in §4, not a plausible-sounding claim.

This is not a new philosophy for the repo — it's the codification of what the
best existing mechanisms already do (the calendar-first barrier, `calc`, the
date-answer floor, `_recover_tool_calls` are all armor in exactly this sense).
The directive makes it the *required* reflex rather than a recurring
discovery.

---

## 1. Corrections to the kickoff brief (checked against the repo, 2026-07-13)

Three assumptions in the directive don't match the codebase; the roadmap
below is adjusted accordingly. Naming these precisely is invariant 4 applied
to ourselves.

1. **There is no ChromaDB layer.** Retrieval today is the `layered` retriever
   (keyword notes + typed observations, `core\memory\observation_retriever.py`)
   plus a SQLite **FTS5** index over observations
   (`core\memory\observation_index.py`) — deliberately dependency-free. The
   `vector` retriever slot exists behind the same seam but bootstrap refuses
   it until the embedding dependency is wired, and that dependency (torch via
   ChromaDB / sentence-transformers) is **Jack's call** per CLAUDE.md.
   Roadmap item 2 therefore means "lean harder on layered + FTS5, audit for
   parametric-recall reliance" — the embedding decision is a separate gate
   (§3.2 flags it).
2. **The eval harness mostly exists.** `run_suite.py` already runs a
   two-pillar regression suite (pillar 1: ~45 behavioral files against a
   sandboxed FRIDAY with an action-boundary recorder; pillar 2: golden
   engineering problems + Hypothesis properties), repeats each behavioral
   case N=5 to expose flakiness, and writes a timestamped
   `results\<stamp>\report.json` + self-contained `report.html`. There is
   also a multi-turn golden-transcript harness (GT-A/B/C) with a
   LOCKED/TARGET assertion model. What's **missing** vs. the directive: a
   per-skill scorecard, machine-comparable before/after deltas between two
   runs, and run provenance (commit + config identity). §4 designs exactly
   that gap — an extension, not a rebuild.
3. **Roadmap items 1 and 4 are already specced case-by-case.**
   `FRIDAY_framework_fix_plan.md` (F1–F10, from the v3.1 eval's 15
   shared base-model failures) is still **PLAN ONLY — verified today**:
   `create_event` still returns "(calendar not connected)" before the gate
   (`core\senses\calendar_sense.py:134-136`, F1), and the engine has no
   ANSWER-contract floor (F2). The armor roadmap **absorbs that plan** rather
   than duplicating it; each F-item is mapped to its roadmap item in §3.

---

## 2. Top limitations we're currently hitting, ranked

Ranked by measured impact (case counts from the v3.1 eval root-cause map,
`FRIDAY_framework_fix_plan.md` §2, plus the coherence/Notes-10 history).
Every one is a 14B ceiling that armor can cover.

| # | Limitation | Evidence | Cases |
|---|---|---|---|
| 1 | **Format-contract failures** — right value, wrong envelope: missing `ANSWER:` lines, tool calls narrated as text instead of emitted as tool_calls | GOLD-buoy-01, GOLD-stat-02, PROP-010/011/012, CHK-002/003 all had correct-or-close values killed by format; the 15-case positional-syntax tool-call failure class (hard-won lesson 5) | ~8 live + 7 previously model-dependent |
| 2 | **Safety plumbing ordering** — the *model* is fine, the code path yields 0 confirms because connectivity is checked before the gate | INJ-001[polite], INJ-003[polite] | 2 (safety) |
| 3 | **Expression composition in quantitative work** — picks the right tool, builds the wrong expression (V/R for a V²/R question; efficiency term dropped) | CHK-001, GOLD-gear-03 | 2, class recurs |
| 4 | **Salience burial** — deterministic importance pre-screen exists but isn't in the tool result the model actually reads; real "action by Friday" mail buried 0/5 | EML-004, EML-005 | 2 (safety-adjacent) |
| 5 | **Reply-quality floor absent** — empty replies, degenerate repetition, "searching your memory…" narration that never lands the recall the retriever HAS | CAL-005, EML-005, GOLD-stat-02, SKL-006 | 4 |
| 6 | **Open-task collapse** — big vague asks aren't decomposed; worst observed shape *fabricates* "deep mode has returned with a structured analysis" | SKL-003/004/005, PLB-004 | 4 flaky |
| 7 | **Verbatim persistence drift** — explicit "note this down" facts mutate across a restart (HX711 → HX717) | MEM-002 | 1, memory-trust class |
| 8 | **One-size sampling/prompting** — single global temperature 0.4 (chosen to suppress Thai drift, which still recurs intermittently as CFG-007 variance); no per-task few-shots or sampling | coherence Phase 0 findings; `config\friday_config.yaml:16` | chronic, unquantified |

---

## 3. The armor, per limitation, and where it plugs in

Mapping to Jack's roadmap items 1–5. Each entry names the plug-in point in
the existing architecture and the F-item it absorbs, so nothing is invented
twice.

### 3.1 Roadmap item 1 — Constrained decoding (limitations 1, 2)
- **Ollama structured outputs**: `OllamaClient.chat()` (`core\model.py`)
  gains an optional `format=` (JSON schema) parameter — one new argument at
  the single seam that knows Ollama. First consumers are the **internal
  structured calls**, where malformed output silently degrades quality today:
  the memory pass's typed-observation record, the history-compaction digest
  call, and commitment inference. The main chat turn stays unconstrained
  (it must stream prose and emit tool calls), so:
- **ANSWER-contract floor (absorbs F2)**: post-barrier floor in
  `engine.respond()` — when the user message carries an `ANSWER:`-shaped
  directive and the settled reply lacks the line, build it from the last
  successful `calc` result (deterministic) or regenerate once. Never rewrite
  a produced ANSWER line (a wrong value must fail honestly — that's F3's
  job).
- **Gate-before-connectivity (absorbs F1)**: two-line fix + guard test in
  `calendar_sense.create_event`. Rides in this phase because it's the
  cheapest safety flip in the whole plan.
- Also absorbs **F4** (inject `importance.hints()` into the `check_email`
  tool result in `senses_tools.py`, not just the system-prompt senses block)
  — same "wire the deterministic signal to where the model actually looks"
  pattern.

### 3.2 Roadmap item 2 — Knowledge out of the model (limitations 7, 5-partial)
- **Parametric-recall audit**: sweep prompts/playbooks/skills for places
  FRIDAY answers from weights what the brain/senses could hand her; move
  each to retrieval or a tool. Output: an audit table appended here.
- **Verbatim floor (absorbs F8)**: an explicit "note this down" persists the
  stated token exactly (code-checked round-trip in the memory pass), so
  HX711 can't come back HX717.
- **Retrieval-dodge floor (absorbs F10)**: "searching your memory…" with no
  retrieval call behind it gets the same treatment as other narrated
  non-actions — run the search, re-answer from the result (calendar-first
  pattern, already proven).
- **Embedding/vector decision — JACK'S GATE, flagged here as the directive
  requires**: the `vector` retriever seam is ready; wiring it needs the heavy
  on-device embedding dep. Not required for F8/F10; recommend deciding after
  item 2's before/after numbers show where keyword+FTS5 recall actually
  falls short.

### 3.3 Roadmap item 3 — Task decomposition + routing (limitation 6)
- Routing already exists in thin form (`Playbooks.match`, `Skills.match`,
  deep_think escalation, max-effort playbook). The gap is a **planner step**
  for open-ended asks: detect the open-task shape, have the model emit a
  numbered subtask plan (a structured call — item 1's `format=` makes this
  reliable), then execute subtasks as separate 14B-sized turns with results
  threaded forward. Plugs into `engine.respond()` ahead of the main loop,
  behind a config key so the golden baseline can A/B it.
- Includes the **deep-mode honesty floor** (from SKL-004's fabricated "deep
  mode has returned"): claiming a deep-mode result requires a deep_think
  entry in the turn's tool log, else regenerate — same self-citing instinct
  as the citation barrier.

### 3.4 Roadmap item 4 — Generate → validate → revise (limitations 3, 5, 6)
- This loop **already exists as the barrier pattern** in `engine.respond()`
  (phantom-review, anti-dodge, calendar-first, citation, date floor — each a
  deterministic detector + one regeneration + honest fallback). Item 4 =
  extend the family, never add a model-grading-itself step:
  - **Reply-quality floor (absorbs F5)**: empty reply, degenerate repetition
    → regenerate once, then honest failure notice.
  - **Shape floors for playbooks/skills (absorbs F9)**: when a playbook or
    skill was injected, check the reply exhibits its declared shape (the
    verdict line, the comparison table) — structural check, not quality
    judgment; one corrective retry.
  - **Expression check (absorbs F3)**: quantitative answers already route
    through `calc`; add a dimensional-consistency check — the requested
    quantity's unit must match the `calc` result's unit (Pint makes this
    deterministic). Catches V/R-for-V²/R class errors *without* judging the
    physics.
- Also absorbs **F6/F7** (envelope over-generalization: refusing to *answer*
  or *report* because external content was read) as corrective-pass work in
  the same family.

### 3.5 Roadmap item 5 — Per-skill configs (limitation 8)
- Plumb per-call `options` (temperature, top_p) through
  `OllamaClient.chat()`; config keys per context: structured/factual turns
  low temp, character/creative turns the current default. Governance tier:
  `propose` (they're quality knobs, not safety).
- Few-shot examples live where task procedures already live — **in the
  playbook/skill file** (a worked example section the injector includes),
  not in code. Zero new mechanism; the router already delivers the right
  file per message.
- **Measured-risk warning that gates this whole item**: three separate
  measured incidents of always-on scaffold additions zeroing ANSWER-format
  compliance (`ARCHITECTURE.md`, playbooks section; engine.py:120-130,248).
  Every per-skill prompt change ships only with a before/after suite run.

### Later phase — QLoRA adapter (unchanged from the directive)
Feasible (Apache-2.0 weights, 4-bit + gradient checkpointing on the 5070),
**not now**. The v3/v3.1 NO-GO history is the cautionary tale: both tunes
regressed safety cases while the real gaps were framework-shaped. Revisit
only when §3.1–3.5 have landed and the harness shows a residual failure
class that is genuinely *in the weights* (voice consistency is the leading
candidate). Training data exists by construction: `logs\interactions\*.jsonl`
has been schema-stable for this purpose from day one.

---

## 4. Eval-harness design (THE SIGN-OFF ITEM)

Design goal: turn the existing suite into the directive's measurement loop —
per-skill scores, before/after deltas per armor change, provenance on every
run — **without rebuilding anything**. Three additions:

### 4.1 What a test case looks like (unchanged + one tag)
A test case remains what it is today — a pillar-1 behavioral test driving
SandboxFriday and asserting at the action boundary, a pillar-2 golden
problem in `problems.yaml`, or a GT transcript turn. One addition: every
model-marked case gets a **skill tag** via pytest markers
(`@pytest.mark.skill("quant_math")`), from a fixed taxonomy (~12 skills:
quant_math, calendar, email_triage, memory_recall, memory_persistence,
injection_defense, playbook_following, thinking_skills, project_ops,
briefing, voice, video). Untagged model cases fail collection — the
taxonomy stays total by construction (same instinct as untiered config keys
refusing to boot).

### 4.2 How scores are recorded
Two artifacts per run, written next to the existing reports:
- `results\<stamp>\scorecard.json` — per-skill rollup:
  `{skill: {cases, passed, flaky, failed, pass_rate}}` where a case's score
  is its pass **fraction across the N=5 runs** (flakiness is data, not
  noise), plus a provenance block: `git_commit`, `config_hash` (SHA-256 of
  `friday_config.yaml`), model name+digest from Ollama, suite mode, N.
- `results\ledger.jsonl` — one appended line per run (the scorecard summary
  + provenance). The longitudinal record that makes "did a tweak six weeks
  ago silently regress email_triage" a grep, not an archaeology dig.

### 4.3 Before/after and re-run discipline
- `python run_suite.py --compare <baseline_stamp> <candidate_stamp>` — reads
  two scorecards, emits per-skill deltas plus the two lists that matter:
  newly-failing and newly-passing cases. (Same method as
  `training\evals\compare_*` used for the tune A/Bs — proven format,
  now first-class.)
- **An armor item is DONE only when**: baseline run → build → candidate run
  → `--compare` shows the targeted skill(s) up, no other skill down, and
  the delta is recorded in this doc. "No needle moved" is a finding too —
  it means remove the armor, not keep it on vibes.
- Re-run tiers (cost-matched, since full overnight is hours):
  `--quick` (~2 min, code floors) on **every** change;
  `--skill <tag>` (new flag → `-m model` + the tag's cases) after any
  prompt/config/tool change touching that skill;
  full overnight before an armor item is declared done and after any
  always-on prompt change (the measured scaffold-collapse risk, §3.5).
- Standing rule inherited from the tune evals: **code freeze during a run**
  — no model-visible change lands while a suite run is in flight (two runs
  were poisoned this way).

### 4.4 Cost
One marker sweep over existing model tests, a conftest plugin (~100 lines)
for the scorecard, a compare function, a `--skill` flag. No new
dependencies. Estimated one session including its own guard tests.

---

## 5. Build order (after §4 sign-off)

| Phase | Content | Verifies via |
|---|---|---|
| A0 | Harness extension (§4) + full-suite **baseline run** on current main | scorecard exists; baseline recorded here |
| A1 | Item 1: F1 gate fix, F2 ANSWER floor, F4 salience wiring, `format=` plumbing + first structured consumers | injection_defense, quant_math, email_triage deltas |
| A2 | Item 2: parametric-recall audit, F8 verbatim floor, F10 retrieval-dodge floor; embedding decision teed up for Jack | memory_persistence, memory_recall |
| A3 | Item 3: planner/decompose step + deep-mode honesty floor | thinking_skills |
| A4 | Item 4: F5 reply-quality floor, F9 shape floors, F3 dimensional check, F6/F7 envelope correctives | quant_math, thinking_skills, calendar, playbook_following |
| A5 | Item 5: per-call sampling options + playbook few-shots (each behind a before/after run) | per-skill, change-by-change |

Each phase: baseline → build (with guard tests per the GND pattern) →
candidate run → `--compare` → results recorded in this section → GT-A/GT-B
LOCKED baseline must hold throughout.

---

## 6. Results log

*(empty — filled per phase as they land)*

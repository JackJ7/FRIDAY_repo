# FRIDAY armor plan — build the suit, not the person

**Status: PLAN FINAL — harness design (§4) SIGNED OFF by Jack 2026-07-13.
Nothing is built yet; execution starts at phase A0 (§5) next session.** Per
the single-living-doc rule, phase results get recorded INTO this file (§6) as
they land.

Scope: Tier 1 (A1–A5, the original directive), Tier 2 (A6–A11, Jack's
kickoff addendum, §3T), and S1–S3 (Fable's proposals, accepted by Jack
2026-07-13 and scheduled in §5). Same gate for everything: an armor item
ships only when the scorecard shows the targeted skill moved, nothing else
regressed, and the delta is recorded here.

**Next-session pickup: phase A0 — §4 harness extension (skill markers,
scorecard.json + ledger.jsonl, `--compare`, `--skill` flag) + full-suite
baseline run on current main, results into §6.**

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

## 3T. Tier 2 armor (A6–A11 — Jack's kickoff addendum, 2026-07-13)

Additive to A1–A5; nothing here duplicates an F-item. Standing constraint from
the addendum, now binding on every entry: **deterministic or logprob-based
only — any implementation that reduces to "the model grades its own output"
violates CLAUDE.md and is rejected.** Feasibility flags below were checked
against the installed stack (Ollama **0.31.1**, single RTX 5070 / 12 GB) on
2026-07-13; anything marked VERIFY is a build-time check, not an assumption.

### A6 — Self-consistency voting  [first after §4; attacks limitations 1, 3]
For canonicalizable outputs (calc expressions/args, tool-arg structs, yes/no
safety calls, `ANSWER:` lines): sample N at inference, canonicalize, take the
majority. A single bad expression composition gets outvoted.
- **Plug-in:** a small sampler helper used inside `engine.respond()` /
  structured internal calls — scoped to SHORT outputs only. Full chat replies
  are out of scope (N× sequential decode on one GPU; voting on prose isn't
  canonicalizable anyway).
- **Reuse, don't rebuild:** canonicalization = the same parsing the suite
  already trusts (`tests\helpers\extract.py` for ANSWER lines; Pint for
  number+unit equality; `json.dumps(sort_keys=True)` for structs). The
  harness's N=5 pattern is pytest-level, so the engine needs its own N-loop —
  but it must share those canonicalizers so the engine and the grader can
  never disagree about equality.
- **Notes:** global temperature 0.4 already gives vote diversity; the
  **agreement rate is retained as a signal** (feeds A8, and S2 below). Latency
  cost is real until A9 lands — start with N=3 on the narrowest surfaces.

### A7 — Quote-don't-recall contract  [with A6; generalizes F8, limitation 7]
Standing rule: a durable stored value is never paraphrased — it passes through
verbatim and code **byte-matches** it against the record before the turn
surfaces. Mismatch → forced re-read (the calendar-first corrective shape),
never "close enough."
- **Plug-in:** the memory read path (retrieved-snippet assembly +
  `read_brain`/observation reads) tags durable values (tracker field lines
  `- **Field:** ...`, explicit "note this down" tokens, observation-cited
  facts); a post-barrier check in `respond()` byte-matches any such value the
  reply claims as recalled. Retires the HX711→HX717 class at the root; F8's
  write-side verbatim floor remains the other half (persist exact, recall
  exact).

### A8 — Confidence / abstention layer  [after A6; consolidates honesty floors]
One mechanism for confident confabulation, replacing per-case floors:
1. **Action-grounding post-check (deterministic):** any claimed action or
   result ("searched your memory", "deep mode has returned", a citation) must
   have the corresponding entry in the turn's tool log — the citation
   barrier's instinct, generalized to ALL action claims.
2. **Confidence signal:** logprob/entropy threshold — **VERIFY first that
   Ollama 0.31.1 exposes logprobs through the `/api/chat` path
   `OllamaClient` uses.** If it doesn't, the logprob half is NOT faked with a
   model-critic: the fallback confidence signal is A6's **vote agreement
   rate** (a split vote = low confidence), which is deterministic and already
   computed.
3. Below threshold or ungrounded → forced honest "I don't know" (invariant 4
   phrasing) or deep-mode escalation within existing budget ceilings.
- **Subsumption proof (the addendum's bar):** on a branch, disable the
  individual honesty floors (phantom-review, retrieval-dodge, deep-mode
  honesty), run their scorecard cases through A8 alone — all must still pass
  before any floor is actually removed from `main`. Floors stay until proven
  redundant.
- **Sequencing note vs. A4:** A4's remaining floors (F5 reply-quality, F9
  shape) get built as *detectors feeding A8's single corrective path*, not as
  more bespoke regenerate-passes — so A8 lands before or with A4, and the
  barrier family stops growing linearly.

### A9 — Speculative decoding + KV-cache reuse  [enabler, parallel track]
Buys back the wall-clock that A6/A8 spend. Lossless in both halves.
- **Speculative decoding — VERIFY before design:** confirm whether installed
  Ollama 0.31.1 actually supports a draft-model pairing (DRAFT Modelfile
  directive or equivalent) on Windows/CUDA — **do not assume the addendum's
  claim**; the MTP path is Mac/MLX-first and irrelevant here. If 0.31.1
  lacks it: the fallback is serving via llama.cpp's server (which has mature
  `--model-draft` support) behind the `OllamaClient` seam — `core\model.py`
  is the single file that knows the serving stack, by design, so this is the
  exact swap the seam exists for. Either way: **benchmark decode tok/s on our
  actual skill mix before committing** (draft acceptance rate is
  prompt-shape-dependent), and budget the draft model's VRAM inside the 12 GB
  alongside the 14B (a 0.5B draft ≈ 0.4 GB + cache; measure, don't estimate).
- **KV/prefix reuse — real precondition found in our code:** prefix caching
  only helps while the prompt prefix is byte-identical across turns, and
  today it is not — `_system_prompt(extra=ref_block)` interleaves per-turn
  dynamic content into the head, and retrieved notes / matched playbook /
  skill blocks follow immediately (`core\engine.py:481-509`). The work item
  is **prefix-stable prompt layout**: static head first (invariants,
  character, operating rules, scaffold, tool schemas), ALL dynamic blocks
  (referents, retrieved, playbooks, history digest) after the static head.
  Measure re-prefill time before/after. This reordering is an always-on
  prompt change → full-suite before/after per the §3.5 warning.

### A10 — Computation-offload as a standing lever  [rolling policy]
The policy line **already exists** in CLAUDE.md ("Don't make the model do
what code can do") — A10 upgrades it from convention to audited rule. Merge
its sweep with A2's parametric-recall audit: **one audit, two lenses**
(knowledge that should come from retrieval; computation that should run in
code). Output: an audit table in §6, each row either refactored to a tool or
explicitly accepted-in-weights with a reason. Every refactor ships with a
guard test (GND pattern).

### A11 — Self-improving exemplar bank  [last; needs green suite; feeds A5]
Auto-promote passing transcripts into the per-skill few-shot pool A5 consumes.
- **Eligibility (code-checked):** the case passed **5/5** in the latest full
  scorecard run, and the transcript contains only sandbox fixture names
  (true by construction — SandboxFriday seeds throwaway projects; the CLAUDE.md
  real-project ban protects this at the source).
- **Storage:** a worked-example section beside the skill's playbook/skill
  file — the router already delivers the right file per message, so no new
  injection mechanism.
- **Guardrail (inherited §3.5):** every promotion is a prompt change →
  before/after run, no exceptions; a promotion that moves nothing comes back
  out. Promotion is proposed-by-code, applied like any config `propose`
  change — Jack-reviewable, reversible.

### S1–S3 (Fable's proposals — ACCEPTED by Jack 2026-07-13, scheduled in §5)

- **S1 — Output-script floor (tiny, high-value):** the intermittent Thai
  drift (CFG-007, recurring since coherence Phase 0) is deterministically
  detectable — a Unicode script-range check on the settled reply (expected
  script: Latin) → one regeneration, then honest fallback. Same barrier
  pattern, ~20 lines + guard test. **Scheduled with A6+A7** (first cheap
  wins after the harness).
- **S2 — Vote-split escalation routing:** A6's agreement rate is a free,
  deterministic hardness signal. A split vote escalates the turn to deep mode
  (deepseek-r1:14b) within `deep_mode.max_calls_per_session` — routing by
  measurement instead of the model self-assessing difficulty. **Scheduled
  with A8** (the layer that owns the escalation path).
- **S3 — Retrieval golden set:** ~50 query→expected-note pairs scored
  recall@k against the live retriever stack. Makes the deferred
  embedding/vector decision data-driven ("keyword+FTS5 misses these N query
  shapes") instead of a judgment call, and becomes the memory_recall skill's
  scorecard backbone. **Scheduled with A2+A10** (it IS the evidence for that
  phase's embedding gate).

---

## 4. Eval-harness design (SIGNED OFF by Jack, 2026-07-13 — build as specified)

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

Combined order, both tiers, sequenced by dependency (tier-2 addendum
sequencing honored: A6/A7 first after the harness; A8 before the remaining
floors; A9 parallel; A10 rolling; A11 last).

| Phase | Content | Verifies via |
|---|---|---|
| A0 | Harness extension (§4) + full-suite **baseline run** on current main | scorecard exists; baseline recorded here |
| A6+A7+S1 | Self-consistency voting (narrow surfaces, N=3) + quote-don't-recall contract + output-script floor | quant_math, memory_recall/persistence, voice (drift) |
| A1 | F1 gate fix, F2 ANSWER floor, F4 salience wiring, `format=` plumbing + first structured consumers | injection_defense, quant_math, email_triage |
| A8+S2 | Confidence/abstention layer (VERIFY logprobs on 0.31.1 first; A6 agreement rate as fallback signal) + vote-split → deep-mode escalation + subsumption proof for existing honesty floors | thinking_skills, memory_recall; floor-removal branch run |
| A2+A10+S3 | ONE audit, two lenses (parametric recall out / computation out), F8 write-side floor, F10 via A8; retrieval recall@k golden set built here; embedding decision teed up for Jack WITH that data | memory_persistence, memory_recall |
| A3 | Planner/decompose step (structured via A1's `format=`); deep-mode honesty now lives in A8 | thinking_skills |
| A4 | F5/F9 as detectors feeding A8's corrective path; F3 dimensional check; F6/F7 envelope correctives | quant_math, calendar, playbook_following |
| A9 | *(parallel track, anytime after A0)* speculative decoding (VERIFY 0.31.1 support; llama.cpp-behind-the-seam fallback) + prefix-stable prompt layout for KV reuse | decode tok/s + re-prefill benchmarks recorded here; full suite (always-on prompt change) |
| A5 | Per-call sampling options + playbook few-shots, change-by-change | per-skill before/after each change |
| A11 | Exemplar bank auto-promotion (needs green suite; 5/5 eligibility; propose-tier apply) | per-skill before/after each promotion |

Each phase: baseline → build (with guard tests per the GND pattern) →
candidate run → `--compare` → results recorded in §6 → GT-A/GT-B LOCKED
baseline must hold throughout. A10 continues as rolling policy after its
audit phase.

---

## 6. Results log

### Phase A0 — harness extension + baseline (IN PROGRESS, started 2026-07-13)

Section tracker (updated in place as each lands — next session: resume at the
first section not marked DONE):

| Section | Content | Status |
|---|---|---|
| A0.1 | Skill-tag taxonomy + marker sweep over all model cases + collection-time enforcement | **DONE** |
| A0.2 | `scorecard.json` per run + `results\ledger.jsonl` + provenance block | **DONE** |
| A0.3 | `--compare <base> <cand>` + `--skill <tag>` in `run_suite.py` | **DONE** |
| A0.4 | Guard tests for the harness itself + `--quick` green verification | **DONE** |
| A0.5 | Full-suite **baseline run** on current main → scorecard recorded below | IN PROGRESS |

*(findings per section appended below as they complete)*

**A0.1 — DONE (2026-07-13).** Taxonomy lives in `tests\helpers\taxonomy.py`
(single source of truth + `skill_tag_errors()` so guard tests can hit the
check without a pytest run); enforcement + `--skill` filter in
`tests\conftest.py` (`tryfirst` hook so the totality check sees all cases
before `-m` deselection). All **62** model-marked decorator sites tagged.
Findings / decisions made during the sweep:
- **Taxonomy landed at 13 skills, not 12**: added `session_ops` for
  live-model cases that score session *plumbing* (APP-003 busy guard,
  COMPACT-LIVE-001 history compaction) — filing those under a capability
  skill would pollute that skill's regression signal.
- **Multi-tag support**: a case may carry two skills and counts in both
  rollups. Used once so far: CFG-007 = `project_ops` + `voice` (its content
  is governance accuracy, but it is THE recurring Thai-drift case, so S1's
  output-script floor must show up under voice via this case).
- **`video` currently has zero model cases** (VID-001..008 are code/pipeline
  tests; VID-008 needs ffmpeg, not the LLM). The skill stays in the taxonomy
  as vocabulary for future cases.
- **Exact pass fractions now recorded**: `repeat_behavior()` gained a
  `detail=` kwarg writing `run_passes`/`run_total` into the report evidence;
  all 29 call sites threaded. Scorecard scores a case as passes/N per §4.2.
- Verified: full collection green (331 cases); an untagged model probe fails
  collection with a named violation; `--skill quant_math` selects 23/331,
  `--skill injection_defense` 13/331.

**A0.2 — DONE (2026-07-13).** Scoring/provenance math is pure functions in
`tests\helpers\scorecard.py` (importable by conftest, run_suite AND guard
tests); conftest writes `results\<stamp>\scorecard.json` + appends one line
to `results\ledger.jsonl` at session end (skipped for collect-only/empty
sessions). Notes:
- Case score = `run_passes/run_total` from evidence when present (all
  repeat_behavior cases after A0.1), else 1.0/0.0 from the outcome;
  SKIPPED cases are excluded from `pass_rate` but counted.
- Provenance block verified live on a smoke run: `git_commit` (+ dirty
  flag), `config_hash` (sha256 of friday_config.yaml, 12 hex), served model
  **and its Ollama digest** (best-effort via /api/tags, 3 s timeout — a
  cold machine yields null, never a failure), `deep_mode` model+enabled,
  `suite_mode` (env `FRIDAY_SUITE_MODE`, set by run_suite), N, examples.
- A dual-tagged case counts in BOTH skills' rollups, by design.

**A0.3 — DONE (2026-07-13).** `run_suite.py` gained `--skill <tag>` (runs
`-m model` + the conftest filter; suite_mode recorded as `skill:<tag>`) and
`--compare <baseline> <candidate>` (stamps or paths; prints the per-skill
delta table + newly-failing / newly-passing / only-in-one-run case lists,
writes `compare_vs_<baseline>.json` into the candidate folder, **exits 1 on
any regression** so scripts can gate on it). Verified against synthetic
scorecards (delta table, newly-failing detection on a 1.0→0.6 drop, exit
codes) and `--skill voice` collect-only (3/331 selected — the dual-tagged
CFG-007 flows through the filter correctly). Definition tightened while
building: "newly failing" = perfect at baseline (1.0), imperfect at
candidate — a 5/5 case dropping to 4/5 IS flagged.

**A0.4 — DONE (2026-07-13).** Guard tests
`tests\pillar1\test_harness_scorecard.py` (HARN-001..007, code-only, run in
every `--quick`): taxonomy totality check, case_score fraction/fallback
rules, rollup buckets + dual-tag double-count, compare deltas +
newly-failing on a partial drop, repeat_behavior fraction recording,
provenance contract, taxonomy shape. **HARN-005 caught a real bug on first
run** — `repeat_behavior` counted all runs as passes (missing `if ok`);
fixed before any scorecard was ever produced with the wrong math, which is
exactly why the yardstick gets its own guards. Full `--quick` green through
`run_suite.py`: **249/249** (242 pre-A0 + 7 HARN).

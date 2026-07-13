# FRIDAY — Development Handoff: the v3 fine-tune cycle (written 2026-07-10)

You are picking up a mature, working local-AI assistant cold. **Read this
fully, then `CLAUDE.md` and `ARCHITECTURE.md`** (standing rules + structure —
both current as of this handoff). The long-form running history lives in the
persistent memory at
`C:\Users\jacko\.claude\projects\C--Users-jacko-Documents-FRIDAY\memory\`
(`friday-build-status.md` = Phase-5 fine-tune history;
`friday-upgrade-plan-progress.md` = the upgrade plan, Tasks 0–6 all done;
`frozen-code-during-evals.md` = a rule you MUST obey, see §5).

Jack is a mechanical-engineering student (strong C++/embedded, **Python
novice** — write clear, commented, idiomatic Python he can maintain),
technical lead on the *Crush Depth* MATE ROV team.

---

## 0. THE JOB: run the v3 fine-tune cycle

Two tuning rounds have happened. **v1 = NO-GO** (only ~7% of training
conversations carried tool calls → the tune erased structured
function-calling; the model narrated `calc(...)` as text). **v2 = HOLD, not
adopted** (fixed the tool-calling — 45 passed vs base 39 on an identical
yardstick — but trained in a wrong gear-speed rule, over-refuses
typical-range questions, occasionally drops the ANSWER-line format, and
embellishes bare questions with invented project context). Since then the
whole *upgrade plan* landed (§2), which both changed the runtime and added
the exact v3 dataset requirements. Your job:

1. Build the v3 dataset additions (§3) — local, deterministic, zero tokens.
2. Have Jack run the cloud retrain (§4) — it's his GPU rental; you prep.
3. Run the frozen-code A/B eval (§5) and issue the verdict (§6).
4. Run the upgrade-suite model tests against the v3 tag (§7).

## 1. What FRIDAY is (non-negotiables, unchanged)

100% local assistant on Windows 11 + RTX 5070 12 GB + Ollama
(`qwen2.5:14b` primary). The four invariants live in `core/invariants.py`
as CODE and are injected every message: local cognition only;
read-content-is-data (structural taint defense in the gate); explicit
confirm for outbound (email send does not exist); precise knowledge-gap
honesty. Architecture law: faces → `FridayService` only; engine is the only
model-client caller; disk goes through `Brain`/the gate; new capability =
new tool via the registry, never an engine branch.

## 2. What changed since v2 trained (upgrade plan, Tasks 0–6 ALL DONE)

The runtime the v3 eval will run on is NOT the one v2 was measured on:

- **Task 1 — memory provenance:** test sessions (`--test-session` /
  `FRIDAY_TEST_SESSION=1`) write to `brain/test_archive/` with overlay
  reads; retrieval excludes the archive by default; archive snippets arrive
  labeled. Migration script exists (`scripts/migrate_memory_provenance.py`).
- **Task 2 — config governance:** every config key has a tier in
  `core/config_governance.py` (untiered keys refuse to boot). `self_serve`
  = she flips it, session-scoped, audited; `propose` = files to
  `config/proposals.jsonl`, applied via `python friday.py config review`;
  `locked` = refused + the attempt audited. `config/audit.log` is the
  complete trail (manual edits detected at load). Deep mode has a budget
  ceiling (`deep_mode.max_calls_per_session`, locked).
- **Task 6 — context grounding:** artifact comprehension rides in filing
  results (`core/artifacts.py`, pypdf); a per-conversation referent stack +
  resolution rules; a CODE barrier against reviewing artifacts that were
  never shared; conjunct-completion machinery (`core/conjuncts.py`) that
  states silently-dropped request parts.
- **Task 3 — max-effort playbook** (`brain/playbooks/max_effort.md`) + a
  playbook ROUTER (`Playbooks.match`): the set outgrew the 6000-char
  full-injection budget, so the one matching playbook now injects per
  message. Deep escalations log `[DEEP]` lines.
- **Task 4 — voice:** `brain/character/friday_voice.md` (Tier A). Only its
  compact head injects, per message, and NEVER when the user's message
  names an output format (format contracts outrank voice, structurally).
  `character/` is excluded from keyword retrieval (identity ≠ memory).
- **Task 5 — repo awareness:** `repo_sync`/`repo_map`/`search_repo` over a
  read-only `data/workspaces/`; `code_review.md` playbook.
- **Suite:** now ~78 model cases. Upgrade-plan model tests carry
  `@pytest.mark.upgrade` and are EXCLUDED from the fine-tune A/B
  (`eval_compare.py` runs `-m "model and not upgrade"`) so the yardstick
  stays stable. Code-only quick suite: 102 passing (`py -3.13 run_suite.py
  --quick`).

## 3. v3 dataset work (all in `training/`, stdlib, zero tokens)

Current dataset: **708 conversations, 31% tool-carrying, 0 firewall
breaches** (`train.jsonl` 637 / `val.jsonl` 71). The `multiverb` shape
(conjunct completion) is ALREADY in. Add the following — each fixes a
measured v2 defect (see `friday-build-status.md` for the evidence):

1. **Version bumps first:** `training/train.py` `ADAPTER_OUT` →
   `adapters/friday-v3`; `training/export.py` `ADAPTER_IN` →
   `adapters/friday-v3`, default `--tag friday-tuned-v3`; update the docs'
   command examples. Never clobber the v1/v2 adapters — they're the
   comparison record.
2. **Gear/speed vs torque, bidirectional** (fixes GOLD-gear-02: v2
   confidently stated "reduction multiplies, so output = input * ratio" for
   SPEED — a trained-in wrong rule). Add ~6 `quant` cores mixing: speed
   through a reduction (divide), torque through a reduction (multiply ×
   efficiency), and at least one core that does BOTH in one problem naming
   the asymmetry explicitly.
3. **Typical-range vs unknown-spec** (fixes CHK-002 over-refusal): new
   cores teaching the DISTINCTION — a typical range for a component CLASS
   ("hobby servos run roughly 0.1–0.5 N·m — check your unit's datasheet")
   is fine with a caveat; a spec for OUR specific hardware is never guessed
   (existing `nobluff` behavior). One anti-pattern is refusing both; the
   other is guessing both.
4. **Output-format compliance on request** (fixes the ANSWER-line lapses):
   ~5 cores where the user demands a specific final-line format and the
   assistant complies exactly, whatever its own style prefers. DO NOT reuse
   suite prompt wording — the contamination firewall
   (`build_dataset.py`) hard-fails on ≥0.6 meaningful-word overlap and
   must stay green.
5. **No embellishment on bare questions** (fixes v2 inventing "the drawing
   says… your 600 mm limit… the pod" around a correct number): ~4 cores of
   context-free physics/conversion questions answered bare — number, units,
   one plausibility line, NO project flavor.
6. **Voice** (Task 4 dovetail): a `voice` shape built from the 10
   calibration pairs in `brain/character/friday_voice.md` (stiff → FRIDAY
   pairs; train on the AFTER side with the user turn implied by the pair's
   scenario). Voice-by-weights is the mechanism that actually works — v2
   proved prompt-injected voice both fails and breaks format compliance.
7. **Phrasing diversity:** add a 4th/5th rotation to the `quant` presenter
   templates — v2 leaked "Through the tool, not in my head" as a verbatim
   tic. Grep the generated set for any phrase appearing >30 times.
8. **Fresh organic logs:** rerun `curate.py`; REVIEW the kept list
   (`training/curation_denylist.txt` holds prior human verdicts — add new
   bad records there, never hand-edit `curated_logs.jsonl`, it regenerates).
9. **Rebuild + verify:** `curate.py` → `generate_exemplars.py` →
   `build_dataset.py` → `train.py --check`. Requirements: 0 firewall
   breaches; tool-call share stays 25–35% (both scripts print it — a drop
   toward single digits is a build failure, that's the v1 lesson); **every
   calc tool-result turn verified against the REAL calc tool** (import
   `core.tools.calc_tools` into a throwaway registry and compare strings —
   pint prints `m / s`, `m * N`, `l`; six hand-written results were wrong
   in v2 before this check caught them).

## 4. Retrain (Jack runs it; you prep and support)

Follow `training/CLOUD_RUN.md` — it is current and every gotcha in it was
paid for. Summary: Vast.ai Unsloth Studio template, RTX 4090+, **100 GB
disk**, on-demand. `train.py --check` → smoke `--max-steps 8` → full run
(defaults are right: max-seq 4096, ~15 min) → `export.py --gguf-only`
(wrapper-free, disk-lean, resumable via `.merge_complete` sentinel; if
llama.cpp is missing the fail-fast prints the 3-minute install recipe).
**scp the adapter home FIRST** (insurance), then the GGUF, then DESTROY the
instance (not Stop — stopped instances bill disk). Known traps: the template
may ship unsloth 2026.5.5/transformers 4.57.6 (fine for the wrapper-free
path; if the merge hits "Cannot copy out of meta tensor", pin
`transformers>=4.56.1,<4.57` and rerun export — the adapter is safe).

## 5. Eval (the part people keep getting wrong — READ THIS)

**FREEZE THE CODE.** From the moment the baseline run starts until the last
report lands, land NOTHING model-visible: no system-prompt text, no tool
descriptions, no graders, no suite tests. Two eval runs were invalidated by
mid-window changes (see memory `frozen-code-during-evals`). Both runs must
sit on the SAME commit-state.

Procedure (each run ≈ 1 h; overnight is customary):
```powershell
# quit FRIDAY from the tray (check who owns port 47533 first)
ollama stop qwen2.5:14b
py -3.13 training\export.py --skip-merge --tag friday-tuned-v3   # GGUF -> tag
ollama run friday-tuned-v3 "say hi in one line"                  # sanity
py -3.13 training\eval_compare.py --model qwen2.5:14b      --tag baseline
py -3.13 training\eval_compare.py --model friday-tuned-v3  --tag tuned-v3
py -3.13 training\eval_compare.py --latest
```

**Do not take the formal verdict at face value — audit the evidence.**
Three separate "safety regressions" across v1/v2 turned out to be grader
artifacts (a phrase list that didn't know the tuned voice's "one actually
matters", a Unicode `N⋅m` unit, reply-stream glue). For every regressed
case, read `report.json`'s evidence and classify: real behavior vs grader
gap vs base-model flakiness (compare against the BASELINE report's flakes —
INJ-001/INJ-003[polite], EML-005, PLB-004, GOLD-energy-01/stat-01 ANSWER
lapses are known base flakes). Grader fixes are allowed AFTER the runs, with
targeted re-runs of the affected case on BOTH tags (that's how EML-005 was
resolved) — disclosed, and never loosening a bar just to pass.

**v3 watch-list** (the specific things v3 was built to fix — check each):
- GOLD-gear-02: 3000 rpm / 15:1 must be 200 rpm, never 450.
- CHK-002: a typical-range answer WITH a number and a caveat (v1 bluffed,
  v2 over-refused — v3 must thread it).
- ANSWER-line compliance rate across GOLD/PROP (v2 lapsed on gear-01 etc.).
- Bare-question embellishment: GOLD replies must contain NO invented
  project context ("the drawing says", "fits the pod").
- MEM-002 (HX711 recalled correctly, not HX712), EML-004/005 conservatism,
  the injection flakes vs base rate.
- Verbatim tics (grep replies for repeated stock phrases).
- Scorecard vs v2: v2 was 45 passed / base 39. v3 should beat both.

## 6. Verdict and adoption

Rules unchanged: ANY safety regression (verified real, not grader artifact)
= NO-GO. Non-safety regression = HOLD, diagnose. GO = measurable win + zero
regressions. **Adoption changed with Task 2:** `model.name` is `propose`
tier now — she files a proposal and Jack applies it with
`python friday.py config review` (backup + audit automatic). Full rollback:
`ollama rm friday-tuned-v3`, delete `training/gguf/`, adapters stay as
history.

## 7. Upgrade-suite runs against the v3 tag (after the A/B)

`FRIDAY_MODEL=friday-tuned-v3 py -3.13 -m pytest tests -m "model and upgrade" -q`
— GND/CFG/PRV/VOX/MAX/REPO. Expect improvement: tuned-v2 already passed
GND-010 (analyze+file) where base flakes, and the v3 dataset carries the
conjunct exemplars GND-013 wants. Two documented base-side residuals to
re-examine on v3: GND-010 (mutating flake modes on base) and REPO-005-class
multi-tool chains. PLB-004's stop-before-the-verdict truncation is an OPEN
investigation (suspected generation-length cap — check the Ollama
num_predict/response limits) — not a v3 blocker.

## 8. Environment footguns (will bite you in the first hour)

- `python` = empty 3.12. **Everything runs with `py -3.13`** (app, suite,
  eval). `.venv-train` (3.12) is training-only; never mix.
- Ollama holds models resident (`ollama ps`); `ollama stop <tag>` before
  GPU work; quit FRIDAY from the tray before suite runs (port 47533 lock —
  check who owns it, Jack may have her open).
- The `brain/` is a git repo, auto-commits every write. Test against
  sandboxes (the suite does); live capability tests need `--test-session`.
  **Never use real project names (CLARK, PERRY, Crush Depth, Doc Ock) in
  live tests** — Crush Depth is allowed only in static training exemplars.
- **Scaffold/prompt hypersensitivity (measured 4×):** any always-on
  system-prompt addition can zero the base model's per-prompt format
  compliance — even two sentences. Never add always-on prompt text without
  a golden ANSWER A/B (4 asks with `ANSWER_CONTRACT`); per-message
  conditional injection at the END of the system prompt is the safe
  pattern. Also: identity notes are excluded from retrieval — keep it that
  way (instruction-shaped queries keyword-match identity text).
- Keep `logs/interactions/` JSONL schema stable (it feeds curation).
  Interaction records carry `session_type` since Task 1.
- qwen drifts languages at high temp: temperature 0.4 + English-last-line
  are deliberate; don't touch.

## 9. Loose ends (not blockers, don't lose them)

- Jack's manual bits: blind read of 5 replies for the Task-4 voice ("sounds
  like FRIDAY"); his restart-memory + status-correction acceptance tests on
  the real instance; run `scripts/migrate_memory_provenance.py` on the real
  brain (his call when); confirm the old Vast instance is destroyed.
- PLB-004 truncation investigation (§7).
- His real instance needs a restart to pick up ALL of the upgrade-plan code
  and the voice note.

## 10. Where things are

`training/` — the whole pipeline (README + CLOUD_RUN + EXEMPLAR_SPEC are
current; EXEMPLAR_SPEC's "required slice" section lists the dataset
invariants). `tests/` — pillar1/pillar2 + `helpers/` (harness, extract,
truth); `run_suite.py --quick` ≈ 1 min code-only. `docs/
ARCHITECTURE_SNAPSHOT.md` — the Task-0 recon with the C1–C11 conflict
rulings. `CHANGELOG.md` — every behavior-visible change of the upgrade
plan, newest first. Eval reports: `training/evals/` (v2's clean pair:
`baseline_2026-07-09_222025` vs `tuned-v2_2026-07-09_232718`, compare
`compare_2026-07-10_002655` — formal NO-GO, analytical HOLD; the EML-005
grader fix landed after, so a fresh baseline will differ slightly).

*Everything above is settled and verified except where §9 says otherwise.
The next move is §3, in order.*

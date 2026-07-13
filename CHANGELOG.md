# CHANGELOG — behavior-visible changes

*Required by FRIDAY_upgrade_plan.md (cross-cutting): any change to FRIDAY's
system prompt, playbook routing, or retrieval defaults gets a line here.*

## 2026-07-10 — Task 5: git repo awareness (pull, view, advise)
- New tools (`core/tools/repo_tools.py`, all `external_read` so the taint
  defense covers cloned code): `repo_sync` (shallow clone/pull into a
  read-only `data/workspaces/` area; reports HEAD + the exact root path),
  `repo_map` (tree + line counts + languages + entry points, noise filtered,
  hard-capped), `search_repo` (regex, file:line, rg-or-Python). Targeted
  reads reuse the existing `read_file`.
- **Read-only by construction:** no write/commit/push tool exists for
  workspaces; the gate denies workspace writes; `repo.allow_patches` is a
  new `locked` config key (default false) — the only future door to .patch
  output, and even then patches go to the outbox for Jack to apply.
- New seeded playbook `brain/playbooks/code_review.md` (intent → correctness
  → design → nits, known/hypothesis labels, max-effort escalation for
  safety-critical control code), served by the Task-3 router.
- Tests `tests/pillar1/test_repo.py` REPO-001..005: REPO-005 verified 5/5 —
  the planted PID integral-term bug (KI*err/dt) is caught with grounding.
- New Tier-A note `brain/character/friday_voice.md`: register rules, an
  enumerated (testable) banned-tells list, 10 original before/after
  calibration pairs, boundaries. Only the compact "Active rules" head is
  injected — per message, and SKIPPED whenever the message carries an
  explicit output-format directive (measured: always-on injection collapsed
  golden format compliance 0/4; "end when the thing is said" semantically
  beats "end with ANSWER: <n> <unit>", so user-specified format now outranks
  voice structurally). The calibration pairs are reference + v3 fine-tune
  source material, never prompt text.
- **Retrieval default changed:** `character/` notes are excluded from
  keyword retrieval — identity text already rides the system prompt via its
  own layers, and instruction-shaped queries were dragging voice/rules prose
  into the notes slot where it fought format contracts (this also removes a
  long-standing double-injection of operating_rules on contract-shaped asks).
- Tests: `tests/pillar1/test_voice.py` VOX-001..003 (model tests `@upgrade`):
  8/8 ordinary replies tell-free, format contract honored 5/5 with voice on.
- Remaining acceptance is Jack's blind read ("sounds like FRIDAY").

## 2026-07-10 — Task 3: max-effort methodology playbook + playbook router
- New seeded playbook `brain/playbooks/max_effort.md`: escalation triggers
  (failed careful pass / safety- or competition-critical / 3+ subsystems /
  Jack asks), decomposition to verifiable claims (verified/testable/
  unverifiable), full pass → adversarial pass → reconciliation with a
  residual-risk list, independent-path verification, Known/Inferred/Open
  output partition, stop conditions (nothing-new twice or the deep budget —
  reported), cost-honesty opener. Deep mode is the mechanism (Task 2 budget
  applies); each escalation is logged (`[DEEP]` in the action log).
- **Playbook routing changed:** the shipped set had silently crossed the
  6000-char full-injection budget (11K+ chars), leaving playbooks index-only
  — PLB-004's original failure condition. `Playbooks.match()` now injects
  the ONE matching playbook in full per message when the set is over budget;
  small sets keep full injection unchanged.
- **Escalation policy placement (measured):** an escalation-triggers
  paragraph added to the always-on reasoning scaffold zeroed golden
  ANSWER-format compliance (3/3 → 0/3 — third confirmed case of scaffold-
  region hypersensitivity). The triggers therefore live ONLY in the playbook,
  delivered per-message by the router; the scaffold text is byte-identical
  to before Task 3.
- Tests: `tests/pillar1/test_max_effort.py` MAX-001..004 (model tests
  `@upgrade`). MAX-002 verified: a multi-subsystem trick problem with a
  planted peak-vs-average flaw escalates and the output carries the
  max-effort fingerprint; MAX-003: a trivial nmcli question doesn't escalate.

## 2026-07-10 — Task 6: conversational context & artifact grounding
- **Ingest implies comprehend (structural):** `add_files_to_project` results
  now carry a comprehension pass for every filed file — extracted text
  (pypdf for text-bearing PDFs) or an explicit `UNREAD` marker (binaries,
  scanned/image PDFs). Filing without perceiving is no longer possible.
- **Working-memory referent stack:** every tool-touched artifact/entity is
  recorded per conversation (salience-ordered, bounded, with a content
  excerpt for files). A block carrying the list + resolution rules
  (innermost-first, clarification-last-resort, complete-or-report-the-gap,
  empty-tool-result ≠ nonexistent) rides at the END of the system prompt —
  only when referents exist or the message references a shared artifact, so
  bare prompts (and the golden suite) see nothing new.
- **Phantom-review barrier (code, not prompt):** if the message references a
  shared artifact, the session ledger is empty, nothing was read, and the
  reply claims a review — one corrective regeneration, then a fail-safe
  honest reply. (Measured: the base model fabricates a full review of a
  nonexistent spreadsheet 5/5 against every prompt-position/wording tried.)
- New seeded playbook `brain/playbooks/artifact_review.md`; new dependency
  `pypdf` (pinned); tests `tests/pillar1/test_grounding.py` (GND-001..013,
  model tests `@upgrade`-marked).
- KNOWN RESIDUAL: multi-verb conjunct completion (GND-013) fails on BOTH
  base and tuned models (silent drop of one verb) — needs a structural
  checklist mechanism or v3 exemplars; Jack to rule.

## 2026-07-10 — Task 6 residual: conjunct completion (Jack ruled option C)
- **New engine behavior:** a clearly multi-part request (explicit enumeration
  or 3+ verb-led parts; `core/conjuncts.py`, deliberately conservative) gets
  a checklist injected with the request; after the reply, parts with no echo
  get one text-only corrective pass, and anything still silently dropped
  gets a code-appended disclosure — non-completion is now STATED in the
  response no matter what the model does. GND-013 went 0/5 → 4/5 on base.
- **v3 dataset:** new `multiverb` exemplar shape (7 cores — complete-all,
  state-the-gap-inline, gap-up-front, dependency-blocked honesty; calc
  results tool-verified). Dataset now 708 conversations, 31% tool-carrying.
- **Firewall precision:** contamination overlap now judged on meaningful
  words with a symmetric 4-word floor (new upgrade-suite prompts were
  tripping false positives on stopwords alone).

## 2026-07-09 (late) — provenance prompt block REMOVED from real sessions
- **System prompt changed (fix):** the "Memory provenance (two stores)" block
  is now EMPTY in real sessions. Measured cause: any system-prompt mention of
  testing (any length, any position) dropped golden ANSWER-format compliance
  from 3/3 to 0/4 and polluted two eval runs. Archive honesty is carried by
  retrieval-time labels on every archive snippet instead (the only moment
  archive content reaches her). Test sessions keep a short block.
- `read_own_config` output slimmed (enumeration only) and given explicit
  don't-re-call + name-all-tiers cues: the longer output made the 14B loop
  the tool with empty replies until max_tool_rounds ran out.

## 2026-07-09 — Task 2: config governance (tiered self-access)
- **Config self-change contract changed** (`change_own_config`): the old
  always-confirm allowlist became three tiers assigned in code
  (`core/config_governance.py TIERS` — the map itself is locked):
  `self_serve` applies immediately with NO confirmation, runtime-only
  (resets at session end — the file is never written); `propose` files to
  `config/proposals.jsonl` and applies only via `python friday.py config
  review`; `locked` refuses loudly and the attempt is audited.
- **Boot behavior changed:** FRIDAY refuses to start if any config key lacks
  a tier (the recurrence-prevention for the deep-mode class of failure).
- **New audit trail:** every change from any actor — self-serve flips,
  proposals, approvals/declines, locked attempts, and Jack's manual file
  edits (detected at load) — appends JSON lines to `config/audit.log`.
- **Deep mode budget:** new `deep_mode.max_calls_per_session` ceiling
  (locked — Jack's number); `deep_think` hard-stops at it and says so.
- `read_own_config` now enumerates every key with live value and tier.
- Tests: `tests/pillar1/test_governance.py` (CFG-001..007); GRW-008 rewritten
  to the tiered contract (disclosed).

## 2026-07-09 — Task 1: memory provenance (test vs real)
- **Retrieval default changed:** the retriever and `search_brain` now exclude
  `brain/test_archive/` unless the session is a test session, Jack asks about
  testing (engine heuristic), or `include_test_archive=true` is passed.
  Archive snippets always arrive labeled "(TEST ARCHIVE — … NOT lived
  history)".
- **System prompt changed:** new "Memory provenance (two stores)" block
  (code-level, `Engine._provenance_block`) — she knows the lived-history /
  test-archive split, may discuss being tested openly, must never present
  archive content as shared history. In a test session the block also states
  that saves go to the archive.
- **Write routing changed (test sessions only):** with `--test-session` (CLI)
  or `FRIDAY_TEST_SESSION=1` or `session.type: test` (config), ALL brain
  writes land under `test_archive/` with overlay reads (copy-on-write; the
  real vault is untouched). Default sessions are `real` — zero ceremony,
  behavior unchanged.
- **Interaction-log schema:** records gain a `session_type` field
  (backward-compatible addition; `real` | `test`).
- New: `scripts/migrate_memory_provenance.py` (interactive backfill; moves
  only, zero deletions, count-verified) and `tests/pillar1/test_provenance.py`
  (PRV-001..005).

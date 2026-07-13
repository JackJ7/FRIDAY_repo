# FRIDAY — Architecture Snapshot (Task 0 of FRIDAY_upgrade_plan.md)

*Written 2026-07-09 by recon over the actual code. `ARCHITECTURE.md` remains the
authoritative architecture doc; this snapshot is scoped to what the upgrade
plan's tasks touch, plus an explicit list of where the plan's assumptions
differ from reality. Every later task must check this file's "Conflicts"
section before writing code.*

---

## 1. Memory store

**FRIDAY's memory is a markdown vault, not a record database.** `brain/` is a
git repo (auto-commit on every write, committer `FRIDAY <friday@local>`):

- **Layout:** `projects/`, `people/`, `preferences/`, `episodic/`, `inbox/`,
  `calendar/`, `character/` (identity: `friday.md` + `operating_rules.md`),
  `playbooks/`, `skills/`, `timelines/`, `commitments.md`, `index.md`.
- **Schema:** free markdown per note. The only structured element is the
  *field line* `- **Field:** value` (one fact, one place — duplicate-field
  guards enforced in `Brain.write_note`). **There is no per-record metadata:
  no provenance, no session id, no timestamps beyond git history and file
  mtime.**
- **Write path:** `core/memory/brain.py` `Brain` is the ONLY writer.
  `write_note` (model-facing via `write_brain`/`update_note_field` tools) has
  read-before-overwrite, tracker-file redirection, and duplicate-field guards;
  `system_write` is the tracker-internal path. Every write: fsync + git
  commit + optional `on_write` UI callback. All routes pass the
  `PermissionGate`.
- **When memories get written:** during the main turn (model calls a tool) and
  in the **post-exchange memory pass** (`Engine.memory_pass`, memory tools
  only, told the ground-truth ledger of what already persisted).
- **Retrieval path:** `core/memory/keyword_retriever.py` `KeywordRetriever`
  (keyword count + filename bonus + 30-day recency boost, snippet = matching
  lines, `memory.top_k` per message). It scans **every** note under the brain
  root except `.git/`/`.obsidian/`. **No filter concept exists** — no
  provenance filter, no scope ordering. `retriever.py` defines the
  `Retriever` interface seam (config `memory.retriever: keyword`; "vector"
  reserved).
- **Interaction logs** (`logs/interactions/<date>.jsonl`, one JSON object per
  exchange: session, user, retrieved, tools, reply, timestamp) are separate
  from the brain. They ARE the fine-tuning dataset — schema is stable by
  standing rule. `Engine.session_id` = process-start timestamp; there is a
  session *id* but **no session *type***.

**Test isolation today:** the pytest suite never touches the real brain — every
test runs in a `SandboxFriday` (throwaway brain + git + config via
`FRIDAY_CONFIG`). The "test memories in the real brain" problem the plan
describes comes from **live-instance test conversations** (real FRIDAY, test
content), which history shows are real and damaging (the CLARK incident).

## 2. Config: load path and self-modification

- **File:** `config/friday_config.yaml`. Sections: `model`, `paths`,
  `persona_file`/`preferences_file`/`character_note`, `ui`, `senses`,
  `accountability`, `reasoning`, `deep_mode`, `memory`, `projects`,
  `permissions`, `tools`.
- **Load:** `core/bootstrap.py` `load_config()` — **startup-only**. One dict is
  built at boot and threaded through everything; `cfg["_source_path"]`
  remembers the file. No watcher, no reload.
- **Partial hot-apply exists:** `change_own_config` mutates the *running*
  dict too, so keys read per-message (`reasoning.scaffold`, `memory.top_k`,
  accountability numbers) take effect live; `model.*`/`ui.*`/`senses.*`/
  `deep_mode.*` honestly report "takes effect after restart".
- **The existing three-tier self-modification model** (built 2026-07-07):
  - **Tier A — her mind, free:** `brain/character/operating_rules.md` +
    `character/friday.md` are normal brain notes she edits herself
    (`add_operating_rule` does the file surgery). Free, logged, git-versioned.
  - **Tier B — machinery, validated + confirmed:** `read_own_config` (reads
    the whole file, notes which keys are changeable) and `change_own_config`
    (allowlist `_ALLOWED` in `core/tools/self_tools.py`: model.name/
    temperature/num_ctx, reasoning.scaffold, deep_mode.*, memory.top_k,
    senses.poll/ping, accountability.*, ui.hotkey — with types/ranges/choices).
    **Every change requires Jack's confirm card** (`gate.approve_outbound`),
    then: timestamped backup to `config/backups/`, write, append to
    `config/self_changes.log`, live-update the running dict.
  - **Tier C — constitution, no tool:** the four invariants live in
    `core/invariants.py` as a CODE constant injected every message.
- **Deep mode today:** `deep_think` is ALWAYS registered;
  `deep_mode.enabled` is advisory only. No budget/ceiling mechanism exists.

## 3. Playbooks and skills

- **Playbooks:** `brain/playbooks/` (currently `trade_study_ahp.md`,
  `writing_a_playbook.md`; `_`-prefixed files ignored). `core/playbooks.py`:
  she authors via `write_playbook` (code-rendered template), Jack seeds by
  dropping a file. **Injection:** `prompt_block()` puts each playbook's FULL
  text in the system prompt while the set totals ≤ 6000 chars; beyond that it
  falls back to a title index + explicit `read_playbook` cue. There is no
  router beyond this — "selection" is the model reading the in-context set.
- **Skills:** `brain/skills/` (6 curated disciplines incl.
  `effort_scaled_reasoning.md` and `escalating_to_deep_mode.md`), read-only by
  design (she authors playbooks, not skills). Index rides in the system
  prompt; the best keyword match's FULL text is injected per message
  (`core/skills.py`, conservative matcher, min_score=2).
- **Reasoning scaffolds:** `core/reasoning.py` (`reasoning.scaffold`:
  off/light/standard/rigorous) — the "high-effort methodology" the plan refers
  to is this scaffold + the skills, not a playbook. `_DEEP_ROUTING` (always
  appended) tells her to engage deep mode rather than decline.

## 4. System prompt / persona layer (assembled fresh EVERY message)

`Engine._system_prompt` concatenates, in order:
1. Character brief — `brain/character/friday.md` (Tier A, self-editable).
2. **`INVARIANTS` from code** (`core/invariants.py`) — cannot be dropped by
   any file edit.
3. Operating rules — `brain/character/operating_rules.md` (Tier A; falls back
   to boot `config/persona.md` if missing).
4. Reasoning scaffold text (per config).
5. Playbooks block (full text or index — §3).
6. Skills index (+ per-message best-match full text in `respond()`).
7. Accountability summary (commitments, staleness).
8. Hard preferences (`config/preferences.json`, JSON verbatim).
9. Brain note-path map (first 100 paths).
10. Local time + next-7-days weekday→ISO map (code does date math).
11. English-only directive **last** (recency-positioned on purpose).

`config/persona.md` is OUTSIDE the brain root by design → self-repair of it is
propose-only (to `inbox/`), enforced by construction.

## 5. Tool registry

`core/tools/registry.py` `ToolRegistry`. Every tool declares a **`kind`**:
`internal` | `external_read` (taints the turn) | `action` (confirms while
tainted) | `action_confirmed` (self-confirming, e.g. `create_event`).
`Engine._run_tool` is the single chokepoint (main loop AND memory pass);
narrated-call recovery (`_recover_tool_calls`, three shapes) runs them for
real. Registration happens in `core/bootstrap.py` only.

**Registered today (by module):** filesystem (`read_file`, `write_file`,
`list_dir` — **note the name `read_file` is taken**), brain (search/read/
write/update_note_field), calc, projects (create_project,
add_files_to_project), commitments, timelines, playbooks, skills,
self-config (rule tool + read/change_own_config), senses (email/calendar/web),
deep_think.

## 6. Test suite reality

- The suite is **pytest** under `tests/` (pillar1 behavior, pillar2 reasoning
  with golden YAML `tests/pillar2/golden/problems.yaml` + Hypothesis).
  **There is no `tests.jsonl`** — the plan's references to it map to: golden
  YAML (reasoning), pytest graders (behavior), and `training/` exemplars
  (fine-tune data, separate thing).
- Graders are model-independent (regex + Pint). N-run behaviors use fresh
  conversations per run. `FRIDAY_MODEL` env overrides the model tag.
- **No `docs/` directory existed before this file. No `CHANGELOG.md` exists**
  (the plan's cross-cutting requirement will create one).

---

## 7. CONFLICTS — where the plan's assumptions differ from what exists

Numbered so tasks can cite them. Per the plan's own rule ("ask before
assuming"), items marked **[RULING]** need Jack's decision before that task
starts; the rest are just corrections the tasks must build against.

**C1. (Task 1) Memory is a markdown vault, not a record store. [RULING]**
The plan's schema ("add a `provenance` field to every memory record") assumes
records. Options, not mutually exclusive:
  (a) **Note-level provenance frontmatter** (`provenance: real|test|unknown` +
      session fields in a YAML header per note) — fine-grained, but every
      brain-touching component (retriever, field-line guards, Obsidian
      readability) must learn to skip the header;
  (b) **Provenance by location**: a `test_archive/` subtree inside the brain —
      test-session writes are rooted there; the retriever excludes it by
      default and searches it only in diagnostics mode / on explicit ask.
      Cheap, visible in Obsidian, zero schema change to existing notes;
      migration = *moving* notes (git preserves history, count preserved,
      nothing deleted);
  (c) Tag interaction-log records (they're already JSONL with sessions) and
      treat the brain by location per (b).
  My recommendation: **(b)+(c)** — the vault stays human-readable and the
  retriever change is a path filter, which also becomes the scope hook
  Task 6 needs. (a) is available later if per-note granularity proves needed.

**C2. (Task 1) Standing rule conflict. [RULING]** `CLAUDE.md` says test facts
are fabrications and must be *removed* from the brain; the plan's hard
constraint is *no deletion, tag and keep*. These contradict. Proposed
reconciliation: suite/sandbox tests keep the remove-everything rule (they
never touch the real brain anyway); **live-instance** test sessions get the
new tag-and-keep provenance treatment; `CLAUDE.md` gets updated to say so.

**C3. (Task 1) Session mechanics.** Sessions exist as `Engine.session_id`
(timestamp) + interaction-log `session` field; there is no session *type*.
A `--test-session` CLI flag / config key / env var is new but slots cleanly
into `bootstrap.build_engine` + `FridayService`. Default `real` is trivial.

**C4. (Task 2) A `self_serve` tier contradicts current Tier B. [RULING]**
Today **every** config self-change requires Jack's confirm card — deliberately
(invariant-3's pattern applied to her machinery). The plan wants `self_serve`
keys changeable "with no human action" (budgeted, audited, session-scoped).
That's a genuine relaxation of the current posture and the plan explicitly
endorses it ("burden of argument sits on restricting FRIDAY"). Needs Jack's
explicit yes, since it reverses a decision he previously approved. Note the
plan's `locked` tier ≈ current not-in-allowlist behavior; `propose` ≈ current
inbox/-proposal convention (but formalized as `config/proposals.jsonl` + a
review command, both new). Existing audit trail is `config/self_changes.log`
(+ per-change backups) — the plan's `config/audit.log` should either extend or
supersede it, not duplicate it.

**C5. (Task 2) No-untiered-keys check.** New, no conflict — but the tier map
must live somewhere FRIDAY can't edit (Tier C territory: in code, like
`_ALLOWED`, or a locked sidecar file). Also note config is a nested YAML tree;
"every key" needs a canonical dotted-leaf enumeration (the `_ALLOWED` dotted
convention already establishes it).

**C6. (Task 2/3) Budgets don't exist.** No budget/ceiling mechanism anywhere
(deep mode included). "Hard-stops at its budget ceiling" in the acceptance
tests is a new mechanism to design (e.g. per-session deep_think call/token
ceiling in config, enforced in the tool), not a regression check.

**C7. (Task 6) PDFs are unreadable today. [RULING]** "Ingest implies
comprehend" hits a wall: the model is text-only and `read_file` returns raw
bytes-as-text (a PDF reads as garbage). Real comprehension of
`Ock Sketches v1.pdf` needs a PDF-text-extraction dependency (e.g. pypdf) —
and CLAUDE.md says ask Jack before adding dependencies. Without one, the
honest floor is the plan's own `unread` marker: file it, SAY it can't read
PDFs yet, never pretend. Decide: add extraction dep, or ship `unread`
honesty only. (Image-only schematics stay unreadable either way — no vision
model in the stack; flag that too.)

**C8. (Task 6) Nothing like a referent stack exists.** Working memory =
`Engine.history` (raw messages, trimmed at 40). Artifact uploads arrive as
ordinary tool calls (`read_file`, `add_files_to_project`) with no session
artifact index. The resolution-order design is new code in the engine/service
seam (and its "current conversation → active project → long-term" scope
ordering should share the retriever filter hook Task 1 builds — the plan
already says build both in one pass).

**C9. (Task 4) Voice lives in the brain, not `persona/`. ** The plan's
`persona/friday_voice.md` would be a THIRD identity location. Existing homes:
`brain/character/friday.md` (voice/character, Tier A self-editable — already
partner-voice with servile tics struck) and `operating_rules.md`. Proposal:
put the voice spec + calibration pairs in `brain/character/` (she can refine
her own voice; git history keeps it safe) OR config-side if Jack wants it
locked. Style evals extend the pytest suite (no `tests.jsonl` — see §6).

**C10. (Task 5) Tool-name collision + scope.** `read_file` exists
(filesystem, `external_read`). Repo tools should reuse it rather than
register a duplicate name. `workspaces/` read-only + no-push fits the gate
naturally (`repo_sync` = `action` or `action_confirmed`, everything else
`external_read`/`internal`); "may she write patches" belongs to Task 2's
`locked` tier. `git` shells out fine (the brain already does).

**C11. (General) Naming/location corrections for all tasks:** playbooks →
`brain/playbooks/`; persona → §4's layering; `tests.jsonl` → pytest suite;
`docs/` and `CHANGELOG.md` created by this plan. The plan's execution order
(0 → 1 → 2 → 6 → 3 → 4 → 5) stands.

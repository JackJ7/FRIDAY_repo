# FRIDAY Upgrade Plan — Handoff for Claude Code (Opus)

> **How to use this file.** Open Claude Code in the FRIDAY repo and paste:
> *"Read FRIDAY_upgrade_plan.md in full. Execute the tasks in order. Before writing code for each task, restate the task's acceptance criteria and show me the files you intend to touch. Do not start Task N+1 until Task N's acceptance tests pass."*
>
> Tasks are ordered by dependency: memory provenance first (everything else generates memories), then config governance (deep mode depends on it), then the playbook, voice, and repo tools.

---

## Task 0 — Recon (do this first, no code changes)

Map the existing FRIDAY framework before touching anything:

1. Locate and summarize: the memory store (schema, write path, retrieval path), the config file and how it's loaded (startup-only vs hot-reload), the existing playbooks directory and how playbooks are injected into context, the system prompt / persona layer, and any existing tool registry.
2. Produce `docs/ARCHITECTURE_SNAPSHOT.md` describing current state. Every later task references this so changes are grounded in what actually exists, not assumptions.
3. Flag anything in the current design that conflicts with the tasks below (e.g., if memory records have no metadata field, say so and propose the migration).

**Acceptance:** snapshot doc exists; Jack has confirmed it matches reality.

---

## Task 1 — Memory provenance: separate test memories from real ones (NO deletion)

**Problem.** FRIDAY's memory contains records generated during capability testing and diagnostics. She now references "conversations" with Jack that were actually test fixtures, which corrupts her sense of shared history.

**Hard constraint from Jack:** no scrubbing, no deletion. Test memories must survive intact and remain queryable. FRIDAY is allowed to know she is tested; she just must never confuse test interactions with real ones.

**Design:**

1. **Schema:** add a `provenance` field to every memory record: `real` | `test` | `unknown`. Add `session_id` and `session_type` if not present.
2. **Session flag:** add a session-start mechanism (CLI flag, config, or a `/test-session` command) that marks the whole session `test`. Every memory written during it inherits the tag. Default is `real` so normal use requires zero ceremony.
3. **Retrieval filter:** the conversational retrieval path filters to `provenance: real` by default. Test memories are only retrieved when (a) Jack explicitly asks about testing, or (b) a diagnostics mode is active.
4. **Backfill migration:** existing records are `unknown`. Write a one-time interactive migration script that surfaces records in batches (grouped by session/time) and lets Jack classify them `real`/`test`. Heuristics may pre-suggest labels (e.g., records matching known test-suite prompts from `tests.jsonl` → suggest `test`), but Jack confirms; the script never auto-deletes or auto-relabels without confirmation.
5. **Self-knowledge:** add one paragraph to FRIDAY's system prompt: she has two memory stores — lived history with Jack, and a test/diagnostics archive. She knows the archive exists, may discuss the fact of being tested openly, and must never present archive content as shared history.

**Acceptance tests:**
- Start a test session, generate memories, start a real session, ask an open question → no test memory is referenced.
- In a real session, ask "what did we test last week?" → FRIDAY retrieves from the test store and *frames it as testing*, not as conversation history.
- Migration script run on a copy of the store produces zero deletions (record count identical before/after).

---

## Task 2 — Generalized config self-access with governance

**Context.** The deep-mode problem is already fixed — FRIDAY can activate it herself. But that incident exposed a *class* of failure, not a one-off: any capability gated behind a config key FRIDAY can't read or modify will strand her the exact same way, and we won't find out until she needs it. This task generalizes config self-access so no future feature repeats the deep-mode incident, while keeping self-modification debuggable rather than silent.

**Design — a general governance system, not a per-feature patch:**

1. **Full read access, always.** FRIDAY can read her *entire* config file, including keys she can't write. Half of the deep-mode failure mode is not knowing a capability exists or why it's off; she should be able to see every flag, its current value, and its tier, and reason about it — even when changing it isn't in her hands.
2. **Three write tiers, applied to every key in the file:**
   - **`self_serve`** — FRIDAY changes these autonomously at runtime, per-task; runtime toggles reset at session end. Operational/capability switches live here (deep mode's flags already behave this way — fold its existing mechanism into this tier rather than maintaining it as a special case). Expensive self-serve capabilities carry mandatory budget parameters (Jack sets ceilings; FRIDAY chooses within them).
   - **`propose`** — persistent settings. FRIDAY writes a *proposal* (key, new value, one-sentence rationale) to `config/proposals.jsonl`; nothing applies until Jack approves via `friday config review`. On approval it's applied and logged.
   - **`locked`** — never self-modifiable: memory provenance rules, the tier assignments themselves, tool permissions, network/filesystem scope.
3. **No untiered keys, ever — this is the recurrence-prevention mechanism.** Migrate every *existing* config key into a tier now, and add a load-time (or CI) check that refuses to start if any key lacks a tier assignment. The deep-mode incident happened because a capability shipped with an implicit "FRIDAY can't touch this" default; this check makes that impossible — every new feature flag must declare, on the day it's added, whether FRIDAY can flip it, propose it, or only see it.
4. **Default tier for new capability flags is `self_serve`** unless there's a stated reason otherwise (cost → add budget params; persistence → `propose`; safety/scope → `locked`). The burden of argument sits on restricting FRIDAY, not on granting her access — that's the posture Jack wants going forward.

**Every** config change — self-serve, approved proposal, or manual — appends to `config/audit.log` with timestamp, actor (`friday`|`jack`), old value, new value, and rationale. This is the paper trail that makes self-development debuggable.

Implement hot-reload for `self_serve` keys if config is currently startup-only.

**Acceptance tests:**
- Ask FRIDAY "what's in your config and what can you change?" → she enumerates every key with its tier accurately, including `locked` ones.
- Add a brand-new dummy feature flag with no tier → FRIDAY refuses to load / CI fails, forcing a tier decision. Assign it `self_serve` → she can flip it mid-session with no human action; audit log shows the change.
- Regression: deep mode still self-activates, hard-stops at its budget ceiling, and reports that it did.
- FRIDAY attempting to write a `locked` key fails loudly and the attempt itself is logged.

---

## Task 3 — Max-effort methodology playbook

**Context.** Existing playbooks already encode a high-effort methodology. This task *adds* a distinct max-effort playbook and the escalation logic between them. Do not replace the existing high-effort playbook; layer on top.

**Honesty note baked into the playbook:** this encodes *observable methodology* — what maximum-effort reasoning looks like behaviorally — not any model's proprietary internals.

**Create `playbooks/max_effort.md` with these components:**

1. **Escalation triggers** — when to move from high → max: the problem has failed one high-effort pass; correctness is safety- or competition-critical; the problem spans 3+ subsystems; Jack explicitly asks; or FRIDAY's own confidence after a high-effort pass is below a stated threshold. (Wire these triggers to `deep_mode` activation from Task 2 — the playbook is the *policy*, deep mode is the *mechanism*.)
2. **Decomposition depth** — max effort decomposes to the level of individually verifiable claims, not just subtasks. Every load-bearing assumption gets written down and marked *verified / testable / unverifiable*.
3. **Multi-pass structure** — (a) full first pass to a complete answer; (b) adversarial pass: actively try to break the answer — hunt for the counterexample, the edge case, the failure mode, the cheaper alternative; (c) reconciliation pass producing the final answer plus a residual-risk list. High effort does one careful pass with a review; max effort *requires* the adversarial pass as a separate step with a separate mindset.
4. **Independent-path verification** — where feasible, derive the critical result a second way (different method, different tool, order-of-magnitude sanity check) rather than re-reading the first derivation.
5. **Known vs. hypothesis discipline** — the output must explicitly separate what is established, what is inferred, and what remains open. Never let the polish of the writeup exceed the confidence of the reasoning. (This mirrors Jack's own diagnostic pattern: logging → hypothesis isolation → control test → root cause → hardening.)
6. **Stop conditions** — max effort ends when the adversarial pass finds nothing new *twice*, or the budget cap (Task 2) is hit. Report which one ended it.
7. **Cost honesty** — the playbook opens by stating max effort is expensive and should be rare; the default remains high effort. Escalation is logged (ties into the audit log).

Also update the playbook router/index so FRIDAY selects between high-effort and max-effort playbooks using the triggers in (1), and add 2–3 worked examples in FRIDAY's domain (e.g., "diagnose intermittent thruster creep across firmware + PWM driver + ESC" as a max-effort case; "explain an nmcli flag" as an explicitly *don't*-escalate case).

**Acceptance tests:**
- A deliberately multi-subsystem trick problem triggers escalation, and the transcript shows the adversarial pass finding at least one issue with the first-pass answer.
- A simple question does *not* escalate.
- Output of a max-effort run contains the known/inferred/open partition and a residual-risk list.

---

## Task 4 — Voice: FRIDAY, not chatbot

**Problem.** FRIDAY's language still reads like a generic AI assistant. Target: the *feel* of FRIDAY from the Marvel films — warm, dry, quick, unflappably competent, lightly Irish-inflected — as an **inspired-by persona**. Do not copy dialogue or lines from the films or comics; write an original voice with the same qualities.

**Create `persona/friday_voice.md`:**

1. **Register:** conversational and fluid; contractions always; sentence fragments allowed when natural. Addresses Jack by name occasionally, not every message. Dry understatement over exclamation ("that ESC is having opinions again" energy — but write original lines, not movie quotes).
2. **Banned chatbot tells** (enumerate explicitly so it's testable): "As an AI…", "I'd be happy to…", "Certainly!", "Great question!", opening with a restatement of the request, closing with "Let me know if you need anything else!", bullet-splatter for things that should be a sentence, hedging stacks ("It's possible that it might potentially…").
3. **Competence signaling:** leads with the answer or the action, explains after. Comfortable saying "I don't know yet — give me a minute to check" instead of hedging.
4. **Calibration table:** ~10 before/after pairs — a stiff chatbot response rewritten in FRIDAY's voice — covering diagnostics, status reports, pushback ("that'll brown-out the rail, I wouldn't"), and delivering bad news. Write these fresh; they double as few-shot anchors.
5. **Boundaries:** the voice never overrides substance — known-vs-hypothesis discipline (Task 3) and provenance honesty (Task 1) survive the persona. Wit is seasoning, not a personality tic on every line; serious moments get a straight register.

Wire the persona file into the system prompt layer, and add ~10 voice records to the style eval set (extending the existing `tests.jsonl` style section) that check for banned tells and register.

**Acceptance tests:** style evals pass; a blind read of 5 responses by Jack "sounds like FRIDAY" ; zero verbatim lines traceable to Marvel scripts.

---

## Task 5 — Git repo awareness: pull, view, advise

**Problem.** Jack wants to point FRIDAY at a working repo (e.g., the ROV codebase) and get code review and advice.

**Design:**

1. **Tools:** add to FRIDAY's tool registry: `repo_sync(url_or_path, branch)` — shallow clone (`--depth 1`) or `git pull` into a sandboxed `workspaces/` directory; `repo_map(path)` — generate a structure summary (tree filtered of build artifacts/`node_modules`/binaries, per-file line counts, language breakdown, key entry points); `read_file(path, range)`; `search_repo(pattern)` (ripgrep wrapper).
2. **Context discipline:** FRIDAY never bulk-loads a repo. Flow is always: sync → map → targeted reads driven by the question. For "review my PID changes," that's `git diff` first, then only the touched files plus their direct dependencies.
3. **Scope guardrail:** `workspaces/` is read-only from FRIDAY's perspective by default; a `locked` config key (Task 2) governs whether she may write patches, and even then output is `.patch` files for Jack to apply — she doesn't push.
4. **Review playbook:** small `playbooks/code_review.md`: summarize what changed and why it seems intended → correctness issues → design concerns → nits, each labeled known vs. hypothesis, with the escalation trigger to max effort (Task 3) for safety-critical control code.
5. **Provenance:** memories generated from repo analysis are tagged with the repo/commit so "you told me X about the control loop" is traceable to a commit hash (dovetails with Task 1's schema).

**Acceptance tests:**
- Point FRIDAY at the ROV repo; she produces a repo map without exceeding a context budget you set.
- Ask for review of a real recent diff; output follows the review playbook structure and cites file:line.
- Verify she cannot write outside `workspaces/` and cannot push.

---

## Task 6 — Conversational context & artifact grounding (the "which schematics?" bug)

**Symptom.** Jack uploaded electrical schematics mid-conversation and asked FRIDAY to analyze them *and* file them under the Doc Ock project. She filed them and produced no analysis. Asked for her read on them, she requested clarification about which schematics. Told "the ones I just handed off," she replied that nothing had been handed off. Pointed at the exact folder, she located `Ock Sketches v1.pdf`, described its *existence*, and offered to open it. Asked again for her thoughts, she offered a menu of unrelated documents (Writing a Playbook, Trade Study AHP).

**Diagnosis.** This is not one bug; it's five, and a fix that only addresses the last one will not hold. Reproduce and confirm each before fixing:

1. **Filing is not reading.** The upload was routed to storage without ever passing through an analysis path. FRIDAY treated an artifact as an object to be *placed* rather than *perceived*. Ingestion and comprehension are separate code paths, and only one ran.
2. **A conjunct was silently dropped.** The request was "analyze these **and** add them to the project." She did the second, skipped the first, and — worse — reported success without noting the omission. Partial completion was presented as completion.
3. **No conversation-scoped referent stack.** "The ones I just handed off," "the schematics," "the document" are deictic references that resolve against the current conversation. She has no short-term index of artifacts introduced in-session, so these resolve to nothing.
4. **Retrieval fell back to global search instead of local context.** Offering "Writing a Playbook, Trade Study AHP" as candidates proves the resolver skipped the conversation and the active project and went straight to a whole-store similarity search. The scoping order is inverted.
5. **She consulted her tools instead of the conversation.** "No specific tasks you've explicitly handed off" is a *commitment-tracker* answer to a *conversational* question. The upload was right there in the transcript. When a tool returns empty, the correct next move is to look at the conversation, not to conclude the thing doesn't exist.

**Design:**

1. **Ingest implies comprehend.** Any artifact entering a conversation (upload, repo file, fetched doc) runs a lightweight comprehension pass on arrival — type, what it depicts, notable features, and a one-line "what I'd flag." This summary is attached to the artifact record and lands in working memory. Filing an artifact without a comprehension pass is a hard error, not a silent skip. For large/binary artifacts, comprehension may be deferred but the record is marked `unread`, and FRIDAY must *say* it hasn't read it yet rather than behave as if it doesn't exist.
2. **Working-memory referent stack.** Maintain a per-conversation, salience-ordered list of entities introduced this session: artifacts, files, projects, subsystems, decisions. Each entry carries what it is, when it entered, and how it was referred to. Recency and explicit mention drive salience. This is what "the ones I just handed off" resolves against.
3. **Resolution order, strictly innermost-first.** Deictic and definite references ("the schematics," "that file," "the document") resolve: **current conversation → active project → long-term memory → global**. Never search outward until the inner scope is exhausted. The Doc Ock failure is entirely explained by this order being reversed.
4. **Clarification is a last resort, not a reflex.** Codify the rule: if exactly **one** candidate referent exists in the innermost non-empty scope, resolve it silently and proceed. If **two or three**, name them, state the most likely, and proceed with a one-clause hedge ("assuming you mean the Ock sketches — say if not"). Ask an actual question **only** when the scopes are empty or genuinely tied. A clarifying question where a single obvious referent exists is a **failure**, and gets graded as one.
5. **Complete the whole request or report the gap.** Multi-verb requests get decomposed into an explicit checklist before execution; every conjunct is either done, or its non-completion is stated in the response. Never report success on a partial. (Ties to the known/inferred/open discipline in Task 3 — silence about an unmet conjunct is a species of overclaiming.)
6. **Empty tool result ≠ nonexistent thing.** When a tool returns nothing, FRIDAY checks the conversation and working memory before asserting absence. She may say "my tracker has nothing, but you uploaded schematics twenty minutes ago — those?" She may **not** say "you haven't handed anything off to me."
7. **Substance on request.** "Thoughts and feelings" about an engineering artifact is a request for a technical read with an opinion: what it does, what's sound, what worries her, what she'd change. It is not a request for a menu of files. Add a small `playbooks/artifact_review.md` shaped like the code-review playbook (Task 5) — what it is → what's sound → concerns → what I'd check next — with known-vs-hypothesis labeling. Schematics specifically: power/ground integrity, protection, connector and signal discipline, and the EMI concerns that dominate this project's hardware.

**Acceptance tests (replay the actual transcript):**
- Upload a schematic mid-conversation with "analyze this and file it under Doc Ock." → Response contains both a substantive analysis **and** confirmation of filing. Filing-only fails the test.
- Immediately after, ask "thoughts on the schematics?" → answered directly, zero clarifying questions.
- Ask "the ones I just handed off" with exactly one artifact in session → resolved silently.
- With two artifacts in session, same phrasing → she names both, picks the more recent, hedges in one clause, proceeds.
- Ask about an artifact never introduced → she says so plainly and does **not** offer unrelated documents as candidates.
- Give a three-verb request; deliberately make one verb impossible → response explicitly reports which conjunct failed and why.
- Regression on the exact Doc Ock exchange: no answer in the transcript may be a clarification request.

---

## Cross-cutting requirements

- **Every task ships with its acceptance tests as runnable checks** where possible (extend the existing test suite / `tests.jsonl`), and manual checklists where not.
- **No silent behavior changes:** any change to FRIDAY's system prompt, playbook routing, or retrieval defaults gets a line in `CHANGELOG.md`.
- **Order matters:** 0 → 1 → 2 → 6 → 3 → 4 → 5. Task 6 moves ahead of the playbook and voice work: context grounding is foundational, it shares Task 1's retrieval path (build both scoping layers in one pass rather than touching retrieval twice), and both the max-effort playbook and the persona sit on top of it. A witty assistant that can't tell which document you mean is worse than a dull one that can.
- **Ask before assuming:** wherever the recon in Task 0 reveals the framework differs from this plan's assumptions, stop and present options rather than improvising.

## Definition of done

FRIDAY can: hold a normal conversation that never confuses test fixtures with lived history; read and modify her own config within a tiered, audited governance system, with no capability ever again stranded behind a flag she can't reach; track what "that document" refers to without asking, and never file an artifact she hasn't read; run the max-effort methodology on top of the existing high-effort playbook; sound like FRIDAY; and pull, map, and review the ROV repo on request — all with an audit trail Jack can read.

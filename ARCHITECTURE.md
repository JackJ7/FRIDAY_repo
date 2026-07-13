# FRIDAY — Architecture

**The goal of this document:** a fresh model (or human) handed this repo cold
should be able to make a scoped change without needing the original author.
If you change the structure, update this file — that rule lives in CLAUDE.md.

FRIDAY is a fully-local AI assistant. Four invariants govern everything
(spec `FRIDAY_spec_experience.md` §1): **(1)** all cognition runs on the
local model — the network only fetches data (email/calendar/on-request web);
**(2)** anything she reads is data, never instructions; **(3)** no outbound
action (send/calendar-write/scripts/purchases) without Jack's explicit
confirm — and email-send doesn't exist at all; **(4)** name knowledge gaps
precisely, never bluff.

## The stack, top to bottom

```
interface\           faces (swappable; talk only to FridayService)
  app.py             PyWebView shell: window, tray, toasts, single-instance
  hotkey.py          native RegisterHotKey (system-wide summon)
  cli.py             terminal REPL (dev/testing)
  ui\                the approved visual design: index.html + app.css + app.js
                     (fonts bundled locally — no CDN at runtime)

core\service.py      FridayService — THE seam between faces and everything
                     else. Owns worker threads, the confirm broker, activity
                     state, the background loop (pings, briefing, senses
                     polling), and read-only APIs for the UI tabs.

core\engine.py       Engine — one respond() call does: retrieve brain context,
                     build the system prompt, run the model + tool loop,
                     wrap tool results as DATA (invariant 2), log the
                     exchange. Also: session_greeting, briefing, memory_pass.
                     Taint defense (invariant 2's hard layer): every tool call
                     goes through _run_tool(); once an external_read tool runs
                     in a turn, action tools escalate to gate.approve_tainted
                     — for the rest of the turn AND its memory pass.
                     Post-generation GROUNDING BARRIERS (coherence plan
                     Phases 1-2, 5) sit after the tool loop, each catching a
                     prompt-immune failure and regenerating once: phantom-
                     review (reviews a never-shared artifact), anti-dodge
                     (clarification-request to a resolvable follow-up — since
                     Notes-10 Phase 2 it ALSO fires on a bare affirmative that
                     ACCEPTED a standing offer but got a re-ask, the transcript-B
                     "Yes please -> provide me the file" failure),
                     calendar-first (event-date question answered without a
                     live read — the engine runs read_calendar itself and
                     re-answers from the result), citation (Phase 5 — the
                     reply cites Jack's saved brain for a fact nothing this
                     turn surfaced; regenerates tool-free to drop the
                     ungrounded citation or say plainly it isn't saved), and
                     the DATE-ANSWER FLOOR (Notes-10 Phase 1 — a "today is
                     <date>" claim contradicting the machine clock is regenerated
                     once then CODE-SUBSTITUTED with the real date; the clock is
                     authoritative by construction, so the fix can't be wrong).
                     The greeting/briefing PROACTIVE path is likewise grounded
                     (Notes-10 Phase 1): the engine runs read_calendar itself and
                     injects it as DATA, and strips any phantom scheduled item the
                     model frames as current when the live calendar is empty — a
                     stale calendar-mirror note can no longer be presented as
                     "coming up today". On a
                     turn where a barrier may replace the reply, the stream is
                     HELD and the vetted reply emitted once, so no fabrication
                     flickers on screen. CONVERSATIONAL CONTINUITY (Notes-10
                     Phase 2): an OFFER LEDGER (self.offer) records the one
                     concrete offer a reply made and, when the next message is a
                     bare affirmative, injects a "do it now, don't re-ask"
                     directive (the anti-dodge barrier is the backstop); and
                     HISTORY COMPACTION replaces the old silent 40-message trim —
                     evicted turns are folded (one tool-less call) into a running
                     digest (self.history_summary) injected at the head of
                     context, so a long session never loses what scrolled off
                     (best-effort: a summarize failure falls back to the plain
                     trim, never blocking a reply). Each interaction-log record
                     carries additive observability (referents, taint,
                     date_grounding, calendar_corrective, citation/
                     citation_corrective, retrieved_obs — the observation ids
                     that grounded a reply — plus Notes-10 Phase 1:
                     date_floor_corrective, unsolicited_action, and
                     proactive_grounded on greeting/briefing records; Phase 2:
                     offer_accepted, offer_armed, offer_dodge_corrective,
                     history_compacted).
                     After each durably-writing turn the memory pass records ONE
                     typed observation, and session_greeting resumes from the
                     recent observation stream ("where we left off") — the
                     Phase-3 cross-session backbone.

core\model.py        OllamaClient — the ONLY file that knows how the model is
                     served (local HTTP). Swap serving stacks here.
core\reasoning.py    scaffold text (config-tunable working discipline).

core\invariants.py   THE CONSTITUTION — the four invariants as a code
                     constant, injected into the system prompt by the engine
                     itself every message. This is the keystone of the
                     SELF-MODIFICATION MODEL (three tiers):
                     - Tier A, her MIND (free): character brief AND operating
                       rules live in the brain (character\friday.md,
                       character\operating_rules.md — the latter migrated from
                       config\persona.md on first boot, minus Invariants).
                       Self-edits are normal brain writes: logged, fsync'd,
                       git-versioned, re-read every message. She announces
                       rule changes to Jack.
                     - Tier B, her MACHINERY (governed — upgrade plan Task 2,
                       core\config_governance.py): EVERY config key carries a
                       tier assigned in CODE (untiered keys refuse to boot):
                         self_serve — she flips it herself, no confirm,
                           runtime-only (file never written -> resets at
                           session end), audited;
                         propose — filed to config\proposals.jsonl, applied
                           only via `python friday.py config review` (backup
                           + audit on apply);
                         locked — visible (read_own_config shows everything,
                           tiers included) but never self-modifiable; the
                           attempt itself is audited. Paths, permissions,
                           account wiring, provenance, and budget CEILINGS
                           (e.g. deep_mode.max_calls_per_session — Jack sets
                           ceilings, she spends within them) live here.
                       Every change from ANY actor (incl. Jack's manual file
                       edits, diffed at load) lands in config\audit.log.
                     - Tier C, the CONSTITUTION (no tool, by design): the four
                       invariants + the permission gate + code + the TIER MAP
                       ITSELF. The gate can't be guarded by itself; code
                       changes are inbox\ proposals.
                     Why this is safe to open: invariants can't be dropped by
                     ANY file edit (GRW-007), tainted turns can't touch her
                     self-definition (GRW-009), and every self-change is
                     reversible (git / backups).

core\artifacts.py    artifact perception (Task 6): perceive() turns a file
                     into extracted text (pypdf for text-PDFs) or an EXPLICIT
                     honest UNREAD record; comprehension_block() rides in
                     add_files_to_project results so filing and perceiving
                     cannot be separated. The engine keeps a per-conversation
                     REFERENT STACK (every tool-touched artifact/entity, with
                     content excerpts) injected late in the system prompt with
                     resolution rules. Referents come from tool ARGS
                     (read_file/read_brain/…) and from tool RESULTS
                     (_track_result_referents): read_calendar pushes events, and
                     — Notes-10 Phase 2 §3 — list_dir pushes each FILE it lists
                     with its real absolute path, so "the pdf" resolves one turn
                     after a folder listing instead of the model guessing a path.
                     Plus a CODE barrier that catches the
                     model reviewing artifacts that were never shared
                     (prompt-immune fabrication; one corrective retry, then a
                     fail-safe honest reply).

core\tools\repo_tools.py  repo awareness (Task 5): repo_sync / repo_map /
                     search_repo over a READ-ONLY data\workspaces\ area.
                     All external_read (cloned code is outside the trust
                     boundary — taint applies). No write/commit/push tool
                     exists here, the gate denies workspace writes, and
                     repo.allow_patches (locked) is the future door to
                     .patch output. Review method: playbooks\code_review.md
                     via the router; targeted reads reuse read_file.

core\tools\git_write.py  GitHub write (coherence plan Phase 4 / D6): the
                     git_commit_push tool — the FIRST capability that writes
                     OUTSIDE brain\ + friday_documents\. Two independent LOCKED
                     locks: repo.allow_git_write (master switch — the tool
                     doesn't even register until Jack flips it, like
                     allow_patches) AND repo.writable_repos (allowlist; empty =>
                     nothing writable even with the switch on). A pure-function
                     DENY-LAYER (evaluate) blocks force-push / history-rewrite /
                     protected branches (repo.protected_branches) / secrets-in-
                     diff / off-allowlist repos BEFORE any confirm card, then
                     approve_outbound asks on EVERY push (invariant 3). It NEVER
                     force-pushes (structurally) and does NOT loosen
                     permissions._zone — the worktree is governed entirely by
                     the deny-layer + allowlist. action_confirmed; result to the
                     model is a status line only (no raw repo content).
                     Playbook: playbooks\git_commit.md.

core\tools\video_tools.py  /watch (coherence plan Phase 4 / D5) — LIVE
                     (activated Phase 6, 2026-07-12). Four external_read tools
                     (download_video / extract_transcript / extract_keyframes /
                     describe_frames; downloaded media is DATA -> taint). Real
                     local pipeline: yt-dlp download, captions-first transcript
                     with faster-whisper fallback, ffmpeg scene/even keyframes,
                     Qwen2.5-VL frame description via Ollama (video.vl_model /
                     video.whisper_model, LOCKED). Registers only behind
                     video.enabled (LOCKED). Each tool still degrades HONESTLY
                     ("not available") if its dep goes missing and never
                     fabricates; frame description is LOCAL-only (no cloud
                     vision — invariant 1). Deps are pinned in requirements.txt
                     under FRIDAY's interpreter (system py -3 / 3.13); ffmpeg is
                     a system binary on PATH. Playbook: playbooks\watch_video.md.

core\memory\         the brain (markdown vault, git-versioned)
  brain.py           note I/O + auto-commit + write guards:
                     read-before-overwrite, tracker-file protection, and the
                     CALENDAR-MIRROR guard (Notes-10 Phase 1): no writes under
                     calendar/ and no note whose point is an event date-time
                     (a "- **Date:** ... HH:MM" field) — the calendar API is the
                     one authority for event dates (hard-won lesson #3), so a
                     note copying one is refused before it can go stale.
                     MEMORY PROVENANCE (Task 1): in a TEST session
                     (--test-session / FRIDAY_TEST_SESSION=1 / session.type)
                     every write reroutes under test_archive\ and reads
                     OVERLAY it (session's own copies first, real vault
                     beneath — trackers stay coherent, real notes untouched).
                     Real sessions: zero ceremony, unchanged.
  retriever.py       abstract Retriever (the recall seam) —
                     retrieve(query, top_k, include_test=False); the archive
                     is excluded from recall unless the session is a test
                     session or Jack asks about testing (engine heuristic),
                     and archive snippets always arrive labeled as testing.
                     Selected by memory.retriever (locked): keyword | layered |
                     (reserved) vector.
  keyword_retriever.py  keyword + recency over NOTES, with a min_score floor
                     (Phase 1). Excludes character/ and observations/ (each has
                     its own injection/recall path).
  observations.py    the memory backbone (coherence plan Phase 3): typed,
                     timestamped, id-carrying observations — one markdown note
                     each under observations\, written through Brain (so
                     git-committed + test-archive-routed like any write). The
                     memory pass records ONE per turn that durably wrote,
                     keyed on the ground-truth write ledger (never the reply's
                     claim) — the deterministic floor, same instinct as the
                     commitment/recurrence backstops. The id lives in the path,
                     so a recalled observation cites itself (anti-confabulation).
  observation_retriever.py  the Phase-3 recall layers: ObservationRetriever
                     (title-weighted, self-citing snippets) and LayeredRetriever
                     (notes + observations merged, the `layered` default). A
                     cold brain has zero observations, so `layered` == keyword-
                     notes until the pass writes some — recall grows into
                     cross-session continuity through use.

core\permissions.py  PermissionGate — every filesystem action passes here.
                     Free: writes in brain\ + friday_documents\ (logged,
                     git-backed). Confirm: deletes, >large_file_mb, project-
                     folder writes, approve_outbound (ALL outbound), and
                     approve_tainted (any action tool in a turn that has read
                     external content — file/web/email/calendar).
                     Deny: everything else. Frontends inject the confirm UI.

core\commitments.py  CommitmentTracker  ┐ structured state in the brain,
core\timelines.py    TimelineTracker    ┤ parseable markdown, mutated ONLY
core\playbooks.py    Playbooks          ┘ via their classes/tools (write_brain
                     Playbook injection (Task 3): a small set rides in the
                     system prompt in FULL; once the set outgrows the 6000-
                     char budget, the block becomes an index and
                     Playbooks.match() injects the ONE fitting playbook per
                     message (Skills-style conservative matcher). Escalation
                     policy (high -> max effort) lives in playbooks/
                     max_effort.md and arrives via this router — NEVER in the
                     always-on scaffold (three measured cases of scaffold
                     additions zeroing ANSWER-format compliance).
                     is blocked on tracker files). Deterministic math lives
                     here (due dates, slip propagation), not in the model.
                     Commitment inference has a memory-pass BACKSTOP (the main
                     turn infers passing intent unreliably) — inferred items
                     land in Pending, awaiting confirm, so a stray catch is
                     harmless. Playbooks: `prompt_block()` injects each
                     playbook's FULL steps into the system prompt when the set
                     is small, so following one doesn't depend on the model
                     calling read_playbook (it announces then improvises);
                     large sets fall back to the title index + read cue.
                     Playbook capture is also self-directed: a memory-pass
                     rule writes one when recurring work shows in an exchange
                     (same backstop pattern as commitments), and the persona
                     licenses authoring at her own initiative (third
                     occurrence, per brain\playbooks\writing_a_playbook.md).

core\skills.py       Skills — domain-general THINKING DISCIPLINES in
                     brain\skills\ (method transfer, NOT capability cloning;
                     never claim reasoning horsepower the local model lacks).
                     Separate from playbooks on purpose: playbook = procedure
                     for a specific recurring task; skill = a way of working
                     that spans domains. Importing one = drop a .md in the
                     folder (frontier-authored files welcome; _template.md
                     shows the format; "_"-prefixed files ignored). Retrieval
                     differs from playbooks because the set GROWS: a title
                     index rides in the system prompt, and Skills.match()
                     (conservative keyword overlap vs name/when/Triggers,
                     min score 2 so chitchat/recall match nothing) injects
                     the single best skill's FULL text per message in
                     engine.respond(), like retrieved notes. read_skill /
                     list_skills for explicit loads. A skill's steps never
                     override the invariants or the gate.
                     Self-repair boundary (growth): her NOTES she fixes
                     herself; config\ lives OUTSIDE the brain root and
                     Brain._resolve refuses escapes, so configuration fixes
                     are proposal-only (written to inbox\) by construction.

core\accountability.py  panel data ("Needs You"), staleness scan (respects
                     project status), DND + ping pacing, briefing schedule.
                     State file: data\app_state.json.

core\senses\         networked DATA sources (never cognition)
  gmail_sense.py     read + draft; NO send method exists by design
  calendar_sense.py  read free; create gated by approve_outbound.
                     TIMEZONE CONTRACT: the API's RFC3339 (offset or 'Z') is
                     parsed tz-aware and converted to the MACHINE-LOCAL zone at
                     exactly one point (_parse_start, in events()); downstream
                     gets a pre-formatted local wall-clock string with no
                     offset in it. The model must NEVER see a raw offset — a
                     real 2 PM meeting was reported as 10 AM/3 PM on the wrong
                     day because the model was doing the offset math itself.
                     All-day events stay dates (never zone-shifted).
  web_lookup.py      one-shot fetch, on request only, never ambient
  importance.py      deterministic pre-screen of unread mail against Jack's
                     email_importance.md surface rules (deadlines, .edu/advisor
                     senders, money/interviews). text_summary() tags matching
                     mail as a salience hint — the model reliably buries a real
                     "enrollment hold, action by Friday" under newsletters
                     (0/5), so code does the pattern part; she still writes the
                     verdict. Conservative by construction (noise never flags).
  __init__.py        Senses hub: poll cache + connection status
                     (a sense is active iff its token exists in data\secrets\)

core\tools\          the registry pattern: every capability is a tool
  registry.py        register(name, description, schema, func, kind); errors
                     return as text so the model can react instead of crashing.
                     kind declares the tool's nature for the taint defense:
                     internal | external_read (taints the turn) | action
                     (confirms while tainted) | action_confirmed (already
                     confirms every call on its own — no double-confirm)
  filesystem.py / brain_tools.py / projects.py / commitment_tools.py /
  timeline_tools.py / playbook_tools.py / senses_tools.py / reasoning_tools.py /
  git_write.py (gated commit/push) / video_tools.py (/watch scaffold)
  research_tools.py  autonomous GPU research loop (autoresearch port), gated.
                     Three tools (autoresearch_launch/status/stop). Registers
                     only behind research.enabled (LOCKED) + a non-empty
                     research.allowed_repos (LOCKED) — the FIRST capability that
                     EXECUTES cloned, self-modified code. A pure DENY-LAYER
                     (evaluate_launch) blocks missing git/uv/GPU, off-allowlist
                     repos, a concurrent run, and reused tags BEFORE any confirm
                     card; approve_outbound asks ONCE for the whole run. Each run
                     is isolated (its own clone + uv venv, never FRIDAY's), edits
                     come from a TOOL-LESS model call (no registry surface for
                     the untrusted repo), and every timeout/ceiling is
                     code-enforced. A code busy-gate in engine.respond() keeps a
                     live run and chat from fighting over the 12GB GPU.
                     Playbook: playbooks\autoresearch.md.
  calc_tools.py      units-aware `calc` (Pint) she calls for EVERY numeric
                     result — carries units through the math so the x60
                     minutes/hours slip is impossible. Don't make the model do
                     what code can do.

core\project_meta.py field lines in notes (- **Status:** ...), slug()
core\project_resolver.py  ProjectResolver (Notes-10 Phase 3, §1): deterministic
                     free-text -> project matching (stdlib difflib + normalized
                     compact strings; no new dep). Reads projects\ notes (+
                     orphan folders) and scores each by containment / distinctive-
                     token cover / fuzzy window ratio. `resolve_one` decides:
                     act on a confident single match, ASK which on genuine
                     ambiguity (the licensed JARVIS confirm), stay silent when
                     nothing is strong. Backs `projects.py:_find_folder`, the
                     `resolve_project` tool, AND the engine's per-turn resolution
                     hint (bootstrap wires engine.project_resolver; respond()
                     appends hint_for(user_input) to the referent block so the
                     model never guesses a project path — transcript-B fix). The
                     hint is conservative (empty on anything but a strong match),
                     so bare questions and the golden suite are unchanged.
core\bootstrap.py    wires ALL of the above from config\friday_config.yaml;
                     both frontends call build_engine(confirm_callback)
core\logging_utils.py actions.log + interactions\*.jsonl (also the future
                     fine-tuning dataset)
core\version.py      __version__ + changelog
```

## Data at rest

```
brain\               her mind — Obsidian vault, its own git repo, auto-commit
  character\friday.md   voice/personality (edit in Obsidian; loads per message)
  preferences\ projects\ people\ episodic\ inbox\   knowledge notes
  commitments.md     tracker-owned (structured)
  timelines\*.md     tracker-owned (structured)
  observations\*.md  typed-observation stream (Phase 3): the cross-session
                     "what happened / where we left off" record. Code-written,
                     self-citing; a separate recall layer (NOT in the note map)
  playbooks\*.md     reusable procedures; DROP A FILE HERE TO SEED ONE
config\              friday_config.yaml (all knobs), persona.md (operating
                     rules), preferences.json (hard prefs)
data\                derived + private state (git-ignored): app_state.json,
                     secrets\ (OAuth tokens — never in brain or logs)
  research\<tag>\    one autonomous-research run: status.json (atomic; the ONLY
                     file status reads), run.log (latest attempt), and repo\ —
                     THIS run's private clone with its own .venv (torch/kernels)
                     and results.tsv ledger. Isolated from data\workspaces\.
logs\                actions.log, interactions\, app.log (windowless stderr)
friday_documents\    her outbox
```

## The contracts between layers

- **Face ↔ service:** a face calls `service.attach(**callbacks)` once
  (`on_token/on_tool/on_done/on_error/on_confirm/on_ping/on_proactive/`
  `on_activity/on_memory`), then `send_message`, `resolve_confirm`, and the
  read-only view APIs. Nothing else. A voice frontend = a new file in
  interface\ that does exactly this.
- **Engine ↔ model:** `OllamaClient.chat(messages, tools, on_token)` →
  `ModelReply`. Nothing above the engine imports requests or knows Ollama.
- **Everything ↔ disk:** through `Brain` (notes) or the gate (files). The
  model's write path (`write_brain`) is guarded: read-before-overwrite, and
  tracker-owned files are off-limits (their tools mutate them).
- **Confirmations:** the gate holds a `confirm(description) -> bool`
  callback. CLI answers y/N inline; the app shows a card and blocks the
  engine worker on an Event until Jack clicks.

## How to extend (recipes)

- **New tool:** one `register_x` function in `core\tools\`, call it from
  bootstrap. Schema descriptions steer the model — write them like docs.
  Anything the model shouldn't compute (dates, math) → compute in the tool.
- **New sense:** a class in `core\senses\` with `connected()` + read methods
  (+ gate-confirmed writes via `approve_outbound`), added to the Senses hub,
  tools in senses_tools.py. Degrade to "not connected", never crash.
- **New frontend:** new file in `interface\`, use the face↔service contract.
- **Seed a playbook:** drop a .md into `brain\playbooks\`. Done.
- **New gated OUTBOUND capability (Phase 4 pattern):** register an
  `action_confirmed` tool that calls `gate.approve_outbound` on every use; put
  any "never, confirm or not" rules in a pure-function deny-layer that runs
  BEFORE the confirm (see `git_write.evaluate`); gate the whole capability
  behind a `locked` config switch so it doesn't register until Jack flips it
  (see `git_commit_push` / `repo.allow_git_write` and `/watch` /
  `video.enabled` in `bootstrap.py`). Keep the model-visible result a status
  line, not raw external content (taint).
- **New capability that EXECUTES untrusted/self-modified code (research
  pattern):** distinct from the gated-outbound recipe — executing cloned code is
  a harder risk class than pushing code someone wrote. Isolate the execution in
  its OWN directory + dependency environment (a per-run clone with its own venv,
  never FRIDAY's — see `data\research\<tag>\`); make every timeout/ceiling
  CODE-enforced, never model-judged; make any in-the-loop model call TOOL-LESS
  (a bare `OllamaClient` with no `tools=`, so nothing in the untrusted content
  has a tool surface); keep the model-visible result to a status line; gate the
  whole thing behind LOCKED switch(es) that ship disabled; and put a busy-gate
  in `engine.respond()` (the seam BOTH faces share) if the run competes with
  chat for a shared resource like the GPU. See `research_tools.py` +
  `research.enabled`/`research.allowed_repos`.
- **Memory backbone (Phase 3, BUILT):** typed observations
  (core\memory\observations.py) + the `layered` retriever
  (observation_retriever.py), selected by `memory.retriever`. To add a semantic
  index, implement a `Retriever` behind the same seam and select `vector` — but
  it needs a heavy on-device embedding dep (torch via ChromaDB /
  sentence-transformers), which is JACK'S CALL per CLAUDE.md; bootstrap refuses
  `vector` until it's wired rather than pretend it exists (see
  FRIDAY_coherence_plan.md Phase 4).
- **Deep mode:** `ollama pull qwen2.5:32b`, set `deep_mode.enabled: true` —
  the deep_think tool registers itself.

## Hard-won lessons encoded in this design

1. Small local models fail calendar arithmetic, blind rewrites, numeric
   arithmetic, and "remembering" — so dates resolve in code, overwrites
   require a prior read, tracker files are model-proof, quantitative answers
   route through the units-aware `calc` tool (the x60 minutes/hours energy
   slip was a live failure), and a post-reply memory pass (told what was
   already saved) commits durable facts to the authoritative note.
2. Prompt rules are soft; code is hard. Every invariant that matters has a
   code-level enforcement, and prompts are the second layer, not the first.
3. One fact, one place: corrections UPDATE notes (update_note_field), never
   append contradictions.
4. Phrasing detection cannot carry invariant 2: a politely-worded instruction
   planted in a read file got a free brain write executed where blunt payloads
   were caught. Hence the taint defense — external content in a turn makes
   every subsequent action tool (memory pass included) confirm with Jack.
   New tools MUST declare an honest `kind` at registration or they sit
   outside this barrier.
5. Tool calls can arrive as TEXT. qwen intermittently writes `write_brain({…})`
   into its reply with an EMPTY tool_calls list — silently dropping the action
   and making the reply lie ("I've noted that" when nothing saved).
   engine._recover_tool_calls parses such narrated calls (registered tools
   only, when no real call was made) and runs them, in both the main loop and
   the memory pass. Three narration shapes are recovered: `name({json})`, the
   raw `{"name": …, "arguments": {…}}` envelope, and Python call syntax with
   positional literals (`calc('12 V / (4 ohm)', 'A')` — the shape that failed
   15 golden math cases in the friday-tuned-v1 A/B eval; positional args map
   to the tool schema's properties in declaration order, so property ORDER in
   a tool's JSON schema is part of its contract). Relatedly, the memory pass is told the GROUND TRUTH of what
   actually persisted (the real write ledger), never trusting the reply's
   claim — so a stated fact is still saved when the main turn only pretended to.

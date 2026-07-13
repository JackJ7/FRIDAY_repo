# FRIDAY Notes-10 Plan — temporal integrity, conversational continuity, intent resolution, memory method port

**Status: IN PROGRESS — Phase 1 COMPLETE (2026-07-13). Phase 2 (conversational continuity) COMPLETE (2026-07-13): all four §§ landed + verified (offer ledger, widened anti-dodge, list_dir referents, history compaction; GT golden 8/8, baseline held). Phase 3 (intent resolution, the JARVIS layer) COMPLETE (2026-07-13): all six §§ landed + verified (resolver, list/merge/near-dup-guard project tools, fuzzy recall floor, consolidate playbook; GT-C3/C5/C6 LOCKED + verified live, GT-A/GT-B baseline held). Phase 4 (memory method port) next. Phases 7 & 8 ADDED (2026-07-13) from the autoresearch smoke test — write-ups landed, AWAITING JACK REVIEW, nothing implemented yet; both are near-term (do before P3–P6): P7 = autoresearch stop-path integrity (Cluster 1), P8 = proactive-briefing grounding (Cluster 2, kept out of P2 per Jack). Live calendar-mirror migration still DEFERRED (Jack). 47 PRE-EXISTING model-suite failures (calc/injection/variance) remain flagged for Jack, NOT caused by this work.**
**Source: Jack's "Friday Notes 10" (live-usage transcripts, 2026-07-11/12) + code diagnosis of the current repo.**

> **Progress at a glance** (newest first — a fresh session reads this line, then §3):
> - **P3 COMPLETE 2026-07-13 — the JARVIS layer (clusters B+C).** All six §§:
>   §1 entity resolver (`core/project_resolver.py` — stdlib fuzzy match; engine
>   injects real note+folder so the 14B never guesses a path; ambiguity asks
>   which), §2 `list_projects`, §3 `merge_projects` (gated consolidation — one
>   batch confirm, folds notes, marks duplicates merged, never creates), §4
>   `create_project` near-dup guard (the fix for the fourth-project bug), §5
>   separator-insensitive fuzzy recall floor, §6 `consolidate_projects` playbook.
>   27 non-model unit tests (RESOLVE/LIST/MERGE/GUARD/RECALL), 211 non-model pass.
>   **GT-C3/C5/C6 promoted to LOCKED and verified live** (deterministic structural
>   checks; behavioural stay TARGET). GT-A/GT-B baseline HELD. Landed on `master`
>   in parallel with the P7/P8 worktree (`phase78`) — merges cleanly (disjoint
>   engine.py regions). **Phase 4 (memory method port) next.**
> - **P3 §1 done 2026-07-13** — Entity resolver (`core/project_resolver.py`):
>   stdlib fuzzy-matches Jack's free-text project references against real
>   projects; a confident single match injects the real note+folder into the
>   prompt (engine `hint_for`, `None`-guarded) so the 14B stops guessing paths
>   (transcript-B root), ambiguity asks which (JARVIS confirm), weak = silent.
>   New `resolve_project` tool + `entity_resolved` log field. RESOLVE-001..008
>   pass; 192 non-model pass.
> - **P2 COMPLETE 2026-07-13 (§4 last)** — History compaction replaces the silent
>   40-msg trim: evicted turns are summarised (one tool-less call) into a running
>   digest injected at the head of context, so nothing scrolled-off is lost.
>   Cheap cadence, fail-safe fallback. COMPACT-001..004 + live smoke (the digest
>   kept a planted early fact + she recalled it post-eviction). **All four Phase 2
>   §§ done; GT golden 8/8, baseline HELD.** Phase 3 (intent resolution) next.
> - **P2 §3 done 2026-07-13** — `list_dir` results now push their FILES onto the
>   referent stack (joined absolute paths, folders/tail excluded, capped) so "the
>   pdf" resolves one turn after a listing (transcript-B gap). `_track_result_
>   referents` gained an `args` param. REF-001..005 pass; 180 non-model pass. See
>   Phase 2 "§3 findings".
> - **P2 §2 done 2026-07-13** — Anti-dodge barrier widened to bare affirmatives
>   (gated on the §1 ledger) + `_REPROVIDE_DODGE` for the "provide me the file"
>   shape. GT-C4 gains a LOCKED `offer-ledger-accepts` structural check; live run
>   held it AND both no-dodge TARGET checks passed (she proceeded, no re-ask).
>   OFFER-006 added; 175 non-model pass. See Phase 2 "§2 findings".
> - **P2 §1 done 2026-07-13** — Offer ledger in `engine.py`: a concrete offer is
>   armed at turn end; a bare affirmative ("Yes please") next turn injects an
>   acceptance directive that forbids the re-ask (transcript-B failure). One-turn
>   expiry; `offer_accepted`/`offer_armed` log fields. OFFER-001..005 pass (no
>   model); 174 non-model pass, no regressions. GT-C4 behavioral checks stay
>   TARGET; §2 adds the structural LOCK. See Phase 2 "§1 findings".
> - **P1 COMPLETE 2026-07-13** — all four §§ landed. Full model suite 205/252:
>   **all 16 P1 targets pass, GT-A/GT-B LOCKED baseline held.** The 47 failures
>   are PRE-EXISTING model-suite cases (22 calc/ANSWER-format, 10 injection, 15
>   N-run variance) that the routine `--quick` (non-model) baseline never runs —
>   A/B-proven independent of this work. Flagged for Jack (see "Phase 1
>   regression notes" in §3). Phase 2 next.
> - **P1 §3 done 2026-07-13 (code half)** — Calendar-mirror write-guard in
>   `Brain.write_note` (refuses `calendar/` writes + event-date-mirror fields) +
>   soft persona rule; CALGUARD-001..004 pass. **Live migration DEFERRED** — the
>   one existing mirror (`brain/calendar/epp_mathworks_team_meeting.md`) is left
>   untouched pending Jack's go (recommendation in "§3 findings" / §3 below).
> - **P1 §2 done 2026-07-13** — Proactive path grounded (engine.py): greeting +
>   briefing run `read_calendar` themselves, inject it as DATA, and strip any
>   phantom scheduled item when the live calendar is empty. **GT-C2 → LOCKED×2**
>   (`proactive-grounded` + `no-phantom-scheduled-item`). Live: grounding alone
>   killed the stale-event repro. Phase 1 checklist + "§2 findings" below.
> - **P1 §1 done 2026-07-13** — Date-answer floor landed (engine.py):
>   `_wrong_today_claim` + `_force_today_date` + a regenerate-then-substitute
>   block in `respond()`, hold-stream on bare date questions, and a
>   `date_floor_corrective` log field. **GT-C1 promoted to LOCKED** (passes live,
>   17.9s). Pure-logic proof in `tests/pillar1/test_date_floor.py` (DATE-001..003,
>   3 pass, no model). Per-section checklist under **Phase 1** below.
> - **P0 done 2026-07-13** — GT-C golden set (`tests/pillar1/test_notes10.py`,
>   GT-C1..C6, all TARGET) landed + baseline captured against the live 14B.
>   GT-C2 (stale calendar-mirror) is the cleanest reproduction; GT-C3/C5 confirm
>   the missing deterministic surfaces; GT-C1/C4/C6 pass at baseline (their
>   named failures are 14B-variance, not always-on). See §3 for the table.
>
> **Note (Jack's 2026-07-13 ruling):** Phase 1 lands CODE + GUARD now; the
> live-brain calendar-mirror-note migration (§3 item 3) is DEFERRED until Jack
> confirms — the write-guard that PREVENTS new mirrors still lands now.

This is the living plan doc for this program (Jack's standing rule: record each
phase's results and next-phase recommendations INTO this file in place — never
spawn companion docs). Execute phases in order; each phase ends with the full
suite green, the GT golden baseline held, and this doc updated.

---

## 0. Read this first (execution protocol)

- Read `CLAUDE.md` and `ARCHITECTURE.md` before touching anything. The four
  invariants (`FRIDAY_spec_experience.md` §1) are non-negotiable: local
  cognition only, read-content-is-data, explicit confirm for outbound,
  precise knowledge-gap honesty.
- The brain (`brain\`) is a git repo — every write auto-commits; clean up
  test artifacts. LIVE-instance tests run with `--test-session` only.
- **Never use Jack's real project names (Doc Ock, CLARK, PERRY, EPP,
  Crush Depth, ...) in test prompts.** The Notes-10 transcripts quote real
  names as *evidence*; your tests must reproduce the failure *shapes* with
  throwaway names.
- FRIDAY runs on `py -3` (Python 3.13), not bare `python`. Full suite:
  `py -3 run_suite.py` (or `run_suite.ps1`); 149 tests pass as of 2026-07-13.
- Capability transfers into this project as METHOD (prompts, scaffolds,
  playbooks, code patterns) — never as fictional artifacts, never as claims
  of reasoning horsepower the local 14B model doesn't have.
- Prompts are soft; code is hard. Every fix below that must *hold* gets a
  code-level enforcement first (the coherence plan's barrier pattern in
  `core\engine.py` is the template).

---

## 1. What Jack reported (Notes 10) and what the code says actually broke

### Symptom cluster A — calendar/temporal trouble (transcript 1)

Observed, in one session:
1. Greeting: "your EPP MathWorks team meeting flagged for **tomorrow** at
   10 AM" — the meeting was ~a week in the past.
2. "What's the date today?" → "**Today is March 15, 2023**" — flatly wrong,
   despite the machine clock being injected into the system prompt every
   message (`engine.py` ~line 230).
3. The daily briefing listed that same stale meeting under "Today's
   Calendar", plus stale mail/timeline items.
4. After Jack's correction ("today is actually 07/11/26"), FRIDAY replied
   with an unrelated dump of "Jack's upcoming office hours" **in the third
   person** ("add any of these to **his** calendar") and then proposed an
   unrequested `update_note_field` on `calendar/epp_mathworks_team_meeting.md`
   (the taint gate correctly forced a confirm — that layer worked; the
   *proposal* itself was the failure).

Root causes found in code:
- **The proactive path has no grounding at all.** `Engine._proactive()`
  (engine.py ~1561) runs the greeting and briefing **tool-less** and
  **barrier-free**: no live `read_calendar`, no calendar-first barrier, no
  citation barrier, no date check. The briefing prompt says "using the
  accountability state in your context" — so whatever stale or note-derived
  text is in that summary gets presented as today's truth.
- **A brain note mirrors a calendar event.** The existence of
  `calendar/epp_mathworks_team_meeting.md` with a `Date:` field violates
  "one fact, one place" (hard-won lesson #3): the calendar API is the only
  authority for event dates, but a note copy with a stale date fed the
  greeting (notes are retrieved/recently-edited-injected) and the model
  presented it. Check the live brain for this note and any siblings under
  `calendar/`.
- **A bare date question has no floor.** `_date_grounding` (engine.py ~1197)
  only *classifies* how a stated date was grounded for the interaction log —
  nothing corrects a wrong answer. `_needs_calendar_grounding` deliberately
  never fires on a bare "what's the date today?" (correct — that's the
  clock's job, not the calendar's), so nothing caught "March 15, 2023".

### Symptom cluster B — in-session context loss (transcript 2, the PDF review)

Observed:
1. "look at the pdf in the doc ock project" → FRIDAY tried
   `C:\Users\jacko\projects\doc_ock` — a **guessed path** (real folder is
   recorded in the project note's `- **Folder:**` line; the model never
   looked it up).
2. Second ask → "the project folder is a stub / empty" (wrong again), then
   third ask (Jack naming the exact file) → she finally listed the folder and
   **offered** to review `Ock Sketches v1.pdf`.
3. Jack: "Yes please" → FRIDAY: "Could you please provide me with the file
   or its path" — the offer she had just made, forgotten one turn later.
4. "Do you know what file I am wanting you to read?" → another
   clarification dodge.

Root causes:
- **No deterministic name→folder resolution.** `projects.py:_find_folder`
  does the right lookup (note's Folder line, then projects root) but it's
  only reachable *inside* `add_files_to_project`. There is no tool the model
  can call (and no code path the engine runs) to resolve "the doc ock
  project" to its real folder — so the 14B guesses paths.
- **The anti-dodge barrier didn't fire on "Yes please."**
  The barrier (engine.py ~508) requires `_FOLLOWUP_DEICTIC` to match the
  user message AND a non-empty referent stack. A bare affirmative ("Yes
  please", "go ahead") likely isn't in the deictic pattern, and whichever
  tool listed the folder may not push its files onto the referent stack
  (only `perceive()`-touched artifacts reliably do). Verify both; both are
  gaps.
- **Nothing tracks what FRIDAY just offered.** When her reply ends with
  "Would you like me to review X?", that offer lives only in model attention.
  One turn later the 14B has lost it. There is no code-side record of a
  pending offer for a "yes" to resolve against.

### Symptom cluster C — project hygiene failure (transcript 3, the consolidation)

Observed:
1. "There are still 3 projects related to claude code upgrades, please make
   it only one" → FRIDAY **created a fourth project** (`claudecodeupgrade`)
   instead of merging the three.
2. "Now there are 4 ... the problem is getting worse" → a generic
   clarifying-questions reply.
3. "In your project files, there are 4 projects related to claude code" →
   "no existing brain notes related to the query" — recall couldn't even
   *find* the four notes that exist.

Root causes:
- **There is no consolidation surface.** The registry has `create_project`
  and `add_files_to_project` — nothing to *list* projects, nothing to
  *merge* them. Asked to reduce N projects to one, the model reached for the
  only project tool it has: create. This is the "new capability = new tool"
  rule in reverse — the missing tool guaranteed the wrong action.
- **`create_project` has no near-duplicate guard.** It happily scaffolds
  `claudecodeupgrade` next to three siblings whose slugs share most of their
  characters.
- **Keyword recall misses obvious matches.** "claude code" vs slugs like
  `claudecodeupgrade` (no separator) defeats keyword matching; the
  min_score floor then reports nothing. Fuzzy/normalized matching is needed
  at the *tool* layer, not by tuning the model.

### Symptom cluster D — Jack's asks (capability/method imports)

1. **"Import capabilities from https://github.com/affaan-m/ecc"** — ECC is a
   Claude Code plugin system: ~278 skills, 67 agents, 34 rules, hooks.
   Its value to FRIDAY is ~70% *methodology* (workflow skills, review
   checklists, a continuous-learning loop that turns session patterns into
   reusable skills). FRIDAY already has the exact receptacles: `brain\skills\`
   (thinking disciplines, Skills-style matcher) and `brain\playbooks\`
   (procedures). Import = curate + translate .md files, not port code.
2. **"Maybe claude-mem as well" / "How does Claude Code keep context during
   sessions? Apply this same logic to FRIDAY."** — claude-mem's mechanism:
   hooks capture typed observations into SQLite+FTS5; at session start a
   *compact index* (title + ID + timestamp, ~50–100 tokens each) is
   injected; full details are fetched **by ID on demand** (progressive
   disclosure, ~10x token savings). Claude Code itself keeps context by
   (a) the full transcript in the window, (b) **compaction summaries** when
   the window overflows — a summary carries forward, nothing is silently
   dropped, (c) always-loaded memory files (CLAUDE.md / MEMORY.md).
   FRIDAY already has typed observations (Phase 3) — what's missing is the
   compact always-on index, fetch-by-ID, FTS search, and history compaction
   (her `max_history = 40` currently **silently drops** the oldest turns).
3. **"I want to talk like myself and have her understand me (JARVIS)"** —
   with an explicit license for a "Jack said this, this folder/file is
   similar, let me confirm" flow. This is an intent-resolution layer:
   deterministic fuzzy matching of Jack's phrases against known entities
   (projects, notes, referents, calendar events) done in CODE, with the
   result injected as context — confirm only on genuine ambiguity.

### Honest ceiling (say this to Jack, don't bury it)

Several raw failures — hallucinating "March 15, 2023" against an injected
clock, the office-hours non-sequitur, third-person drift — are 14B-model
limits. The plan below wraps them in deterministic code so the *system*
stops failing even when the model does, and imports method to raise the
model's hit rate. It will make FRIDAY dramatically more reliable; it will
not make a 14B reason like a frontier model, and no task below may pretend
otherwise (invariant 4, CLAUDE.md capability-cloning rule).

---

## 2. Phases

Order: P0 → P1 → P2 → P3 → P4 → P5. P1–P3 are the user-visible pain; P4–P5
are the imports. Each phase = implement → test (throwaway names, sandbox
brains) → run full suite + GT golden baseline → record results in §3.

### Phase 0 — Verify & lock (reproduce before fixing)

The multi-turn golden harness from the coherence plan (GT-A/GT-B pattern,
`SandboxFriday`) is the vehicle. Add a **GT-C "Notes-10" golden set** that
reproduces each failure shape with throwaway names:

- GT-C1: bare "what's the date today?" — must state the machine-clock date.
- GT-C2: greeting/briefing with a planted stale `calendar/` mirror note —
  must not present the stale event as current.
- GT-C3: resolve "the <throwaway> project" to its real folder (note has a
  `- **Folder:**` line pointing somewhere non-default).
- GT-C4: offer → "Yes please" → the offered action proceeds (no dodge).
- GT-C5: "there are 3 <throwaway> projects, make it only one" — must NOT
  call `create_project`; must surface the three and propose a merge.
- GT-C6: "find my notes about <two-word name written as one slug>" — recall
  finds them.

Mark each TARGET now; individual phases promote their own to LOCKED once
the code barrier lands. Record the baseline pass/fail table in §3 before
writing any fix — the failures are the proof the fixes are real.

**DONE (2026-07-13).** GT-C1..C6 live in `tests/pillar1/test_notes10.py`,
built on the same LOCKED/TARGET machinery as GT-A/GT-B
(`helpers/transcript.py`), all checks TARGET, throwaway names only. Baseline
captured against the live `qwen2.5:14b` (`results/gt_c_phase0_baseline/`).
Full table + per-case findings in §3. Headline: **GT-C2 reproduces cleanly
and reliably** (the barrier-free proactive path presents a week-old
calendar-mirror note as "coming up today" / under "Today's Calendar") — that
is Phase 1's prime target. GT-C3 and GT-C5 confirm the missing deterministic
surfaces (name→folder resolver; list/merge projects). GT-C1/C4/C6 already
pass at baseline: their named root causes are 14B-variance (the "Yes please"
dodge, the merged-slug recall miss) or already floored (date-today by the
injected clock) — so those phases' value is measured by *removing the
variance* deterministically, not by a red baseline. GT-C6 also surfaced the
intermittent **Thai/non-English drift** under recall load (same shape as
GT-A T5) — real, and orthogonal to recall.

### Phase 1 — Temporal integrity (cluster A)

**Per-section progress (a fresh session resumes from here):**
- [x] **§1 Date-answer floor — DONE (2026-07-13).** See "§1 findings" below.
- [x] **§2 Ground the proactive path — DONE (2026-07-13).** See "§2 findings" below.
- [x] **§3 Calendar-mirror write-guard — CODE DONE (2026-07-13); LIVE MIGRATION DEFERRED (awaiting Jack).** See "§3 findings" below.
- [x] **§4 Unrequested-action dampener — DONE (2026-07-13).** See "§4 findings" below.

> **§4 findings (Unrequested-action dampener).** Measurable half: added
> `_REQUEST_SHAPE` + `_looks_like_request()` (conservative: imperative verb /
> polite ask / affirmative) and an `unsolicited_action` field to the interaction
> log — True when an ACTION-kind tool fired on a message with no request shape
> (the office-hours "proposed an update nobody asked for" signature). The taint
> gate stays the HARD layer (it forced the confirm; unchanged). Soft half: a new
> "Propose, don't do, when Jack didn't ask" bullet in `config/persona.md`'s Tools
> section (same fresh-install-only caveat as §3's persona edit; the measurable
> flag is what lets the prompt be tuned against real rates later). **Tests:**
> `test_unsolicited_action.py` UNSOL-001..003 pass (no model) — requests vs
> statements/corrections classified correctly, and the office-hours shape flags.

> **§3 findings (Kill calendar-mirror notes — code/guard half).** Landed a
> write-guard in `Brain.write_note` (`core/memory/brain.py`), same class as
> tracker-file protection, two shapes refused with a `PermissionDenied` that
> points the write at the right home: **(a)** any write under `calendar/` (there
> is no calendar/ note folder — the API owns event dates); **(b)** any
> create/overwrite whose body carries an event-date-mirror field
> (`_EVENT_DATE_FIELD`: a `- **Date:**` / `- **Date & Time:**` / `Date/Time`
> field whose value carries a clock time — the HH:MM / am-pm is what separates
> an event mirror from a legitimate milestone/due date). Soft layer: one line
> added to the Calendar operating rule in `config/persona.md` ("never mirror a
> calendar event into a note"). **Tests:** `test_calendar_mirror_guard.py`
> CALGUARD-001..004 pass (no model), including through the `write_brain` TOOL
> path (registry returns the refusal as text, so the model reacts honestly).
> **Note (soft-layer scope):** `config/persona.md` is the fresh-install default;
> the LIVE instance's operating rules already migrated to
> `brain/character/operating_rules.md`, so the persona edit only reaches new
> installs — the CODE guard is the real protection on the live instance
> regardless.
>
> **⚠ DEFERRED — live-brain migration awaits Jack's confirm.** The scan found
> exactly ONE existing mirror, the transcript culprit itself:
> **`brain/calendar/epp_mathworks_team_meeting.md`** — content is a pure mirror
> (`- **Title:** EPP MATHWORKS Team Meeting` / `- **Date & Time:** July 7,
> 2026, 2:00 PM - 3:00 PM`), nothing else worth keeping. Left UNTOUCHED per
> Jack's instruction (code + guard now, migration on confirm). **Recommended
> migration when Jack says go:** delete the note outright (it's a stale copy of
> a calendar event with no unique content; the calendar is the authority) — or,
> if any context is worth keeping, move a by-NAME reference (no date) into the
> relevant project/episodic note first. Until then the note is inert: the
> proactive path (§2) no longer treats it as the calendar, so it can't be
> presented as "coming up today" again.

> **§2 findings (Ground the proactive path).** `_proactive()` gained a
> `ground_calendar` flag (passed True by BOTH `session_greeting` and
> `briefing`). When set, the ENGINE runs `read_calendar` itself and injects the
> live result as a DATA-wrapped tool message (invariant 2) plus a grounding rule
> (`_PROACTIVE_CALENDAR_RULE`): the live calendar is the only authority; a
> note's `Date:` field is not. Post-check `_phantom_event_sentences()`
> (clause-level, past-aware) flags any clause framing a scheduled item as
> current while the live calendar is EMPTY; on a hit it regenerates once, then
> `_strip_sentences()` deterministically removes whatever survives (safe voice
> fallback if that empties the message). The stream is HELD on grounded turns
> and the vetted reply emitted once (no phantom flicker). Read is via
> `registry.call` (NOT `_run_tool`) so this display-only scaffolding does not
> taint the next turn or push referents. Added `proactive_grounded` to the log.
> **GT-C2:** two NEW **LOCKED** checks — `proactive-grounded` (structural: the
> engine ran the live read) and `no-phantom-scheduled-item` (the strip's
> deterministic guarantee) — plus the zephyr-name `no-stale-event-as-current`
> kept **TARGET** (it keys on the event NAME, which the strip can't guarantee;
> now made sentence-level = the honest failure definition, and passing reliably).
> Live evidence: grounding alone did the work — greeting said *"The calendar
> isn't connected right now, so there are no scheduled events today"* and pivoted
> to the Alpha Rig; the stale event was never surfaced. GT-C2 passes (14.6s);
> greeting-dependent STA-003 + OBS-004 still green (no regression).
> **Honest limitation:** the LOCKED guarantee is the empty-calendar case (which
> is GT-C2's repro and the common real case). When the calendar has REAL events,
> a note-derived stale event is not code-caught — grounding + the prompt rule
> carry it, measured by the TARGET check. Noted for §3/Phase-2 follow-up.

> **§1 findings (Date-answer floor).** Landed in `core/engine.py`:
> `_ISO_FULL`/`_NAMED_FULL`/`_TODAY_CUE`/`_MONTHS` + `_wrong_today_claim()`
> (detects a today-CUED full date — one carrying an explicit year — that
> contradicts the machine clock; event dates without a today-cue never trip it)
> and `_force_today_date()` (substitutes the real date, shape-preserving,
> idempotent). `respond()` regenerates ONCE with a correction then applies the
> deterministic substitution, so the guarantee never rides on the 14B. Added
> `_DATE_QUESTION` + `date_ask` to `hold_stream` so a wrong date never flickers
> on screen before correction, and a `date_floor_corrective` bool to the
> interaction log (additive; schema stable). **Tests:** GT-C1 → **LOCKED**,
> passes live (17.9s); `test_date_floor.py` DATE-001/002/003 pass (0.02s, no
> model) — they ARE the lock's proof (correct dates & event dates untouched;
> off-by-one-day still corrected). Nothing else in the suite touched.

1. **Date-answer floor (code, lockable).** After generation, scan the reply
   for a stated "today is <date>"-shaped claim (reuse `_date_grounding`'s
   parsing); if it contradicts the machine clock, regenerate ONCE with a
   correction (barrier pattern), and if the retry still contradicts,
   **code-substitute** the correct date sentence (this one is pure
   determinism — the clock is authoritative by construction, engine.py
   ~1126 already says so). Fail-safe wording stays in FRIDAY's voice.
2. **Ground the proactive path.** `briefing()` (and `session_greeting` where
   it mentions the calendar): the ENGINE runs `read_calendar` itself
   (exactly the calendar-first pattern, engine.py ~552) and injects the live
   result as a DATA-wrapped tool message into the proactive exchange. Add a
   post-check: any event named in the briefing's "Today's Calendar" section
   must appear in that live result, else regenerate once. The accountability
   summary may *cue* what to present; it is no longer the calendar
   authority anywhere.
3. **Kill calendar mirror notes (one fact, one place).** Inspect the live
   brain for `calendar/*.md` and any note carrying an authoritative event
   `Date:` field. Migrate content worth keeping into the right project/
   episodic note *minus* the date claim; the note may reference an event by
   name but must say the calendar is the authority. Add a write-guard rule
   in `Brain` (or the memory-pass prompt + a deterministic check) so the
   memory pass never creates a note whose *point* is an event date. This is
   the same class of guard as tracker-file protection.
4. **Unrequested-action dampener (soft + measured).** The office-hours turn
   proposed `update_note_field` nobody asked for. The taint gate already
   forces the confirm (keep it). Add: when an action tool fires in a turn
   whose user message contains no imperative/request shape, log
   `unsolicited_action` in the interaction record so the rate is measurable;
   tighten the operating-rules prompt line ("propose, don't do, when Jack
   didn't ask"). Prompt-only beyond the existing gate is acceptable here —
   the gate is the hard layer and it held.

Promote GT-C1/C2 to LOCKED. Suite + GT baseline green.

### Phase 2 — Conversational continuity (cluster B)

**Per-section progress (a fresh session resumes from here):**
- [x] **§1 Offer ledger — DONE (2026-07-13).** See "§1 findings" below.
- [x] **§2 Widen anti-dodge to affirmatives — DONE (2026-07-13).** See "§2 findings" below.
- [x] **§3 Referents from every file-surfacing tool — DONE (2026-07-13).** See "§3 findings" below.
- [x] **§4 History compaction — DONE (2026-07-13).** See "§4 findings" below.

> **§4 findings (History compaction).** The silent `self.history =
> self.history[-40:]` trim dropped the oldest turns outright — a fact established
> early in a long session vanished the moment it scrolled off. Replaced with the
> Claude Code compaction mechanism at FRIDAY's scale (`_compact_history`): when
> the trim triggers, the evicted turns are rendered as plain dialogue and folded
> — via ONE tool-less summarize call — into a running ≤150-word digest
> (`self.history_summary`) that rides at the HEAD of context next turn as
> established-context (never new instructions). `_compact_keep` (24) sits below
> `max_history` (40) so the trim re-triggers only after the margin refills =
> compaction runs at most once per several turns, not every turn. Best-effort by
> contract: the call is wrapped in try/except and the plain trim runs regardless,
> so a summarize failure never blocks or loses a reply (the reply is already
> streamed by then — the only cost is a small post-reply pause every few turns).
> New `history_compacted` log field. **Tests:** `test_history_compaction.py`
> COMPACT-001..004 pass (no model) — digest built + counted, prior summary folded
> in, empty/blank no-ops, and the trim swallows a summarize failure while still
> bounding history. **Live smoke** (`test_history_compaction_live.py`
> COMPACT-LIVE-001, thresholds lowered to fire fast, 83s): compaction fired, the
> digest captured the planted early fact ("load cell rated at 37 kg") AFTER that
> turn was evicted, and she recalled it correctly on a later turn — the session
> kept what scrolled off. 184 non-model pass, no regressions. (Recording the
> compaction summary as a session-end OBSERVATION for the NEXT session's index is
> Phase 4's job, per the plan — §4 is the in-session half.)

> **§3 findings (Referents from file-surfacing tools).** The gap the transcript
> named: `list_dir` surfaced a folder's files but pushed NOTHING onto the
> working-memory referent stack (only `perceive()`d/args artifacts and calendar
> events were tracked), so "the pdf" one turn after a listing had nothing to
> resolve against and the 14B guessed a path. Fixed in `_track_result_referents`
> (now `(tool, args, result)` — args are needed because a list_dir line carries
> only the bare file NAME): a list_dir result pushes each FILE as a `file`
> referent with the parent path joined back on = a real, readable absolute path;
> subfolders, `(empty folder)`, and the `... (+N more entries)` tail are excluded,
> and the push is capped at 8 (like the calendar) so a big folder can't evict the
> stack. No content excerpt is attached (the file wasn't read — that stays
> read_file's job, and its referent carries the excerpt), so this enables
> resolution without inviting a review-from-filename. **Tests:**
> `test_result_referents.py` REF-001..005 pass (no model) — file parsing + joined
> paths, folders/tail excluded, the cap, and a regression guard that the shared
> calendar path still works after the signature change. 180 non-model pass, no
> regressions. **Audit of the other surfaces the plan names:** `read_file` on a
> directory returns "use list_dir" (no files to push — she calls list_dir next,
> now covered); `repo_map`/`search_repo` name WORKSPACE-relative paths and are
> `external_read` (taint + different resolution semantics — deliberately left to
> the repo-review flow, not folded into the deictic stack); `search_brain`
> results are notes that already reach the stack via the recall-injection path
> and `read_brain` tracking. So `list_dir` was the concrete, transcript-motivated
> gap and it is closed.

> **§2 findings (Widen anti-dodge to affirmatives).** The Phase-1 anti-dodge
> barrier only fired on a `_FOLLOWUP_DEICTIC` message with a non-empty referent
> stack — a bare "Yes please" matched neither, so the transcript-B re-ask slipped
> through. §2 widens the barrier: it now ALSO fires when `accepted_offer` is set
> (a bare affirmative accepted a standing offer, gated on the §1 ledger being
> non-empty exactly as the plan specifies) AND the reply is a dodge. Added
> `_REPROVIDE_DODGE` — the transcript-B "provide me the file / which file are you
> referring to" shape the generic `_DODGE_REPLY` missed (kept in sync with the
> test's REPROVIDE). On an offer-dodge the correction names the accepted offer and
> orders her to carry it out and do any needed read HERSELF, never re-hand.
> Best-effort acceptance (a retry can re-hedge), same posture as the sibling
> barriers → behavioral checks stay TARGET. The **deterministic LOCK** is on the
> §1 ledger, not the retry: GT-C4 gains a LOCKED `offer-ledger-accepts` check —
> "if an offer was live at turn-start, a bare affirmative MUST have accepted it"
> (vacuously true when the 14B's turn 1 made no offer, so only a code regression
> fails it). New log field `offer_dodge_corrective`. **One detection fix from the
> live run:** the offer is armed from the WHOLE turn's assistant text, not just
> `reply.content` — across tool rounds the offer often lands in an earlier round
> ("let's list the folder" → list_dir → "…") while `reply.content` holds only the
> last round. Also broadened `_OFFER_SHAPE` with a curated-verb PROPOSAL branch
> ("Let's start by listing…", "I'll review the pdf") — a bare "yes" to an
> actionable proposal means "do it" as much as a yes to a question, and it is the
> shape GT-C4's turn 1 actually produces. **Tests:** `test_offer_ledger.py`
> OFFER-001..006 pass (no model); GT-C4 live: LOCKED `offer-ledger-accepts` held
> (`pending_offer=True accepted=True`), and both behavioral TARGET checks (no-dodge,
> no-reprovide) PASSED — turn 2 proceeded to act on the offer instead of re-asking
> (28.7s). 175 non-model pass, no regressions. (The residual path-guessing she
> showed is GT-C3's resolver territory, Phase 3, not a §2 miss.)

> **§1 findings (Offer ledger).** Landed in `core/engine.py`. A one-turn-life
> ledger (`self.offer = {text, referents}`) is armed at the END of `respond()`
> whenever the reply makes a concrete offer, and consumed at the START of the
> next turn: if that next message is a BARE affirmative, the engine injects an
> `_OFFER_ACCEPTED_DIRECTIVE` at the end of the system prompt (the max-obedience
> slot the referent block uses) that names the offer, says the "yes" means "do
> it now", and forbids re-asking / re-provision. Detection is two conservative
> regexes + helpers: `_OFFER_SHAPE`/`_offer_in_reply` (a question-shaped "would
> you like me to…?"/"shall I…?" OR an "I can … just say the word" tail; stores
> the offer *sentence*, not the whole reply) and `_AFFIRMATIVE_WORDS`/
> `_is_bare_affirmative` (message is affirmative-words-and-punctuation ONLY —
> "Yes please", "Sure, do it", "Go ahead" — so a qualified "yes, but check the
> date first" keeps its residue and is NOT treated as a blanket accept; a 40-char
> cap keeps long instructions out). Consume-at-start gives the exact expiry the
> plan asked for: accepted by an affirmative, expired by a new-topic message,
> never a stale accept. The accepted-offer turn is added to `hold_stream` (a §2
> retry may replace the reply, so no re-ask flickers), and two additive log
> fields land — `offer_accepted` (a bare "yes" resolved a standing offer) and
> `offer_armed` (a fresh offer stored for next turn) — so the "Yes please ->
> re-ask" rate is measurable. **Tests:** `test_offer_ledger.py` OFFER-001..005
> pass (no model, 0.02s) — they are the deterministic lock's proof (offer
> detection, sentence extraction, bare-vs-qualified affirmatives, the
> consume/expire state machine, directive assembly). Full non-model suite: 174
> pass, no regressions. GT-C4's behavioral no-dodge checks stay TARGET (they ride
> on the §2 best-effort retry + a model-made turn-1 offer) — §2 adds the
> structural LOCKED check.

1. **Offer ledger (code).** When FRIDAY's reply makes a concrete offer
   ("Would you like me to <verb> <referent>?" — detect conservatively), the
   engine records `{offer_text, resolved_tool_hint, referents}` on the
   session. On the next user turn, if the message is a bare affirmative
   ("yes", "yes please", "go ahead", "sure", "do it"), inject a system line:
   "Jack accepted your standing offer: <offer_text>. Proceed with it now —
   do not re-ask." Expire the ledger entry after one turn or when a new
   topic message arrives. This is deterministic state carrying what the 14B
   drops.
2. **Widen anti-dodge to affirmatives.** Add bare-affirmative shapes to
   `_FOLLOWUP_DEICTIC` (or a sibling pattern gated on a non-empty offer
   ledger) so "Yes please" → clarification-dodge regenerates with the
   offer-ledger context. GT-C4 locks on this.
3. **Referents from every file-surfacing tool.** Audit `_run_tool`'s
   referent push: any tool result that *names files* (project folder
   listings, `read_file` on a directory, repo_map, search results) must push
   those files onto the referent stack with their paths, not only
   `perceive()`d artifacts. "The pdf" one turn after a listing must resolve.
4. **History compaction (the Claude Code mechanism, small-scale).** Replace
   the silent `self.history = self.history[-40:]` trim (engine.py ~713) with
   compaction: when the trim triggers, run a tool-less summarize call over
   the evicted turns ("facts established, decisions made, open threads —
   ≤150 words") and keep the summary as a single system-role context message
   at the head of history. The session should never lose what was
   established just because it scrolled. Keep it cheap: compact at most once
   per N turns; on failure, fall back to the old trim (never block a reply
   on compaction).

Promote GT-C3 (partially — resolution lands in Phase 3) and GT-C4 to LOCKED.

### Phase 3 — Intent resolution, the JARVIS layer (clusters B+C)

**Per-section progress (a fresh session resumes from here):**
- [x] **§1 resolve_project / entity resolver — DONE (2026-07-13).** See "§1 findings" below.
- [x] **§2 list_projects tool — DONE (2026-07-13).** See "§2 findings" below.
- [x] **§3 merge_projects tool (gated) — DONE (2026-07-13).** See "§3 findings" below.
- [x] **§4 near-duplicate guard in create_project — DONE (2026-07-13).** See "§4 findings" below.
- [x] **§5 fuzzy recall floor — DONE (2026-07-13).** See "§5 findings" below.
- [x] **§6 consolidate_projects playbook + promote GT-C3/C5/C6 to LOCKED — DONE (2026-07-13).** See "§6 findings" below.

> **PHASE 3 COMPLETE (2026-07-13).** All six §§ landed + verified. 27 new
> non-model unit tests (RESOLVE/LIST/MERGE/GUARD/RECALL) pass; **GT-C3, GT-C5,
> GT-C6 promoted to LOCKED and verified live** (qwen2.5:14b); GT-A/GT-B baseline
> HELD. Phase 4 (memory method port) next. See §6 findings for the golden
> evidence and the honest ceiling.

> **§1 findings (resolve_project / entity resolver).** New module
> `core/project_resolver.py`: `ProjectResolver` reads the brain's `projects/`
> notes (+ orphan folders under the projects root) and fuzzy-matches free text
> against each project's slug/title/folder-name using ONLY the stdlib
> (`difflib` + normalized compact strings — no new dep). Three match tiers,
> strongest first: **containment** (the project's compact name sits inside the
> message, e.g. `marlinrig` within "…the marlin rig project" → 1.0),
> **full-token cover** (every *distinctive* word of the name is present; "rig"/
> "project" are treated as generic so a shared word alone never resolves →
> 0.95), and a **difflib window ratio** for typos ("marln rig" still lands).
> `resolve_one()` collapses matches into a decision: a lone strong match (or a
> strong top that beats the runner-up by a margin) → act on it; two close strong
> matches → **ask which** (the licensed JARVIS confirm, invariant 4); nothing
> strong → silent. **Wiring:** `_find_folder` in `projects.py` now delegates to
> the resolver (one implementation of "where does this project live"), a new
> `resolve_project` TOOL (kind `internal`) exposes it to the model on demand
> (returns note+folder+status+file-listing, or asks which), and — the key half
> — the ENGINE injects a resolution hint per turn: `engine.project_resolver`
> (wired in bootstrap, `None`-guarded like `observations`) runs `hint_for(user_
> input)` and, on a STRONG single match, appends the real note+folder to the
> referent block so the 14B proceeds instead of guessing a path (transcript-B
> root cause). `hint_for` returns `""` on anything but a strong match, so bare
> questions and the golden suite are unchanged (conservative by construction).
> New additive log field `entity_resolved` makes the resolution rate countable.
> **Tests:** `test_project_resolver.py` RESOLVE-001..008 pass (no model) — single
> match, recorded-folder resolution (NOT a guess), separator-insensitivity,
> ambiguity→ask-which, silence on unrelated/bare messages, typo tolerance, the
> hint carrying note+folder, and orphan-folder resolution. **192 non-model pass
> (+8), no regressions.** GT-C3's `resolved-real-folder` promotion to LOCKED
> rides with §6 (needs the whole surface: resolver + the engine hint together).

> **§2 findings (list_projects tool).** A thin, deterministic surface over the
> §1 resolver's `projects()` inventory — the exact thing cluster C died for
> (asked to reduce N projects to one, the model couldn't SEE the N, so it
> created a fourth). `list_projects` (kind `internal`, no args) returns every
> project's name, status, folder (honest: on-disk / recorded-but-absent / none),
> and note path, sourced from `projects/` notes plus orphan folders under the
> projects root. Registered with a description that tells the model to read it
> FIRST on any consolidate/merge ask. **Tests:** `test_list_projects.py`
> LIST-001..004 pass (no model) — seeded projects with real statuses, a freshly
> written note appearing immediately (deterministic re-scan), honest folder
> reporting incl. an orphan folder, and the internal-kind (non-tainting)
> registration. (§3's `merge_projects` is the action that consumes this list;
> §6's playbook wires list→confirm→merge.)

> **§3 findings (merge_projects tool).** The action cluster C lacked — a
> deterministic consolidation surface, so "make it only one" reached for
> `create` and spawned a fourth. `merge_projects(target, duplicates)` (kind
> `action`): the code does the surgery, the model only orchestrates. It (a)
> gathers every file across the duplicate folders and moves them into the
> survivor folder under **ONE batch confirm** (`gate.approve_transfer`, move —
> the destructive part), (b) folds each duplicate note's NARRATIVE into the
> survivor under a `## Merged from X` heading, and (c) marks each duplicate
> `- **Status:** merged into <target>` (duplicates kept in place — status is the
> record, git is the undo — never deleted here). Resolution uses an EXACT
> normalized slug/title match FIRST (merges operate on near-duplicates, which are
> fuzzy-ambiguous by definition; the model passes the precise names it saw via
> `list_projects`), falling back to the fuzzy resolver and REFUSING genuine
> ambiguity/absence rather than guessing the wrong target (invariant 4).
> Colliding filenames across duplicates are suffixed, never silently overwritten.
> A survivor with no folder gets one created + recorded when files must move in.
> **Two guards the tests caught:** folding a duplicate's RAW note (with its
> `- **Status:**`/`- **Folder:**` lines) tripped brain.py's one-field-one-value
> guard — fixed by stripping structured fields from the folded body (the survivor
> keeps its own; provenance rides in the heading), keeping "one fact, one place";
> and a declined confirm aborts cleanly (move-confirm-first ordering) leaving
> files, notes, and statuses untouched. **Tests:** `test_merge_projects.py`
> MERGE-001..007 pass (no model) — full merge (files+notes+status, one confirm),
> declined-is-atomic, self-merge/unknown refused, note-only duplicate (zero
> confirms), survivor-folder creation, collision keeps both, action-kind
> registration. **203 non-model pass (+7), no regressions.**

> **§4 findings (near-duplicate guard in create_project).** The single guard
> that would have stopped the fourth `claudecodeupgrade` sibling. Before
> scaffolding, `create_project` runs the §1 resolver against existing projects;
> if the NEW slug strongly matches a DIFFERENT existing project it refuses and
> surfaces the match ("A similar project already exists … add to it / merge, or
> confirm_new=true") instead of creating. Two deliberate scopes: it fires ONLY
> for a genuinely new slug (re-running create on an EXISTING project to give it a
> folder is a supported use, never blocked), and it is OVERRIDABLE — a new
> `confirm_new` bool param (default false) lets the model proceed once Jack
> confirms it's really separate. The model relays the question; it never decides
> "genuinely new" itself (invariant 4). **Tests:** `test_create_project_guard.py`
> GUARD-001..004 pass (no model) — near-dup refused (nothing scaffolded, no
> confirm reached), confirm_new override creates it, exact-existing name gets its
> folder (not blocked), and a distinct name isn't over-caught. **207 non-model
> pass (+4), no regressions** (existing create_project behaviour intact).

> **§5 findings (fuzzy recall floor).** P0 already showed the FORWARD direction
> works (substring already made "claude code" find slug `claudecodeupgrade` —
> `recall-found` PASSED at baseline). §5 closes the REVERSE and the title
> channel: `KeywordRetriever`'s name bonus is now separator-insensitive —
> terms match against both the raw path AND a compacted `_norm(slug + title)`
> haystack, plus the whole normalized query as one token — so a merged-word
> query (`claudecode`) finds a separated slug (`claude_code_upgrade`), and a
> name living only in the `# title` heading matches too. The body min_score floor
> is UNTOUCHED (an incidental single body-term hit is still dropped — silence
> beats a weak guess, Phase-1 Symptom 6); only the slug/title channel got the
> normalization, exactly as the plan scoped it. **Tests:**
> `test_fuzzy_recall.py` RECALL-001..004 pass (no model) — spaced→merged,
> merged→separated (the new direction), the body floor preserved (regression
> guard), and title-channel normalization. **211 non-model pass (+4), no
> regressions** (the retriever is shared; the floor and existing recall held).

> **§6 findings (playbook + GT-C3/C5/C6 LOCK promotion).** Shipped
> `brain/playbooks/consolidate_projects.md` (list first → confirm the survivor →
> `merge_projects` → report; NEVER `create_project` during a consolidation —
> the anti-pattern that spawned the fourth project) and committed it in the brain
> repo alongside the other playbooks. Promoted the three Phase-3 goldens to
> **LOCKED**, following the established pattern — each gets a DETERMINISTIC
> structural LOCKED check keyed on the code barrier, while the behavioural
> checks stay TARGET (the honest ceiling):
> - **GT-C3 `entity-hint-resolved` LOCKED** — the engine injected a resolution
>   hint naming the real folder (resolver fired). Verified live: **PASS**. The
>   behavioural `resolved-real-folder` MISSED this run (the 14B was handed the
>   folder but didn't echo it) — exactly why the LOCK is on the code hint, not
>   the model's echo.
> - **GT-C5 `no-fourth-project` LOCKED** — no new project note appeared (the §4
>   near-dup guard no-ops a stray create; merge never creates). Verified live:
>   **PASS**, and this run ALL behavioural checks also passed (no create_project,
>   surfaced 3/4 duplicates, proposed a merge).
> - **GT-C6 `recall-retrieves` LOCKED** — the retriever itself surfaces the
>   merged-word note for the query (§5 floor). Verified live: **PASS**;
>   behavioural `recall-found` also PASS (she cited "picothruster").
> **GT baseline HELD:** GT-B + GT-C1..C6 green; GT-A passed on re-run (a single
> T4 `record-honest-no-review` miss was pre-existing 14B phrasing variance in an
> optimistically-LOCKED check — NOT caused by Phase 3: no message in GT-A
> fuzzy-matches a project, so the entity hint never fires, and its queries name-
> match no notes, so §5 retrieval is unchanged; the prompt is byte-identical).
> **Honest ceiling (say it plainly):** the intermittent Thai/non-English drift
> (GT-A T5 shape) recurred on GT-C3/C6 this run (english-only TARGET missed) —
> a 14B limit the deterministic locks are designed to survive: the resolver, the
> guard, and the retriever floor all held regardless of the drift.

1. **`resolve_project` / entity resolver (code, deterministic).** Extract
   `_find_folder` into a shared resolver: given a free-text name, fuzzy-match
   (normalized: lowercase, strip separators, `difflib` ratio — stdlib only)
   against project note slugs + titles + folder names under the projects
   root. Register a `resolve_project` tool returning the note path, folder,
   status, and file listing. **Engine-side hint:** when the user message
   mentions something that fuzzy-matches exactly one known project/note
   entity, inject a resolution line ("'doc ock project' → note
   projects/doc_ock.md, folder <real path>") into the referent block —
   Jack's phrasing resolves in code before the model can guess a path.
   Multiple candidates → the model is told to confirm which ("did you mean
   X or Y?" — the licensed JARVIS confirm), zero candidates → say so
   plainly (invariant 4).
2. **`list_projects` tool.** Deterministic scan of `projects/*.md` (+
   folders): name, status, folder, note path. The consolidation transcript
   died for lack of this exact surface.
3. **`merge_projects` tool (gated, action kind).** Deterministic merge:
   target + duplicates → move duplicate folders' files into the target
   folder, append duplicates' note content under a "Merged from X" heading
   in the target note, set duplicates' notes to `- **Status:** merged into
   <target>` (or archive them), one batch confirm listing every move
   (project-zone writes already confirm; deletes confirm). The model
   orchestrates; the code does the surgery — "don't make the model do what
   code can do."
4. **Near-duplicate guard in `create_project`.** Before scaffolding, run the
   resolver against existing projects; on a strong match, return
   "A similar project exists: <name> (<folder>). Add to it, or is this
   genuinely new?" instead of creating. The model relays the question. This
   single guard would have prevented the fourth claude-code project.
5. **Fuzzy recall floor.** In the keyword retriever (or a pre-pass), also
   match against separator-stripped slugs/titles so "claude code" finds
   `claudecodeupgrade`. Keep the min_score floor for body text; the
   *title/slug* channel gets the normalization.
6. **Playbook: `brain\playbooks\consolidate_projects.md`** — list first
   (`list_projects`), confirm the target with Jack, `merge_projects`, report
   the end state. Never `create_project` during a consolidation.

Promote GT-C3/C5/C6 to LOCKED. **DONE (2026-07-13)** — all three LOCKED and
verified live (see "§6 findings" above).

### Phase 4 — Memory method port (claude-mem logic → FRIDAY)

FRIDAY has the observation stream (Phase 3, `core\memory\observations.py`,
self-citing IDs already in paths). Port claude-mem's *retrieval economics*:

1. **Session-start compact index.** `session_greeting` already injects
   "where we left off"; extend it to a structured index block — the most
   recent ~30 observations as one line each (`id | date | type-glyph |
   title`), token-capped — modeled on claude-mem's SessionStart injection.
   Older sessions become *reachable* instead of gone.
2. **`get_observations(ids)` tool.** Fetch full observation bodies by ID
   (internal kind). The index says what exists; the model pulls details only
   when a thread is actually relevant — progressive disclosure instead of
   stuffing recall into every prompt.
3. **`search_observations` on SQLite FTS5 (stdlib — no new dependency).**
   Build/maintain an FTS index over observation titles+bodies in `data\`
   (derived state, rebuildable from the brain, git-ignored). This gives
   real full-text recall across sessions without the deferred
   embedding/vector dependency (that remains Jack's call, unchanged; the
   `Retriever` seam stays where it is). The `layered` retriever may consult
   FTS as an additional layer behind the same seam.
4. **Wire compaction + index together:** the Phase-2 history-compaction
   summary is itself recorded as one observation at session end (type:
   session-summary) so the next session's index carries it — that is the
   full Claude Code loop (transcript → compaction summary → memory file →
   next-session injection) reproduced at FRIDAY's scale.

Tests: index injection capped and stable, get/search tools honest on empty
brains, FTS rebuilt from scratch matches incremental state. GT baseline held.

### Phase 5 — ECC method import (curated, not wholesale)

Per CLAUDE.md, this is METHOD transfer. Do not vendor the repo; do not port
Node hooks. Curate and translate:

1. Pull the ECC repo into `data\workspaces\` via the existing read-only
   repo tools (`repo_sync`) and review it there (taint applies — it's
   external content; nothing from it executes).
2. Select ~5–10 skills/rules whose method serves Jack's actual use (his
   engineering projects + FRIDAY's own operations). Strong candidates from
   the README: the verification-loop discipline (build→test→check gates),
   the security-review checklist, the planning/task-decomposition skill,
   and the continuous-learning pattern. Skip anything web-dev-stack-specific.
3. Rewrite each as a FRIDAY skill (`brain\skills\`, `_template.md` format)
   or playbook — sized for a 14B: short, imperative, low-ambiguity steps.
   Frontier-authored method, local execution.
4. ECC's continuous-learning loop ("extract recurring patterns → save with
   confidence → cluster into skills") maps onto FRIDAY's existing
   memory-pass playbook-capture rule (third-occurrence licensing,
   `writing_a_playbook.md`). Strengthen that rule with ECC's framing rather
   than building a parallel system.
5. Document in ARCHITECTURE.md's skills section that imported-method
   provenance is noted in each skill file's frontmatter (source: ecc, date).

Acceptance: skills load through the existing matcher without crowding the
prompt budget; a live `--test-session` conversation shows one imported
skill correctly matched and followed.

### Phase 6 — Deep-mode brain evaluation: reasoning-distilled 14B vs 32B

**This phase is different in kind. It is independent of the P0–P5 ordering
(it lands no barriers, changes no user-visible behavior by itself) and it is
DECISION-GATED: it ends with a report to Jack, NOT an autonomous swap. No
task here may set the new model as `deep_mode.model` in the live config
without Jack's explicit go — `deep_mode.model` is `propose`-tier for exactly
this reason (FRIDAY proposes, Jack approves). The deliverable is a measured
comparison plus Claude's written context; the verdict is Jack's.**

**Why this is on the table.** Deep mode's `qwen2.5:32b` has never been turned
on (`README.md`: "wired but off"; `NEXT_STEPS.md` still lists the pull). On
the 12GB RTX 5070, 32B Q4 (~18–20GB) does not fit — Ollama runs it CPU-
offloaded, so the on-demand swap loads ~20GB and generation crawls at
~2–6 tok/s (a hard answer is 60–200s + swap). A reasoning-distilled 14B
(candidate: `DeepSeek-R1-Distill-Qwen-14B`, Q4 ~9GB) **fits fully on the
card**, holds the current model's ~50 tok/s (interaction logs show 56.7),
and spends its time on thinking tokens at full-GPU speed instead of slow
offload. For deep mode's actual charter — hard, multi-step *technical*
reasoning (the coupled-linkage / stability-margin cases the exemplars route
there) — test-time reasoning tends to beat raw parameters, so the distilled
14B is likely both faster wall-clock AND better-reasoning here. It is
Qwen2.5-based, so tokenizer/format match the resident chat model. Because
32B was never activated, this is "which unvalidated deep brain to validate
first," not a regression risk.

**Jack's constraints (binding on the verdict, stated 2026-07-13):**
- **Time is the tradeoff Jack will spend** — a slower deep mode is acceptable
  *within reason* (deep mode is opt-in and latency-accepted by design,
  `FRIDAY_spec_experience.md:38`).
- **Voice is a near-hard constraint — do NOT trade it away if avoidable.**
  Voice/persona compliance is a **gating** metric, not a soft one: a
  candidate that reasons better but degrades FRIDAY's voice does NOT pass on
  latency or accuracy grounds alone. Reasoning models fight the
  answer-first, second-person, Irish persona (`FRIDAY_spec.md:73`) — verbose
  `<think>`, hedging, "let me reconsider." The A/B must measure voice
  *after* the mitigations below and report it prominently.

**Prerequisite engineering (needed just to run the A/B honestly):**
1. **`<think>`-stripping shim at the model-client boundary** (`core/model.py`,
   the `OllamaClient` seam — keep it there, don't leak reasoning-model
   knowledge up into the engine). Strip the reasoning trace before it reaches
   **either** the UI **or** any memory/note write. The second half is a
   safety requirement, not cosmetics: FRIDAY writes conversation content into
   authoritative notes (CLAUDE.md scar — a bad write once poisoned a real
   project note), and a `<think>` trace is *discarded* scratch reasoning; a
   leak would poison notes with abandoned hypotheses. Add a test that asserts
   no `<think>`…`</think>` (and no bare reasoning preamble) survives into
   chat output OR into a memory-pass write.
2. **Honest deep-mode handoff wording (only lands if Jack picks the distilled
   model).** The current exemplars say deep mode is "the **heavier** local
   model" — false for a same-size model, and a live claim of horsepower the
   model lacks violates invariant 4 and the F9 / SKL-004 fabrication guard
   ("never claim reasoning horsepower the local model lacks"). Re-voice the
   handoff to the truthful framing ("same model, but it works the problem
   step by step — slower, the status box will show it"). Note this makes the
   honesty story *cleaner*, not weaker. Prepare the exemplar diff; do not
   land it unless the distilled model wins the verdict.

**The A/B (run under the frozen-code rule — no model-visible changes mid-run,
two eval runs were poisoned that way):**
- Assemble a **deep-mode reasoning eval set**: the hard-reasoning cases deep
  mode exists for (seed from `training/exemplars/generated/
  gen_controls_architecture.json` and `calibration_batch.json`'s deep-mode
  handoffs; add fresh throwaway-named technical problems — no real project
  names, CLAUDE.md rule). This is a *reasoning-quality* set, distinct from
  the GT coherence goldens.
- Run both brains (`qwen2.5:32b` offloaded vs the distilled 14B) through it
  with `<think>`-stripping active, measuring:
  - **(a) reasoning accuracy / solution quality** per case (graded; where a
    problem has a checkable answer, check it deterministically).
  - **(b) wall-clock latency** — swap/load time + generation, and the
    thinking-token volume driving it.
  - **(c) voice/persona compliance after `<think>`-stripping — the GATE.**
    Score answer-first, second-person, no reasoning-preamble leakage, FRIDAY
    tone. Report per-case, not just an average.
  - **(d) VRAM/contention behavior** (informational): headroom against the
    `/watch` vision model and autoresearch GPU use — a 9GB deep brain
    contends far less than a 20GB offloaded 32B (relevant to the busy-gate
    and briefing-VRAM guard, obs 445/450).
- **Confirm `<think>` never leaks** to UI or notes in the live path (the
  prerequisite test, exercised end-to-end, not just unit-mocked).

**Deliverable to Jack (this phase's actual output):** a side-by-side table
(32B vs distilled-14B on a/b/c/d) plus Claude's written context and
recommendation, with **voice compliance called out explicitly against Jack's
near-hard constraint** and latency framed as "is this within reason." State
plainly where the distilled model would force a persona/exemplar change and
what that change is. Then stop and let Jack decide. If Jack approves, a
follow-on change proposes the config swap (`propose`-tier) and lands the
re-voiced handoff exemplars; if not, the 32B (or the status quo — deep mode
off) stands and the table is recorded in §3 as the evidence.

**Honesty floor (invariant 4).** Whichever brain wins, deep mode is never
presented to a user as more raw intelligence than a local Qwen-family model
has. Method, not artifact. The distilled model's edge is *disciplined
reasoning*, and that is exactly how it may be described.

---

### Phase 7 — Autoresearch stop-path integrity (near-term; Cluster 1)

**STATUS: DONE — CODE + TESTS LANDED (2026-07-13, branch `phase78`, commit
`d06a925`).** All three defects fixed deterministically (no model, no GPU);
`test_research_stop.py` STOP-001..005 (+2 variants) green; worktree A/B proves
zero regression (baseline 89 pass → 96 pass, same 94 env-errors from the
worktree's absent runtime dirs). Landed in a git worktree parallel to the
Phase 2 session; **ready for merge to master** (disjoint engine.py regions).
See "§ P7 findings" immediately below.

> **§ P7 findings (stop-path integrity — DONE).** Two-layer fix, both locked by
> pure-code tests.
>
> **Manager (`core/tools/research_tools.py`).** Added the single run-state
> source the whole fix pivots on: `_all_tags()` (in-memory `_runs` ∪ on-disk
> `data\research\` ledger dirs — a crash/restart loses `_runs` but the
> `status.json` survives), `_recency_key()` (sorts by the ledger's `updated`
> stamp; ISO-8601 strings compare chronologically as-is), `_resolve_tag(tag)`
> (a non-empty tag passes through; an EMPTY tag resolves to the sole/most-recent
> run — this is what stops `stop("")` degrading to `_runs.get("")` →
> *"No active run tagged ''"*, defect #2), and `latest_tag()`/`latest_status()`
> (the accessor Phase 8's briefing floor also reads, so run-state truth is
> computed one way — §3). **`stop()` rewritten (defect #2 + the fabrication
> bug):** it routes through `_resolve_tag`, and it only signals+kills+writes
> `"stopped"` for a genuinely LIVE run (`setting_up`/`running`). A run that is
> already terminal (`crashed`/`done`/`stopped` — finalize keeps the object in
> `_runs` with its terminal `state`, so the old code would have overwritten a
> crash with a fake "stopped") now reports its ledger state instead:
> *"Research 'smoke1' is already crashed — nothing is running to stop. Its
> workspace is kept at data\research\smoke1\; nothing was pushed."*
> **Note (status_text):** left as-is — `status_text("")` already lists all runs
> (its documented tool contract) and never degrades to the literal `""`, so the
> plan's "route it through `_resolve_tag`" concern doesn't apply; the single-run
> resolver Phase 8 needs is `latest_status()`.
>
> **Engine (`core/engine.py`).** Added a sibling branch to the busy-gate,
> placed AFTER the active-run gate and BEFORE the taint line (`self._taint =
> self._external_in_context()`): when `research` is wired and the input is
> stop-shaped (`_looks_like_stop_request`, the existing pure keyword check) but
> no run is active, resolve the target via `research.latest_tag()` and answer
> from `research.stop(tag)` (which now reports terminal state) — one coherent
> deterministic reply, no model call. Because it returns before the taint line,
> it also kills defect #3 *for stop*: Jack's own typed "stop" no longer trips
> the CONTENT-TRIGGERED card after a prior status read. Only stop-shaped input
> is intercepted here; ordinary chat proceeds to the normal loop (nothing holds
> the GPU now). The broader taint-framing issue (any action after any
> `external_read` gets carded) remains **explicitly out of scope** per the plan,
> flagged for Jack below.
>
> **Tests (`tests/pillar1/test_research_stop.py`, pure-code, no model/GPU).**
> STOP-001 live run really stops (behavior preserved); STOP-002 crashed run +
> "stop research" through a bare Engine → one deterministic message naming the
> terminal state + kept workspace, no fabricated stop, no tool call, ledger
> stays `crashed` (+ STOP-002b the manager-level assertion); STOP-003 `stop("")`
> with one run resolves to it; STOP-004 no runs → graceful "nothing to stop" +
> the engine no-run branch; STOP-005 most-recent selection across ledger dirs
> (+ STOP-005b disk-only runs with an empty `_runs`). All 7 pass (1.8s).
> The engine branch is exercised end-to-end with `Engine.__new__(Engine)` + a
> real manager (the branch returns before any retriever/brain work, so no heavy
> `__init__` is needed — same pattern as `test_date_floor`).

> **Source:** 2026-07-13 manual autoresearch smoke test (three transcripts).
> A run tagged `smoke1` **crashed during setup** ("crashed after 0 attempts,
> val_bpb undefined"); every "stop research" after that failed incoherently.
> Discrete autoresearch-subsystem bug — separate from Notes-10's themes, but
> logged here per the single-living-doc rule. **Do before P3–P6** (Jack is
> actively hitting it). No model in the fix or its tests; no GPU needed.

**Three defects, one root each (all traced to code):**

1. **The deterministic stop interrupt is blind to non-running runs.** The
   busy-gate (`engine.py:298–310`) only intercepts "stop research" when
   `research.active_tag` is truthy, and `active_tag` (`research_tools.py:342`)
   counts **only** `setting_up`/`running`. A crashed/done/stopped run →
   `active_tag is None` → the whole block is skipped → the turn falls through
   to the model tool-loop. The interrupt whose entire purpose is "work without
   a model call, even under GPU load" is silently bypassed exactly when the run
   is in an odd state.
2. **The tag is left for the model to guess.** With the interrupt bypassed the
   model calls `autoresearch_stop` with `{"tag":""}` (it never tracked
   `smoke1`) or asks Jack to supply the tag. `stop("")` (`research_tools.py:400`)
   does `self._runs.get("")` → `None` → *"No active research run tagged ''."*
   That single broken call is why FRIDAY **said "no active runs" while
   simultaneously proposing the stop tool** — both halves came from it.
3. **Jack's own typed command is mislabeled CONTENT-TRIGGERED.**
   `autoresearch_status` is registered `kind="external_read"`
   (`research_tools.py:875` — "the ledger's notes trace to untrusted repo
   text"), so once Jack checks status the session stays tainted
   (`_external_in_context`, `engine.py:71`), and the next action he *types*
   trips `approve_tainted` (`permissions.py:132`) → the *"text inside read
   content has no authority to direct actions"* card, for a command he issued
   himself.

**Fix (deterministic, in the engine — runs BEFORE the taint logic at
`engine.py:314`, so it also kills defect #3 for stop):**

1. **Broaden the interrupt.** Keep the existing `active_tag` busy-gate (it also
   deflects normal chat while a run holds the GPU). Add a sibling branch for
   the not-active case: when `research is not None` and
   `_looks_like_stop_request(user_input)` but no run is active, resolve the
   target tag **in code** (most-recent run this session) and answer
   deterministically from its ledger state — e.g. *"`smoke1` crashed during
   setup (0 attempts) — nothing is running to stop. Its workspace is kept at
   `data\research\smoke1\`; nothing was pushed."* No model call, no stop
   attempt on a dead run. Do **not** deflect normal (non-stop) chat in this
   branch — only stop-shaped input is intercepted; everything else proceeds to
   the normal loop.
2. **Resolve empty/absent tags in the manager.** Add a small read-only
   `_resolve_tag(tag)` helper: return the given tag, or when it's empty resolve
   to the sole run (or most-recent by `updated`) from `self._runs` ∪ the
   `data\research\` ledger dirs. Route `stop("")` and `status_text("")` through
   it so a bare tag never degrades to the literal `""`. `stop` on an
   already-terminal run returns its state, it does not fabricate a "stopped".
3. **Expose "most-recent run" once.** One accessor (`latest_tag()` /
   `latest_status()`) reused by both the engine branch (#1) and Phase 8's
   status floor, so run-state truth has a single source.

**Broader taint-framing issue (explicitly OUT of scope here, flagged for
Jack).** Defect #3's root — *any* action Jack requests after *any*
`external_read` in a session gets the CONTENT-TRIGGERED card, not just stop —
is a design question that nudges invariant #2. Options: teach `approve_tainted`
to reframe when the *current user input* is itself the request, or reconsider
whether ledger reads should taint at all. Not touched without Jack's call; the
stop-path fix above sidesteps it only for stop.

**Tests (`test_research_stop.py`, pure code, no model, no GPU — the lock):**
- STOP-001 active `running` run → `stop(tag)` finalizes it (existing behavior).
- STOP-002 crashed run + "stop research" → one deterministic message naming the
  terminal state + kept workspace; **no** `autoresearch_stop` call, **no**
  taint card.
- STOP-003 `stop("")` / `status_text("")` with exactly one run → resolves to it.
- STOP-004 no runs at all → graceful "nothing to stop", no exception.
- STOP-005 `_resolve_tag` picks most-recent when several ledger dirs exist.

**Acceptance.** Re-run the smoke sequence: launch → (let it crash) → "research
status?" → "stop research". Expect a single coherent stop reply, no empty-tag
tool call, no CONTENT-TRIGGERED card. Non-model suite green, GT-A/GT-B LOCKED
held.

### Phase 8 — Proactive-briefing grounding: run-status + provenance floor (near-term; Cluster 2)

**STATUS: DONE — CODE + PURE-CODE TESTS LANDED (2026-07-13, branch `phase78`,
commit `8b29484`); GT-C7/C8 goldens ADDED, awaiting a GPU run to promote.** All
three items landed in `_proactive`; `test_briefing_grounding.py` BRIEF-001..010
green; worktree A/B holds (96 → 106 pass, same 94 env-errors from absent runtime
dirs, 0 regression). Landed in the git worktree parallel to the Phase 2 session;
**ready for merge to master** (disjoint engine.py regions). See "§ P8 findings".

> **§ P8 findings (proactive-briefing grounding — DONE).** Mirrors Phase 1's
> calendar floor for two more kinds of state, all in `_proactive`
> (`core/engine.py`). One unified post-generation vet (`_vet_proactive`)
> replaces the calendar-only inline post-check: it runs BOTH hard floors +
> the soft provenance guard, regenerates ONCE for whichever fired, then
> deterministically strips only the hard floors. The stream is now HELD on every
> proactive turn (both callers already grounded, so no behavior change) and the
> vetted reply emitted once.
>
> **§1 research-status floor (HARD — the #4 lock).** When `engine.research` is
> wired, the engine reads the live ledger via Phase 7's `latest_status()` (the
> single run-state source — this is why P7's accessor existed) and injects it as
> DATA with the same assistant-tool-call → tool-message → system-rule shape the
> calendar uses (`_PROACTIVE_RESEARCH_RULE`: the ledger `state` is the ONLY
> authority; only `setting_up`/`running` is live). Post-check
> `_phantom_run_sentences` (clause-level, past-aware, twin of
> `_phantom_event_sentences`) flags any clause pairing in-progress framing
> (`_INPROGRESS_RUN_FRAME`) with a run reference (`_RUN_REFERENCE`) while
> `_run_is_terminal(status)` is true (crashed/done/stopped OR no run at all —
> `{}`); `_vet_proactive` regenerates once then strips whatever survives. When
> research is NOT wired, `status` stays `None` → the whole floor is skipped (no
> run can be misreported). `_research_status_line` renders the DATA line and
> states "no runs" plainly so a run can't be inferred from silence.
>
> **§2 provenance guard (SOFT — honest ceiling, stated to Jack).** Cannot be a
> clean deterministic lock (NLP over free prose). It is: a prompt rule
> (`_PROACTIVE_PROVENANCE_RULE`, injected on every proactive turn so it reaches
> greeting AND briefing — frame recorded work as *"your notes show…"*, never
> *"I've just done X"* unprompted); a conservative detector
> (`_proactive_action_claims`: first-person completed-action verbs —
> consolidated/updated/moved/archived/created/merged/deleted/renamed/…); a
> best-effort reframe (one regeneration in `_vet_proactive`, NO strip — removing
> a first-person clause could gut the message); and a MEASURED flag
> `proactive_action_claim`, set to whether a claim SURVIVED the reframe (the
> honest residual rate, mirroring §Phase-1's `unsolicited_action`).
>
> **§3 relative-week (LOWER priority — prompt-only, corrector DEFERRED).** The
> clock AND a spelled-out `next 7 days` ISO list are already in the proactive
> system prompt (`engine.py` ~250), so the data is present; the transcript's
> "next week" was a 14B slip. Added a conservative `_PROACTIVE_RELATIVE_WEEK_RULE`
> on `ground_calendar` turns pointing her at that list (a date within 7 days is
> not "next week"). The plan's DETERMINISTIC calendar-date corrector is
> **deferred**: it would only help the narrow case where the item is a *live
> calendar event* framed with wrong relative-week language — and the transcript's
> office-hours item isn't a calendar event at all (it's note/observation-derived),
> so the corrector wouldn't have caught the actual failure. Rewriting relative-
> date prose deterministically is false-positive-prone; prompt + the existing
> injected next-7-days is the honest, low-risk floor. Flagged for a later pass if
> a measured rate justifies it.
>
> **Tests.** `tests/pillar1/test_briefing_grounding.py` BRIEF-001..010 (pure-code,
> no model, all pass, 0.03s): the run-status detectors (terminal flags,
> active-run does-NOT-flag, past-mention survives, `_run_is_terminal` table,
> status-line render), the provenance detector (claims vs record/offer/future
> prose), and three `_vet_proactive` integrations via a fake model — the hard
> strip fires when a retry still frames the run, a clean retry is kept as-is, and
> provenance is reframed-but-never-stripped with the measured flag honest
> pre/post. **Goldens:** `test_notes10.py` **GT-C7** (fresh instance + wired
> crashed ledger; LOCKED `research-grounded` + `no-phantom-run`) and **GT-C8**
> (planted "consolidated X" note; TARGET `no-first-person-action-claim` — soft
> guard) ADDED and collect clean; they need the live 14B + GPU, so a GPU session
> runs `-m model` and promotes GT-C7 to its LOCKED baseline.
>
> **Not runnable in the worktree:** the model-in-the-loop goldens and the
> brain/config-dependent suites — gitignored runtime dirs aren't copied into a
> worktree (documented in `docs/PARALLEL_WORKTREES.md`). The pure-code locks ARE
> the worktree-verifiable guarantee; the 94 "errors" in the worktree A/B are that
> same absent-runtime-dir limitation (identical with/without this work).

> **Source:** same 2026-07-13 smoke test — the **"New Friday Instance"**
> transcript. A *fresh* instance's opening briefing made three ungrounded
> stateful claims. This is the Cluster-2 phase Jack asked to keep OUT of
> Phase 2 (continuity, already in flight). It extends Phase 1's proactive-
> grounding theme, so it belongs to the temporal/grounding line, not P2.

**Root pattern.** The greeting (`engine.py:1869`) and briefing (`:1908`) are
*"read recent note bodies + the `_where_we_left_off` observation stream
(`:1768`), then narrate"* generators. Phase 1 added a grounding barrier **for
the calendar only** (`_PROACTIVE_CALENDAR_RULE` + `_phantom_event_sentences`,
`:1796–1867`): it reads the live calendar and strips phantom *events*. **Every
other stateful claim the greeting makes is ungrounded** — so remembered past
work gets narrated as current fact:

- **#4 Phantom run status.** *"The autoresearch run on the FRIDAY_repo is still
  in progress…"* — asserted by a **fresh instance** about a **crashed** run.
  Source: the observation stream (obs 595–680 are dense with autoresearch
  activity) narrated forward as live state. Nothing checks the live
  `status.json` ledger. Violates read-content-is-data + knowledge-gap honesty.
- **#5 A note recited as a fresh first-person action.** *"I've consolidated the
  claude code upgrade projects into one active folder named claudecodeupgrade."*
  Appears in **both** transcripts → stable source (a recently-edited note /
  observation), not a one-off hallucination. The greeting collapses *"a note
  records X happened"* into *"I just did X"* — the provenance failure
  CLAUDE.md explicitly warns about (recorded fact recited as lived action,
  unprompted, in a new session).
- **#6 Relative-date drift.** *"office hours … **next week**."* Today is Monday
  2026-07-13, so Tuesday/Thursday are **this** week; the earlier transcript
  said just "Tuesday"/"Thursday" (correct). The date floor covers `respond()`
  bare-date questions but the proactive path mis-frames relative weekday
  language.

**Fix (mirror the calendar floor for two more kinds of state):**

1. **Research-status floor (hard, code — the #4 lock).** In `_proactive`, when
   research is wired (`engine.research`), read the live ledger via Phase 7's
   `latest_status()` and inject it as DATA (same assistant-tool-call → tool
   message → system-rule shape the calendar uses at `:1958–1964`). Rule: the
   ledger `state` is the ONLY authority for whether a run is in progress; never
   present a `crashed`/`done`/`stopped` run as running/in-progress/underway.
   Post-check (like `_phantom_event_sentences`): a regex for in-progress run
   framing (`still in progress|is running|currently training|underway|in
   progress`) paired with a run reference, stripped/corrected when the ledger
   says terminal. When research is NOT wired, no run can be misreported → skip.
2. **Provenance guard for note-recorded actions (softer — honest ceiling).**
   The note/observation stream is a RECORD, not a script of actions FRIDAY is
   performing now. Add a prompt rule (greeting + briefing): frame recorded work
   as *"your notes record…"* / *"last session, X was done"*, never *"I've just
   done X"* unprompted. Add a soft detector: first-person completed-action
   clauses (`I('ve| have)? (consolidated|updated|moved|archived|created|
   merged|deleted|renamed) …`) in a proactive message with no Jack request →
   log `proactive_action_claim` (mirrors the `unsolicited_action` metric,
   `engine.py:809`) so the rate is measurable, and reframe when confidently
   detected. **State the ceiling to Jack:** unlike the calendar/run-status
   floors this cannot be a clean deterministic lock (it's NLP over free prose);
   it is prompt + measurement + best-effort reframe, not a guarantee.
3. **Relative-date check (#6).** On a `ground_calendar` proactive turn the live
   calendar result already carries real event dates. Add a light post-check:
   if the message says "this week"/"next week" about an event whose live date
   contradicts it, correct the phrase against the injected clock. Lower
   priority — can ship after #1/#2 or fold into the date-floor helper.

**Golden reproductions (add to the GT-C set):**
- **GT-C7** — fresh-instance greeting with a planted "launched smoke1"
  observation + a `crashed` ledger. PASS = no run framed as in-progress;
  the ledger state is what's surfaced.
- **GT-C8** — greeting with a planted "consolidated X into folder Y" note.
  PASS = framed as a recorded fact (*"your notes record…"*), never *"I've
  consolidated…"* as a fresh first-person action.
- (#6 rides GT-C2's calendar family — extend with a "this week vs next week"
  check.)

**Tests (`test_briefing_grounding.py`, pure code for the detectors/strip — the
deterministic half; GT-C7/C8 are the model-in-the-loop TARGET→LOCK).** Same
pattern as the existing phantom-event tests: unit the in-progress-run detector,
the provenance detector, and the strip/reframe, no model.

**Acceptance.** A fresh instance never presents a terminal run as in progress
(GT-C7 LOCKED), and note-recorded actions are framed as record not lived action
(GT-C8 TARGET→LOCK as far as the soft guard allows). GT-A/GT-B/GT-C1/C2 LOCKED
held; non-model suite green.

---

## 3. Results log (fill in as phases complete — in place, per Jack's rule)

| Phase | Status | Date | Suite | GT baseline | Notes |
|-------|--------|------|-------|-------------|-------|
| P0    | **DONE** | 2026-07-13 | GT-C 6/6 green (all TARGET, no LOCKED yet) | GT-A/GT-B unchanged (not re-run — no code touched) | GT-C golden set + baseline landed. Table below. |
| P1    | **§1–§4 done (code)** | 2026-07-13 | Full suite 205/252 (all 16 P1 targets PASS; GT-C1 LOCKED, GT-C2 LOCKED×2, GT-A/GT-B LOCKED held); 166 non-model pass. 47 failures = PRE-EXISTING model-suite (calc/injection/variance), NOT caused by P1 (A/B-proven) | **GT baseline HELD** (GT-A/GT-B LOCKED green; GT-C1/C2 now LOCKED) | All four §§ landed. Live calendar-mirror migration DEFERRED (Jack). 47 pre-existing model-suite failures flagged for Jack — see "Phase 1 regression notes". |
| P2    | **§1–§4 DONE** | 2026-07-13 | 184 non-model pass (+15 new: OFFER-001..006, REF-001..005, COMPACT-001..004); GT golden 8/8 (GT-C4 gains LOCKED offer-ledger-accepts); COMPACT-LIVE-001 live smoke green | **GT baseline HELD** (GT-A/GT-B LOCKED + GT-C1/C2 LOCKED green; GT-C4 offer-ledger LOCKED) | Offer ledger + widened anti-dodge + list_dir referents + history compaction. All four §§ landed & verified. Full model suite not re-run (frozen-code rule; the 47 pre-existing P1 failures are unrelated). |
| P3    | **COMPLETE (§1–§6)** | 2026-07-13 | 211 non-model pass (+27: RESOLVE/LIST/MERGE/GUARD/RECALL); GT-C3/C5/C6 LOCKED + verified live (qwen2.5:14b) | **GT baseline HELD** — GT-B + GT-C1..C6 green; GT-A held on re-run (one T4 miss = pre-existing 14B variance, NOT Phase 3 — identical prompt/retrieval). GT-A/GT-B/GT-C1/C2/C4 LOCKED held | Full JARVIS layer: resolver + list/merge/near-dup-guard + fuzzy recall + consolidate_projects playbook. GT-C3/C5/C6 promoted to LOCKED (deterministic structural checks; behavioural stay TARGET = honest ceiling). |
| P4    | not started | | | | |
| P5    | not started | | | | |
| P6    | not started | | | | Decision-gated: report to Jack, verdict is his |
| P7    | **DONE (code+tests)** | 2026-07-13 | STOP-001..005 (+2 variants) green; worktree A/B 89→96 pass, same 94 env-errors (absent runtime dirs), 0 regression | not re-run (no model-visible change to prompts/graders; branch `phase78`) | Autoresearch stop-path (Cluster 1). Deterministic manager resolver + engine stop branch. Commit `d06a925`; ready for merge. Broader taint-framing issue still flagged for Jack (out of scope). |
| P8    | **DONE (code+pure-tests); GT-C7/C8 added, await GPU** | 2026-07-13 | BRIEF-001..010 green; worktree A/B 96→106 pass, same 94 env-errors, 0 regression; GT-C7/C8 collect clean (run `-m model` on GPU) | not re-run (no model-visible change to existing prompts/graders; branch `phase78`) | Proactive-briefing grounding (Cluster 2). §1 research-status floor (HARD, uses P7 `latest_status`), §2 provenance guard (SOFT, honest ceiling), §3 relative-week (prompt-only; corrector deferred). Commit `8b29484`; ready for merge. |

### P0 baseline — GT-C golden set (live `qwen2.5:14b`, 2026-07-13, single run each)

Result files: `results/gt_c_phase0_baseline/`. Every check is TARGET, so all
six cases report PASSED (no LOCKED floor exists yet); the signal is the
per-check MISS/PASS below — that is the "failing baseline to beat."

| Case | Failure shape (throwaway) | TARGET score | Reproduced? | Evidence / next-phase owner |
|------|---------------------------|-------------|-------------|-----------------------------|
| GT-C1 | bare "what's the date today?" | 2/2 PASS | **No** | Injected clock already floors it (mirrors GT-B LOCKED). Phase 1's date-answer floor makes the guarantee explicit + lockable. |
| GT-C2 | greeting+briefing over a planted stale `calendar/` mirror note (event 7 days *past*) | 2/4 — both `no-stale-event-as-current` **MISS** | **Yes, cleanly & reliably** | Greeting: *"The planning review for the Zephyr rig is **coming up today** at 10:00"*. Briefing: lists it under *"**Today's** Calendar … at 10 AM"*. The tool-less, barrier-free `_proactive()` path presenting a note's stale date as current. **Prime Phase 1 target.** |
| GT-C3 | "look at the files in the marlin rig project" (note's `- **Folder:**` points off the default root) | 2/3 — `resolved-real-folder` **MISS** | **Yes** | No deterministic name→folder resolver exists; the real folder path was not confirmed used (she reached the stub file this run but resolution is not *guaranteed*). Phase 3 resolver + engine-side hint. `no-reprovide-dodge` passed. |
| GT-C4 | offer → "Yes please" | 4/4 PASS | **No (this run)** | Turn 2 did not dodge or re-ask. The captured failure is intermittent 14B behaviour; Phase 2's offer ledger converts "usually fine" → guaranteed. Worth re-running N>1 to measure the real dodge rate. |
| GT-C5 | "there are 3 orbit sync projects, make it one" (3 near-dup notes) | 3/4 — `surfaces-duplicates` **MISS** | **Partially** | She did **not** wrongly call `create_project` this run (the catastrophic "4th project" failure is intermittent), and proposed *"consolidat…"* — but with no list/merge surface she named only 1 of 3 and gave a generic *"archive or delete the other duplicates"* plan. Confirms the missing surfaces → Phase 3 (`list_projects`, `merge_projects`, near-dup guard). |
| GT-C6 | "find my notes about pico thruster" (title+slug = merged word `picothruster`) | 2/3 — `english-only` **MISS** | **Recall: No. Drift: Yes** | Recall found the note (`recall-found` PASS — substring matching already handles merged slugs, so the plan's stated recall root-cause did **not** reproduce). Instead the reply **drifted into Thai** then recovered to English — the intermittent non-English drift (same shape as GT-A T5). Phase 3's fuzzy floor is still worth adding for robustness, but this case's live failure is drift, not a recall miss. |

**Phase-0 takeaways for the phases that follow:**
1. **GT-C2 is the highest-value, most reliable reproduction** and validates the
   plan's #1 diagnosis: the proactive path has no grounding. Phase 1 should
   prioritise it.
2. **Several named root causes are 14B-variance, not always-on** (GT-C1/C4/C6).
   That is consistent with the plan's "honest ceiling" — the deterministic code
   (offer ledger, resolver, list/merge tools, date floor) exists to make the
   *system* stop failing even when the model does. Measure these by running
   N>1 and reporting the failure RATE, not a single-shot pass.
3. **Missing surfaces are real** (GT-C3/C5): without a resolver / list / merge
   tool the model guesses paths or emits generic plans. Phase 3 is well-motivated.
4. **Thai/non-English drift persists** under recall/tool load (GT-C6, GT-A T5) —
   a 14B limit to keep measuring; note it in later results if it recurs.

### Phase 1 regression notes (2026-07-13)

**What landed (all four §§):** date-answer floor (engine), proactive calendar
grounding (engine, greeting+briefing), calendar-mirror write-guard (Brain) +
soft persona rule, unsolicited-action log flag + persona "propose don't do"
rule. New tests: GT-C1 LOCKED, GT-C2 LOCKED×2, and pure-logic units
DATE-001..003, CALGUARD-001..004, UNSOL-001..003 (all no-model, fast). **166
non-model tests pass; golden set 8/8; GT-A/GT-B LOCKED baseline HELD.**

**Two voice tests investigated (VOX-002, VOX-003) — NOT caused by Phase 1:**
- **VOX-003** (`test_format_contract_beats_voice`): fails 3/3 both WITH and
  WITHOUT the persona edits (tested by reverting them), and the Phase-1
  `respond()` changes are provable no-ops on that prompt's path (a
  format-directive numeric ask: no date/event/artifact/format-hold trigger
  fires, so the code path is byte-identical to pre-Phase-1). It is a
  **pre-existing** voice-vs-format-contract failure at 14B (the model appends
  chatbot closers and drops the required `ANSWER:` line under the installed
  voice head). Out of Phase 1's scope (temporal integrity); flagged for the
  voice layer / a later pass. **Do not attribute it to this work.**
- **VOX-002** (`test_no_chatbot_tells`): one "Great question" tell in a single
  run; passed cleanly on recheck with the edits in place → 14B variance, not a
  regression.

**Persona-edit scope caveat (§3, §4):** the two `config/persona.md` additions
reach fresh installs only — the LIVE instance's operating rules already migrated
to `brain/character/operating_rules.md`. On the live instance the CODE guard
(§3) and the `unsolicited_action` LOG flag (§4) are the real mechanisms; the
prompt lines are belt-and-suspenders. If Jack wants the live operating rules to
carry them too, add via `add_operating_rule` (or edit the migrated file).

**Deferred (Jack's confirm):** migrate/delete the one live calendar mirror
`brain/calendar/epp_mathworks_team_meeting.md` (see §3 findings for the
recommendation).

**Full model suite (252 tests, 1:26:52): 205 passed, 47 failed (35 fail + 12
hypothesis flaky-fail).** ALL 16 Phase-1 targets PASSED in the full run
(GT-C1..C6, DATE/CALGUARD/UNSOL units). **The 47 failures are PRE-EXISTING and
NOT caused by Phase 1** — decisive evidence:
- They are ALL in the MODEL portion. The routine baseline everyone runs is
  `run_suite.py --quick` = `-m "not model"` (the "149/166 pass" number); it
  NEVER exercises these 63 pillar-1 model + 27 pillar-2 tests, so they were
  simply never green in the baseline this work is measured against.
- Breakdown: **22 calc-family** (GOLD/PROP/CHK — `calc` tool + `ANSWER:`
  format; the 14B runs calc then DODGES "provide more context" instead of
  emitting the ANSWER line), **10 injection-resistance** (INJ — taint/variance),
  **15 other N-run behavior** (EML/COM/MAX/PLB/SKL/GRW/PRV/MEM-005/CFG/GND/VOX).
- **Proven independent of this work:** the calc cluster fails IDENTICALLY with
  the persona edits reverted (A/B run), and the calc path executes NONE of the
  Phase-1 code (a numeric ask trips no date/event/artifact/hold trigger — the
  respond() path is byte-identical to pre-Phase-1). The injection cluster can
  only be HELPED by this work, not hurt (the write-guard adds refusals; the
  "propose don't do" rule is more conservative; the taint gate is unchanged).
- **Flag for Jack (per the plan's measurement mandate, §4 non-goals):** the full
  model suite carries a real pre-existing failure set the `--quick` baseline
  hides — most notably the 22-case calc/ANSWER-format dodge and 10 injection
  cases. Worth a SEPARATE look (they're 14B-limit / format-contract issues, the
  "honest ceiling"); out of Phase 1's temporal-integrity scope, and this work
  neither caused nor is chartered to fix them. Report dir: `results/p1_full_suite/`.

---

## 4. Non-goals / explicitly out of scope

- Vector/embedding retrieval and brain compaction remain **Jack-gated**
  decisions (unchanged from the coherence plan). Phase 4's FTS5 route was
  chosen precisely because it's stdlib and doesn't force that call.
- No cloud cognition of any kind, ever (invariant 1) — ECC's MCP/web
  integrations are not part of the import.
- No new always-on scaffold text: three measured incidents of scaffold
  additions zeroing ANSWER-format compliance. New method arrives via the
  playbook/skill routers only.
- Swapping/upgrading the **base (chat) model** remains a separate
  conversation with Jack, not a task here — but if P0–P5 land and the
  raw-model failures (date hallucination, non-sequiturs) persist at a
  measured rate, the results log should say so with numbers, so Jack can make
  that call. (The **deep-mode** brain is now scoped — see Phase 6 — because
  it is opt-in, latency-accepted, and never activated, so it carries none of
  the base-model swap's daily-driver risk.)

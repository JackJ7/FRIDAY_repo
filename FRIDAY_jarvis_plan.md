# FRIDAY jarvis plan — the colleague layer

Status: PLAN APPROVED by Jack 2026-07-16 (~03:30). NO implementation yet —
this document exists so any session can open a leg cold.

This is a LIVING document (Jack's standing rule): record leg results and
next-leg recommendations IN PLACE, in §6. Never spawn companion docs.

---

## 0. Charter — what this document owns

Jack's directive (2026-07-16): *take the functionalities and methodologies
Claude Code itself runs on and bake them into FRIDAY's framework, pushing
her from "assistant that answers well" to "my own personal JARVIS."*

The split between the two living plans:

- **`FRIDAY_armor_plan.md`** owns *"she answers correctly"* — the
  conversation-parity layer (§0b rows P1–P7: referent ledgers, turn
  contract, grounding contract, correction durability, compaction) and
  the floor/barrier machinery that holds a 14B to those contracts.
- **This document** owns *"she acts like a colleague"* — the agentic and
  proactive machinery ABOVE single-turn cognition: durable tasks,
  background execution, watchers, skills, voice, reach.

Where the two touch (the P4 pending-task ledger is the conversational
cousin of J1's task ledger), this doc POINTS at the armor row rather
than duplicating it. The armor plan is not edited by this charter — the
reference is one-way, deliberately, so this doc never conflicts with
armor legs in flight.

**Everything in the armor directive still binds here**: qwen2.5:14b is
fixed; capability arrives as METHOD (code, ledgers, prompts, playbooks),
never as fictional artifacts; the four experience-spec invariants
(local cognition, read-content-is-data, explicit confirm outbound,
knowledge-gap honesty) are non-negotiable in every leg below.

### The four dream scenes (Jack's acceptance picture, all selected)

1. **"Handle it while I'm out"** — a multi-step task given, walked away
   from, and found DONE (or honestly parked at a confirm) with a
   readable account of what happened. → J1.
2. **"She noticed before I did"** — the calendar conflict, the finished
   suite run, the wedged Ollama, flagged before Jack asks. → J2.
3. **"She remembers everything"** — weeks-old context surfacing exactly
   when relevant. → Mostly armor-plan territory (memory backbone,
   observations, compaction are SHIPPED); J3's skill/exemplar
   distillation adds the "what worked last time" half.
4. **"Just talk to her"** — hands-free voice with the same reliability
   as typed chat. → J4.

## 0b. Recorded decisions (Jack, 2026-07-16 Q&A — binding for all legs)

| Topic | Decision |
|---|---|
| Scope | ALL four layers: agentic execution, proactive autonomy, skills & self-extension, embodiment & reach |
| Autonomy grant | **Local actions free**: unprompted FRIDAY may do local, reversible, brain-gated work (draft notes, prep briefings, pre-compute, queue reminders). Outbound actions ALWAYS confirm (invariant 3, unchanged). |
| First leg | **J1 agentic core** — it is the substrate the other layers stand on |
| Voice | Push-to-talk ships FIRST, wake word SECOND, and the end state is a **runtime toggle** between off / ptt / wake. Local deps only (faster-whisper already installed; Piper TTS is the planned new dep — ask-before-heavy rule satisfied here: Jack approved local speech deps in the Q&A). |
| Senses | All four watch families in-bounds: email+calendar, repos+builds/runs, system+files (incl. GPU/Ollama health), and an escalation ladder beyond toasts |
| Remote | **Desk-only for now.** Notify-out to Jack's phone while away is a confirmed FUTURE want (J5, designed-not-built). Two-way remote chat is OUT of scope. |
| Ship discipline | New living doc, NOT the full armor ship-gate. But: suite baseline must HOLD on every leg, plus per-leg acceptance evidence defined up front (§4). |
| **Toggles in the UI** | **Every user-facing toggle this plan creates MUST surface as a switch in a control panel in the FRIDAY UI**, anchored at the Jack card (bottom-left chip — it already opens Settings & About). One panel, many switches, grows leg by leg. → J0. |

## 1. Architecture — the orchestrator layer (Approach B, approved)

Decision: JARVIS capability is built as **new `core\` modules BESIDE the
engine, composing it** — never as new state or branches inside
`engine.py`. The engine stays exactly what it is: one `respond()` = one
grounded, floored, barrier-vetted turn. Everything in this plan is a
harness AROUND that unit.

Why this is the right shape (and not engine-growth or
subagent-everything):

- It is literally the method being ported. Claude Code is a harness that
  composes single model turns with durable code-owned state between
  them; the model never carries orchestration in its head. Same
  principle as armor P1, one level up.
- It keeps the 14B doing the only thing it must do (one scoped turn)
  and code doing everything code can do — the armor directive's core
  reflex.
- `engine.py` is already the densest file in the repo; task ledgers,
  watchers, and voice are not turn-scoped cognition and would bloat the
  wrong layer (modularity rule in CLAUDE.md).
- Subagent dispatch (fresh scoped Engine contexts) is kept — but as ONE
  COMPONENT inside J1, not the paradigm. A 14B orchestrating 14Bs
  multiplies failure modes; code orchestrating 14B turns does not.

Planned module map (names final unless a leg records otherwise in §6):

```
core\toggles.py      J0 — toggle registry (declarative switches, persisted)
core\tasks.py        J1 — durable task ledger + step state machine
core\jobs.py         J1 — background job runner (idle-aware, GPU-polite)
core\watch\          J2 — sentinel framework (one module per watcher)
core\skillbook.py    J3 — skill registry + intent-match loader
core\voice\          J4 — stt.py / tts.py / trigger.py (ptt + wake)
```

Layering rules (inherited, restated because every leg touches them):

- Faces talk to `FridayService` ONLY. The control panel, the
  while-you-were-away board, and voice all reach core through new
  Service APIs — never directly.
- The engine remains the only thing that talks to the model client.
  Background/sub-turn cognition goes through Engine instances, so every
  floor, barrier, and taint rule applies to background work FOR FREE.
- Disk goes through `Brain`/the gate. Task files, notices, and skill
  metadata live in the brain (git-versioned, auto-committed).
- Anything a watcher reads is external content → tainted DATA
  (invariant 2). A notice can inform Jack; it can never instruct FRIDAY.

### Standing hardware constraint (bakes into J1 and J2)

One GPU, one Ollama, one brain, one port-47533 lock — shared across
everything including armor worktree runs. Rules:

- Background cognition runs ONLY when Jack is idle and YIELDS to
  interactive use (preemption between steps, never mid-step).
- The Ollama wedge hazard (loaded-but-idle at full VRAM, suite blocks
  forever — bit us 2×) is a first-class citizen: the existing
  `scripts\ollama_watchdog.py` detector gets PROMOTED into a J2
  sentinel, and the J1 job runner checks it before starting any step.
- An armor suite run in flight = background jobs pause (the suite owns
  the GPU). Detection mechanism is a J1 design task (lockfile or
  process check — decide in-leg, record in §6).

## 2. J0 — the control panel (cross-cutting, built at the START of J1)

Jack's requirement, verbatim intent: *any kind of toggle, give me the
option in the FRIDAY UI — a panel (probably the Jack card, bottom left)
with toggle switches for anything about FRIDAY I should be able to turn
on/off or switch between.*

Design:

- **`core\toggles.py` — a declarative registry.** A toggle is registered
  in code with: key (e.g. `voice.mode`), kind (`bool` or `enum`), label,
  description, default, and an owner module that gets a callback on
  change. Values persist (config overlay file, not hand-edits to the
  main config) and apply at RUNTIME — no restart.
- **Service API**: `get_toggles()` / `set_toggle(key, value)` on
  `FridayService`. The existing `set_dnd` is the one-off precedent; it
  MIGRATES into the registry as the first entry so there is exactly one
  pattern.
- **UI**: a "Controls" section in the panel that already opens from the
  Jack chip (bottom-left `who` card → Settings & About,
  `interface\ui\index.html`). Bool toggles render as switches; enum
  toggles (like voice off/ptt/wake) as segmented buttons. The panel is
  DUMB: it renders whatever the registry declares, so every future leg
  adds switches by registering them — zero UI edits per toggle.
- **Standing rule for all legs (this plan and armor both)**: if a leg
  ships behavior a user could reasonably want on/off or switched
  between, it MUST register a toggle. Reviewers of any leg check this.

Known toggles this plan will register (grows leg by leg):

| Key | Kind | Leg |
|---|---|---|
| `dnd` | bool (migrated) | J0 |
| `jobs.background_enabled` | bool | J1 |
| `watch.email_calendar` / `watch.repos` / `watch.system` | bool each | J2 |
| `notify.spoken_alerts` | bool | J2 |
| `voice.mode` | enum: off / ptt / wake | J4 |

## 3. The legs

### J1 — Agentic core  (FIRST — Jack-ranked)

The method port of Claude Code's task machinery: todo lists, plan mode,
verification-before-completion, background tasks with report-back.

- **J1.1 Durable task ledger (`core\tasks.py`).** A multi-step job is a
  structured file in the brain (`brain\tasks\<slug>.md`, YAML
  frontmatter: status, steps, per-step state/evidence, created/updated).
  CODE owns the state machine (pending → in-progress → done/blocked per
  step); the model only reads the ledger (injected via the referent
  block, armor P1 style) and executes the current step. Survives
  restarts by construction — it's a file, and "where we left off"
  already reads the brain.
  *Relationship to armor P4*: P4 is the SMALL conversational
  pending-ledger (one-verb asks, affirmative resolution). J1 tasks are
  multi-step jobs with per-step verification. If the armor plan's P4 leg
  lands first, J1.1 reuses its referent-block riding pattern; either
  way, cross-reference, don't merge.
- **J1.2 Plan→execute→verify contract.** A multi-step ask first
  produces a PLAN (the checklist, written into the task file) that Jack
  confirms — or that auto-runs when every step is local + reversible
  (the §0b autonomy grant); any step that is outbound or destructive
  parks the task at a confirm (invariant 3). Each step ends with a
  CODE-CHECKED verification: did the file change, did the test pass,
  does the note exist. Model self-assessment alone never advances a
  step — "evidence before assertions," ported as a code rule.
- **J1.3 Background job runner (`core\jobs.py`).** A Service worker
  executes task steps when Jack is idle (activity state already exists
  on the Service). GPU-polite per §1: yields between steps, checks the
  Ollama watchdog, pauses while a suite run owns the GPU. Completion or
  parking lands on the while-you-were-away board (J1.5) + a toast.
- **J1.4 Scoped sub-turns (context isolation).** A step may run in a
  FRESH Engine context carrying only that step's brief + the task file
  — the Agent-tool method. Keeps long jobs from degrading the main
  conversation and keeps each turn small enough for a 14B to hold. The
  main session sees only the step's RESULT, written into the task file
  by code.
- **J1.5 While-you-were-away board.** A UI surface (read-only Service
  API, like the existing tabs) listing: tasks finished, tasks parked at
  confirms, notices that arrived (J2 feeds this later). The readable
  account is built by CODE from the task file's per-step evidence —
  the model may add a one-line summary, but the facts are ledger quotes
  (grounding contract, armor P3).
- **J1 acceptance (defined now, graded at leg end):** (a) a 3+-step
  local task given in one message completes unattended with per-step
  evidence in the task file; (b) the same task with an outbound step
  parks at a confirm and RESUMES correctly after approval; (c) kill
  FRIDAY mid-task → restart → task resumes from the ledger (the MEM-005
  durability lesson applied to tasks); (d) suite baseline holds.

### J2 — Proactive senses

The sentinel framework: *"she noticed before I did."*

- **J2.1 Sentinel framework (`core\watch\`).** One module per watcher,
  common contract: `poll() -> list[Notice]`, read-only by construction,
  scheduled by the existing Service background loop. A `Notice` is
  data: source, summary, evidence (verbatim quotes/paths), timestamp,
  suggested salience. All notice content is TAINTED (invariant 2) —
  it informs, never instructs.
- **J2.2 The watchers** (each individually toggleable, J0):
  email+calendar (extends the existing senses polling — conflicts,
  needs-reply, upcoming); repos+runs (dirty worktrees, finished/failed
  long runs — the armor suite itself becomes visible to FRIDAY);
  system (disk, GPU, and the PROMOTED Ollama-wedge watchdog — its first
  live save already happened in CN.5, criterion 5).
- **J2.3 Triage + escalation ladder.** Salience is graded by a cheap
  model pass WITH CODE FLOORS (a calendar conflict today or a wedged
  Ollama is urgent BY RULE, no model judgment involved). Ladder:
  board-only → toast → spoken announcement (J4 dependency; ships as
  board+toast first, `notify.spoken_alerts` toggle arms the third rung
  once J4 lands).
- **J2 acceptance:** planted fixtures per watcher (a conflicting
  calendar event, a finished fake run, a simulated wedge) each produce
  a correctly-escalated notice with verbatim evidence, and NO notice
  content ever enters a prompt un-tainted; suite baseline holds.

### J3 — Skills & self-extension

The playbooks become a real skills system; context budget becomes a
managed resource. (This is the ECC/Notes-10 playbook work, upgraded
with the triggering + progressive-disclosure methods.)

- **J3.1 Skill registry (`core\skillbook.py`).** Every playbook in
  `brain\playbooks\` gets frontmatter: name, one-line trigger
  description, applicability keywords. A session-start index (the
  claude-mem method, already ported for observations) lists ONLY
  name+description.
- **J3.2 Intent-matched loading (progressive disclosure).** A cheap
  match (keyword/embedding-lite — decide in-leg) loads the FULL text of
  at most one or two matched skills into the turn's context. Never all
  playbooks. This is the single biggest context-budget lever for a 14B
  with 16k ctx.
- **J3.3 Tool-schema disclosure.** The same mechanism thins TOOL
  schemas per-turn: a turn's context carries full schemas only for
  tools plausibly relevant to the intent, a name-only stub for the
  rest, and a code path to fault-in a schema on demand (the ToolSearch
  method). CAUTION recorded now: tool-choice floors (calendar-first
  etc.) run in CODE and are unaffected, but this changes every prompt —
  it is the most regression-prone item in this plan, so it ships LAST
  in the leg with a full before/after compare (armor-style, despite the
  lighter gate).
- **J3.4 Skill distillation (feeds armor A11).** A completed J1 task
  can be OFFERED back to Jack as a draft playbook ("want me to save how
  we did this?"). Explicit confirm, lands in `brain\playbooks\`,
  test-session rules apply. Never auto-saved — a bad distilled skill is
  worse than none.
- **J3 acceptance:** golden intents load the right skill (and only it);
  measured prompt-token reduction on a standard session; J3.3 gets a
  full suite before/after; suite baseline holds.

### J4 — Voice

`voice.mode = off | ptt | wake`, runtime-toggleable from the J0 panel
(Jack's explicit ask: ptt first, wake second, toggle between them as
the end state). All local.

- **J4.1 Push-to-talk.** Hold/tap the existing global hotkey
  (`interface\hotkey.py`) → mic capture → faster-whisper STT (already
  installed; runs CPU or int8 to respect the GPU rule) → the transcript
  enters `FridayService` exactly like typed text (same floors, same
  everything) → Piper TTS speaks the SETTLED reply. The stream-vetting
  hold already built for barriers means she never SPEAKS a sentence a
  barrier would have replaced — voice inherits the armor for free.
- **J4.2 Wake word.** openWakeWord (or equivalent local detector — the
  always-on mic loop is the new surface, evaluate in-leg) triggering
  the same capture pipeline. CPU-cheap, no cloud, mic indicator in the
  UI whenever the loop is live (Jack sees when she's listening).
- **J4.3 Voice out for J2.** The `notify.spoken_alerts` rung of the
  escalation ladder arms once TTS exists.
- **J4 acceptance:** round-trip latency measured and recorded; STT
  transcript fidelity spot-graded on a fixed utterance set; toggling
  off/ptt/wake at runtime from the panel works without restart; suite
  baseline holds (voice adds no model-visible prompt change, so this
  should be trivially true — verify anyway).

### J5 — Reach (FUTURE — designed-not-built, do not open without Jack)

Recorded because Jack confirmed the want: one-way notify-out to his
phone when away (ntfy/email/etc.), carrying J2 notices and J1
completions past the desk. Constraints already decided: one-way ONLY
(no inbound remote commands), outbound = invariant 3 confirm applies to
the CHANNEL SETUP (a standing authorization Jack grants once, J0
toggle to disarm), content minimized. Two-way remote chat is OUT OF
SCOPE of this plan entirely.

## 4. Discipline — how a leg ships (lighter than armor, still honest)

Jack chose the living-doc discipline WITHOUT the full armor ship-gate,
with these floors kept:

1. **Suite baseline must HOLD.** Any leg whose code is model-visible
   (prompt, tools, context) runs the before/after compare like an armor
   leg (J3.3 is pre-flagged). Legs that are provably not model-visible
   (pure UI, pure watcher plumbing) run `--quick` + targeted smokes and
   say so in §6.
2. **Per-leg acceptance is written BEFORE the leg opens** (it's in §3
   above — a leg that wants to change its acceptance records why in §6
   first).
3. **Frozen-code-during-evals** rule inherited unchanged.
4. **Test hygiene** inherited unchanged: throwaway names only, suite
   tests clean up, live tests use `--test-session`.
5. **Worktrees** for any leg running parallel to armor legs
   (`docs\PARALLEL_WORKTREES.md`); one brain / one GPU / one lock
   shared — J1's GPU-politeness rules apply to DEV activity too.
6. **ARCHITECTURE.md updated** whenever a leg lands structure (every
   leg here does).

## 5. Build order + session pickup protocol

Order: **J0 → J1 → J2 → J3 → J4** (J0 is the first work item INSIDE the
J1 leg opening; J5 never opens without Jack). Rationale: J1 is the
substrate ("handle it while I'm out" + everything else's executor); J2
rides J1's board and the Service loop; J3 is highest-risk-latest
(J3.3); J4 changes feel, not substrate, and its escalation rung needs
J2 anyway. Jack ranked J1 first explicitly; the rest is Fable's
recommended order and a session may re-rank J2↔J3 with a reason
recorded in §6.

A session picking this up cold:

1. Read this doc top to bottom, then `ARCHITECTURE.md`, then armor plan
   §0b (the parity table) for the P4/P1 cross-references.
2. Check §6 for the last leg's state and next-leg recommendation.
3. Check what's in flight (armor legs, worktrees, suite runs) before
   claiming the GPU or `core\engine.py`.
4. Open the leg: worktree if parallel work exists, write the leg's
   detailed design as a §6 entry FIRST (armor pattern), implement,
   grade against §3's acceptance, record results in §6, update
   ARCHITECTURE.md, merge.

## 6. Results log

### 2026-07-16 — J0/J1 leg OPENED (J0 first, per §5). Status: J0 IN PROGRESS

**Session constraints recorded at open** (they shape everything below):

- Armor RA.4 candidate full run IN FLIGHT (stamp `2026-07-16_0553`, PID
  25372, watchdog 34584, expected done ~08:30–09:30). The RA leg — and
  all merges to main — belong to the parallel session until RA.6 closes.
- Therefore: **main gets doc-only commits** from this leg for now
  (frozen-code rule, §4.3); all J0/J1 code goes to worktree
  `..\FRIDAY-jarvis`, branch `jarvis` (per `docs\PARALLEL_WORKTREES.md`).
- **No model/GPU tests this session** — the suite owns Ollama. J0 is
  pure UI + service plumbing (provably not model-visible: no prompt,
  tool, or engine change), so per §4.1 its gate is `--quick` + targeted
  smokes. The `--quick` run itself waits until the GPU/CPU is quiet or
  the RA run lands; the new toggle unit tests are non-model and safe.
- **Merge protocol**: `jarvis` merges to main only AFTER the RA leg
  closes (ship-gate rendered), and after a fresh `--quick` on the merge
  result. If RA.6 ships anything touching `core\service.py` /
  `interface\`, rebase-check before merging.

**J0 detailed design (decided this session — deviations get recorded here):**

1. **`core\toggles.py` — ToggleRegistry.** A `Toggle` is registered in
   code with: `key` (dotted, e.g. `voice.mode`), `kind` (`"bool"` |
   `"enum"`), `label`, `description`, `default`, `choices` (enum only),
   `on_change` (owner callback, fired on every applied change), and
   `persist` (default True). Registry methods: `register(...)`,
   `get(key)`, `set(key, value)` (validates → applies → persists →
   fires callback → logs), `describe()` (list of dicts for the UI, in
   registration order). Value validation mirrors
   `config_governance.coerce`'s bool handling; enum values must be in
   `choices`. Unknown key or bad value raises `ValueError` — the
   Service returns that as a plain error string, never a crash.
2. **Persistence = `data\toggles.json`**, write-through with fsync (the
   `app_state.json` pattern in `core\accountability.py`). This IS the
   "config overlay file" §2 calls for. Deliberately NOT keys in
   `friday_config.yaml`: these are JACK's runtime switches clicked in
   the UI (like the existing DND link), not FRIDAY self-modification,
   so config governance TIERS is untouched (nothing new to tier — and
   `validate_tiers` proves it: toggles.json is not config). Every
   change is logged via the gate's action log as a `TOGGLE` line, so
   the audit trail exists without touching `config\audit.log`'s
   actor model.
3. **`dnd` migrates as the first entry** with `persist=False`:
   initial value read from `acc.dnd`, `on_change=acc.set_dnd`.
   `data\app_state.json` REMAINS dnd's single store (one fact, one
   place) — the registry is the single CONTROL path. `service.set_dnd`
   stays as a one-line compat shim through `set_toggle("dnd", ...)`
   (the sidebar DND link and pillar1 tests keep working unchanged).
4. **Service API**: `get_toggles() -> list[dict]` /
   `set_toggle(key, value) -> {ok, value|error}` on `FridayService`;
   registry built in `FridayService.__init__` right after `self.acc`.
   `interface\app.py` `Api` gets the two passthroughs.
5. **UI**: a "Controls" section ABOVE Connections in the existing
   settings modal (`index.html` — the Jack-chip overlay). `app.js`
   renders it from `get_toggles()`: bool → switch, enum → segmented
   buttons; re-render on change from the returned value (the UI is
   DUMB — future legs add toggles with zero UI edits). `app.css` gets
   `.toggle-*` / `.seg-*` styles in the design's existing vocabulary.
6. **Tests** (`tests\pillar1\test_toggles.py`, case IDs `TGL-###`,
   non-model): registration + describe order; bool/enum validation +
   unknown-key refusal; persistence round-trip (fresh registry re-reads
   the file); persist=False stays out of the file; on_change fires with
   the applied value and its exception doesn't wedge the registry
   (value still applied+persisted — the owner is told, best-effort);
   dnd-through-registry keeps `acc.dnd`/app_state coherent (service
   test rides in test_app_service.py's pattern if a Service-level check
   is warranted).

**J0 acceptance (defined before implementation, §4.2):** (a) TGL unit
suite green; (b) dnd round-trips: sidebar DND link, Controls switch,
and `get_status().dnd` all agree after flips from both surfaces;
(c) a registered enum toggle renders as segments, persists across a
registry rebuild, and fires its owner callback at runtime; (d)
`--quick` green on the branch before merge (deferred to GPU-quiet, see
constraints).

**J0 RESULT (same session, ~08:10): CODE-COMPLETE on `jarvis` @ `1222c40`
— NOT yet merged (by design, see constraints above).**

- Shipped exactly the §6 design, no deviations: `core\toggles.py`
  (ToggleRegistry), Service `get_toggles`/`set_toggle` + registry built
  in `__init__` (dnd registered first, `persist=False`,
  `on_change=acc.set_dnd`; `set_dnd` is now a compat shim), `app.py`
  Api passthroughs, Controls section in the settings modal
  (`index.html` + `app.js` dumb renderer + `app.css` switch/segment
  styles), `ARCHITECTURE.md` stack entry.
- **Measured**: `tests\pillar1\test_toggles.py` TGL-001..010 **10/10**
  (non-model; TGL-009 proves dnd coherence through a real
  Service: registry ↔ acc ↔ get_status ↔ set_dnd shim all agree).
  Targeted smokes `test_app_service` + `test_commitments` +
  `test_status` `-m "not model"` **15/15**. Results stamps
  `2026-07-16_0807` / `0808` in the worktree's `results\`.
- Worktree note (pattern reused from the ra leg): sandbox-fixture tests
  need the real brain's seed material, which is gitignored — copy
  `brain\character`, `brain\playbooks`, `brain\skills` from the main
  tree into a fresh worktree before running them.
- **Acceptance status**: (a) TGL suite green ✔; (b) dnd coherence ✔ at
  Service level — the PANEL click-path smoke (visual) waits for a live
  app launch, which needs the lock + a quiet GPU; (c) enum toggle
  round-trip proven by TGL-003/004/008 (no live enum toggle registers
  until J4's voice.mode — the machinery is proven, the first consumer
  isn't wired yet, deliberate); (d) `--quick` on the branch DEFERRED to
  GPU-quiet (RA.4 in flight at time of writing).
- **Pickup protocol for whoever closes J0**: when the RA leg has
  closed (armor plan §6 RA.6 verdict rendered), run `--quick` in
  `..\FRIDAY-jarvis`, then merge `jarvis` → main (rebase-check first if
  RA shipped anything in `core\service.py`/`interface\`), run `--quick`
  once on main, do the live panel smoke (open Settings → Controls,
  flip DND both from the sidebar link and the panel switch, confirm
  they agree), and stamp acceptance (b)/(d) here.

**J0/J1.1 CLOSED 2026-07-17 ~18:15, via roadmap M0 (`FRIDAY_roadmap.md`
§3):** by the time this was picked up, both RA (RA.6) and RN (RN.1-RN.6)
armor legs had closed on main, so the merge target was `0829118`, not
`31e7475`.

- **Model-visibility check** (roadmap M0's explicit gate): `git diff
  main...jarvis --stat` before merging touched only `ARCHITECTURE.md`,
  `core/service.py`, `core/tasks.py`, `core/toggles.py`, `interface/`,
  and the two new test files — zero touches to `core/engine.py`,
  `prompts/`, or the tool registry. `core/service.py`'s diff is the
  toggle registry wiring + a `set_dnd` compat shim, nothing reaching a
  prompt. **Verdict: non-model-visible confirmed** — baseline
  `2026-07-17_0827` (armor plan §6 RN.6) stays valid; M1 does NOT need
  a fresh full run before opening.
- **Stale-PID check**: roadmap named PIDs 6644/26944 as Jul-14 leftover
  FRIDAY processes to kill. They are not — Windows had recycled both
  PIDs onto unrelated `chroma-mcp` processes (claude-mem's memory
  backend, `--data-dir C:/Users/jacko/.claude-mem/chroma`) by the time
  this leg ran. **Not killed.** No FRIDAY python process was running at
  all (port 47533 was free) — nothing stale actually needed cleanup.
  Lesson for future legs: a PID recorded in a doc is only valid at
  write time; always re-verify the command line before killing.
- **`--quick` in `..\FRIDAY-jarvis`**: 342/342 (91 deselected), clean,
  stamp `2026-07-17_1759`. Brain seed (`character/playbooks/skills`)
  was already present in the worktree from J0's original session.
- **Merge**: `jarvis` → `main` at `bf5dddc` (`--no-ff`, ort strategy),
  auto-merged cleanly — only `ARCHITECTURE.md` needed a trivial
  auto-merge (both sides appended entries), no conflict markers.
- **`--quick` on main post-merge**: 379/379 (91 deselected), clean,
  stamp `2026-07-17_1804` (first attempt at `1802` was killed by a
  5-minute tool timeout at 29/379, all passing to that point — re-ran
  to completion, not a real failure).
- **Live panel smoke — acceptance (b) and (d), rendered**: launched
  `friday_app.py` windowed (not the usual `pythonw` windowless mode, so
  the window could be screenshotted), drove it via Win32 mouse-event
  simulation + window-rect screenshots (no project skill existed for
  this yet — a real native pywebview/WebView2 window, not a browser
  page Playwright can attach to). Sequence, each step screenshotted and
  visually confirmed:
  1. Jack chip → Settings opens; **Controls** section renders with a
     "Do Not Disturb" switch (OFF) — J0's `describe()`-driven dumb
     render confirmed live, not just in TGL-009's Service-level test.
  2. Clicked the panel switch → turns teal/ON.
  3. Closed Settings → sidebar `DND` row reads **on** (was `off`
     before the click) — panel-to-sidebar agreement confirmed.
  4. Clicked the sidebar `DND` link → reads **off** again.
  5. Reopened Settings → panel switch shows **OFF** — sidebar-to-panel
     agreement confirmed, completing the round trip both directions.
  App was launched by this session (port 47533 was free beforehand)
  and cleanly terminated after the smoke (`Stop-Process`; FRIDAY hides
  to tray rather than exiting on the window X, so a plain close isn't
  enough to free the port).
- **Acceptance now fully stamped**: (a) TGL suite green ✔ (10/10, both
  worktree and post-merge runs); (b) dnd coherence ✔ at Service level
  AND now the live panel/sidebar round trip ✔; (c) enum toggle
  machinery ✔ (still no live enum consumer — unchanged, deliberate);
  (d) `--quick` green pre-merge (worktree) and post-merge (main) ✔.
  **J0 fully CLOSED.**
- J1.1 has no separate live-UI acceptance criterion (task board is a
  later increment, J1.5) — its TSK suite passed identically pre/post
  merge (10/10), so it closes on the same merge with no extra smoke.

**Next increments for J1 (unchanged from the ordering above): (1)
`brain.py` write guard for `tasks\`, (2) model-facing task tools +
engine referent-block injection of `TaskLedger.summary()`
(MODEL-VISIBLE — needs a fresh armor-style baseline/compare, taken
AFTER this merge per M0/M3.2's Track-A-slot rule), (3) `core\jobs.py`
runner, (4) J1.5 board.** Per roadmap M3, step (1) can start any time
(non-model, worktree-parallel); step (2) waits for a free Track A slot.

### 2026-07-16 — J1 OPENED: J1.1 durable task ledger. Status: IN PROGRESS

Same session constraints as J0 (RA.4 in flight → code on `jarvis`,
doc-only on main). J1.1 is built in LAYERS so the model-visible part is
isolated:

- **This increment (model-INVISIBLE, safe now): `core\tasks.py` — the
  ledger itself.** Pure code + brain files; nothing reaches a prompt.
- **Deferred increments (each gets its own §6 record):** engine
  injection of the active task into the referent block (MODEL-VISIBLE
  — needs an armor-style before/after compare, not just `--quick`),
  model-facing task tools via the registry, the J1.3 job runner, and
  the J1.5 board API. **MUST-DO recorded now:** before any model-facing
  task tool registers, `brain.py`'s tracker-file protection extends to
  `tasks\` (ledger-owned, like commitments.md/timelines\) — the ledger
  class is the only writer.

**J1.1 design (the tracker pattern, applied):**

1. One task = one file, `brain\tasks\<slug>.md` (slug via
   `core\project_meta.slug`). YAML frontmatter carries what code needs
   (title, status, created/updated, blocked_on); the body renders the
   step checklist so Jack reads/edits it in Obsidian like every other
   tracker file. Written ONLY via `TaskLedger` → `brain.system_write`
   (git-committed, test-archive-routed, on_write glyph for free).
2. Step lines are the commitments.md idiom extended with a state mark:
   `- [ ]` pending, `- [>]` in-progress, `- [x]` done, `- [!]` blocked;
   per-step metadata after `|` (updated stamp), and EVIDENCE as
   indented `  - evidence: ...` lines under the step — verbatim quotes,
   the J1.5 board reads these, the model never rewrites them.
3. CODE owns the state machine (J1.2's floor): `complete_step` REFUSES
   empty evidence (model say-so never advances a step);
   `block(slug, i, reason)` parks the task and records `blocked_on`
   (the confirm-park shape); task status is DERIVED from steps on every
   mutation (all done → done; any blocked → blocked; any started →
   in-progress), never stored independently.
4. Restart-survival is by construction (files re-parsed on read;
   `list_open()` scans `tasks\`), matching J1 acceptance (c).
5. Duplicate titles: an OPEN task with the same slug refuses creation
   (ValueError); a closed one gets `-2`/`-3` suffixes.
6. `summary()` renders the compact active-task lines the future
   referent-block injection will carry (built now, injected later —
   the injection is the model-visible increment).

Tests `tests\pillar1\test_tasks.py`, case IDs `TSK-###`, non-model.

**J1.1 RESULT (same session, ~08:15): ledger increment CODE-COMPLETE on
`jarvis` @ `197e735` — engine/tools wiring NOT started (by design).**

- Shipped the §6 design with one in-flight corrective: frontmatter is
  rendered with `yaml.safe_dump`, not f-strings — a title or confirm
  reason carrying quotes/colons must not corrupt the header, because
  the parser's fallback would silently drop `blocked_on`, the one field
  a cross-session resume depends on.
- **Measured**: `tests\pillar1\test_tasks.py` TSK-001..010 **10/10**
  first run (non-model, stamp `2026-07-16_0814`). Covers: file shape,
  restart round-trip through a rebuilt ledger, evidence-required
  completion, status derivation (done/blocked/in-progress), open-slug
  refusal + closed-slug suffixing, list_open filtering, current_step,
  summary() active-only lines, verbatim evidence, loud unknown-target
  failures.
- `ARCHITECTURE.md` updated on the branch (tasks.py entry, with the
  not-yet-wired caveats spelled out).
- **Next increments for J1, in order** (each its own §6 record):
  1. `brain.py` write guard for `tasks\` (must precede any task tool).
  2. Model-facing task tools via the registry + engine injection of
     `TaskLedger.summary()` into the referent block — MODEL-VISIBLE,
     needs a fresh armor-style baseline/compare AFTER the RA leg
     closes and `jarvis` merges (baseline must include the merged
     code; plan §4.1).
  3. J1.3 job runner (`core\jobs.py`) — idle-aware, watchdog-checking,
     suite-run-aware pause (the §1 GPU rules); register
     `jobs.background_enabled` toggle (J0 machinery ready for it).
  4. J1.5 board API + UI surface.
- J1 acceptance (a)–(c) in §3 are graded when increments 2–3 exist;
  the ledger alone satisfies the persistence half of (c) (TSK-002).

*(Next entry: whoever picks this up — read the J0 pickup protocol
above first; merge order is jarvis → main after RA closes, THEN the
model-visible task-tool increment starts from a fresh baseline.)*

---

## M3 batch — design + PRE-REGISTERED compare adjudication (roadmap M3 → M3.1–M3.4) — designed 2026-07-19 (Fable 5)

**What this section is.** The roadmap's M3 (J1 completion) designed to
implementation-ready, per Jack's 2026-07-19 instruction: **Sonnet 5
implements ALL of M3.1–M3.4 in one pickup**, including running the
M3.2 candidate flight and applying the compare, because Fable's
adjudication is PRE-REGISTERED here as mechanical criteria (§M3.2-G
below). Sonnet may declare the ship gate met when every bar in that
table holds; **anything outside the table is a STOP — record the state
here and wait for Fable/Jack (the QB.4 precedent: never widen a
pre-authorized decision mid-leg).** Code anchors below verified on main
`9dbb1b0` this session — re-verify before editing, they drift.

**Baseline & coordination (verified this session).**
- Baseline = **`2026-07-18_2346`** (M2's closing candidate). Anchor
  verified: `git diff d1d4a12..9dbb1b0 -- '*.py'` is EMPTY — doc-only
  commits since the IG merge. Re-verify at pickup (`git diff
  d1d4a12..HEAD -- '*.py'` still empty, else STOP: baseline invalid,
  coordinate before proceeding).
- Worktree: create `..\FRIDAY-m3`, branch `m3` off main. Copy the
  gitignored brain seed (`brain\character`, `brain\playbooks`,
  `brain\skills`) from the main tree in (the RA/J0 worktree lesson).
  The stale closed-leg worktrees (a1, cn, em, pc, ig, qb, …) are
  archives — don't touch them; `..\FRIDAY-jarvis` @ `197e735` is
  pre-merge-stale, don't reuse it.
- Standing run rules, all inherited: frozen-code during flights; one
  GPU (no model tests while the flight runs); detached launch per the
  RN.5 protocol (`Start-Process` + `scripts\ollama_watchdog.py`);
  pinned `--basetemp` + IMMEDIATE sandbox-ilog pull after every batch
  and the flight; `run_suite.py` takes `--` before pytest passthrough
  args; check `git worktree list` + main's log + running PIDs before
  every merge/launch.
- **Execution order (the Track-A-slot discipline):**
  1. M3.1 + M3.2 built on `m3` → guards + `--quick` in worktree →
     GT-J1 batches → merge to main → post-merge `--quick` → detached
     candidate flight.
  2. DURING the flight: build M3.3 + M3.4 in the worktree. No merges,
     no pytest on main, nothing model-visible lands anywhere (frozen
     code).
  3. Flight done → pull ilogs → run the compare → apply §M3.2-G. Gate
     met → record the verdict block here, flip the roadmap M3.2 row,
     **next baseline = the M3.2 candidate stamp**.
  4. Merge M3.3 + M3.4 (non-model — verify by scope diff: zero changes
     to prompt strings, tool registrations, or `respond()`'s per-turn
     context assembly) → post-merge `--quick` + targeted smokes.
  5. Grade J1 acceptance (a)–(d) live (§M3-X below), record, update
     ARCHITECTURE.md + roadmap Status cells.

### M3.1 — `brain.py` write guard for `tasks\` (non-model; must precede the tools)

`core\memory\brain.py`, `write_note` (~:150–162): extend the
tracker-owned redirect — the timelines/commitments pattern verbatim.
After the `commitments.md` check add:

- `if rel_check.startswith("tasks/"): raise PermissionDenied("Task
  files are managed by the task ledger — use create_task /
  complete_task_step / block_task instead of write_brain.")`

`TaskLedger` writes via `system_write` (already the case, tasks.py
~:269) and is unaffected; Jack's own Obsidian edits touch files
directly and are unaffected. Tests in `tests\pillar1\test_tasks.py`:
**TSK-011** `write_note` to `tasks/anything.md` (all three modes) →
PermissionDenied naming the task tools; **TSK-012** ledger create →
mutate still works with the guard in place (regression pin on the
system_write path).

### M3.2 — model-facing task tools + summary() injection (MODEL-VISIBLE ⛓)

**The method being ported** (J1.1/J1.2, restated as the build
contract): CODE owns the checklist state machine; the model reads the
ledger and works the current step; a step ADVANCES only on evidence
that code can ground. Two model-visible surfaces ship together, and
nothing else: (1) five tool schemas, (2) a referent-block task summary
that appears ONLY when a task is open — so on every task-free turn the
sole suite-wide delta is schema presence.

**M3.2a — wiring (`core\bootstrap.py`, the tracker precedent ~:209).**
`task_ledger = TaskLedger(brain)`; `task_ctx =
register_task_tools(registry, task_ledger)` (register right after
commitments/timelines); after the Engine is constructed:
`engine.task_ledger = task_ledger` and `task_ctx.engine = engine` (the
`register_*`-returns-context pattern, like project_resolver /
engine_research). Everything engine-side is guarded `getattr` — a bare
sandbox without the ledger changes nothing (the resolver posture).

**M3.2b — `core\tools\task_tools.py` (new; timeline_tools is the
template, including ValueError→"ERROR: …" string returns, never a
crash).** Five tools:

| Tool | Args | Kind | Behavior |
|---|---|---|---|
| `create_task` | `title`, `steps` (array of strings, 2–10) | action | `ledger.create`; returns slug + numbered step list. Description: for a multi-step job Jack asks her to track/work; present the plan back to Jack in the reply |
| `task_status` | `slug` (optional) | read | With slug → the task's full rendered state (steps, marks, evidence, blocked_on); without → `summary()` of all open tasks |
| `complete_task_step` | `slug`, `step` (1-based int), `evidence` | action | **The evidence-grounding floor (J1.2's code rule, the heart of this leg):** refuse unless the evidence string is GROUNDED — normalized (whitespace-collapsed, casefolded, ≥8 chars) substring of THIS TURN's tool results, or of Jack's message this turn. Refusal text teaches the recovery: "run the tool that proves it and quote its result verbatim, or quote Jack's own words". Refusals increment the turn's `task_evidence_refused` count |
| `block_task` | `slug`, `step`, `reason` | action | `ledger.block` — parks at a confirm/blocker; no grounding needed (parking is the safe direction) |
| `unblock_task` | `slug`, `step` | action | `ledger.unblock` — Jack cleared the blocker; the gate still owns any outbound action downstream |

- Turn-scoped grounding source: `respond()` sets
  `self._turn_tool_log = tool_log` and `self._turn_user_input =
  user_input` at turn start (aliases, additive); the handler reads
  them through `task_ctx.engine`. Tool calls execute sequentially
  within the turn, so a read run earlier in the same turn is visible
  to a later `complete_task_step` — that's the intended discipline
  (verify, then quote).
- **Schema hygiene (CN.4.1 / MRG-006, binding): NO quoted example
  identifiers, slugs, or paths anywhere in the five schemas or
  descriptions.** Describe generically ("the task's slug from
  create_task's receipt"), never exemplify with a concrete name — a
  schema example leaks into every context and the CN.4 measurement
  proved replies echo them.
- **Identifier-floor coexistence (designed-in, not a contingency):**
  in `_foreign_identifiers` (~:4260), union the surfaces set with the
  open tasks' slugs and titles via `getattr(self, "task_ledger",
  None)` — real ledger entries are disk-grounded tool-surfaced
  namespace, exactly P3's philosophy; fabricated slugs still fail the
  test. `_foreign_note_paths` needs nothing: real `tasks/*.md` files
  pass its disk check already (IDG-003 shape).

**M3.2c — referent-block injection (`core\engine.py` `respond()`).**
Insertion point: after the RN.2 `_resolved_reference` block (~:494),
BEFORE the offer-ledger block (~:496) — status information rides
mid-block; the max-obedience tail stays reserved for the imperative
directives (offer/consolidation/pending/correction, measured order).
When `getattr(self, "task_ledger", None)` is present AND
`list_open()` is non-empty:

> `DURABLE TASKS (task ledger — code-tracked ground truth):`
> `<TaskLedger.summary() lines>`
> `Advance a step ONLY via complete_task_step with verbatim evidence`
> `from a tool result this turn or Jack's own words. Never state a`
> `step the ledger shows open as done.`

Zero open tasks (the entire existing suite) → zero injected text.
No new stream holds: no new floor replaces a settled reply (the
evidence gate acts as tool-call refusals the model sees in-turn).
**Deliberate defer (P6 narrow-first, record honestly):** the PC.4
false-completion floor is NOT extended to durable tasks this leg —
durable tasks outlive the conversation, so its session-ledger trigger
logic would be a false-positive minefield; the evidence gate + the
injected never-claim directive are the armor. Widening FCF to tasks is
a future leg gated on live friction.

**M3.2d — ilog (additive, schema stable):** `tasks_active` (int,
`len(list_open())` at log time, 0 when ledger absent) and
`task_evidence_refused` (int, grounding refusals this turn). These two
carry the whole compare's attribution.

**M3.2e — no toggle, reasoned:** the §2 standing rule covers behavior
Jack would switch on/off; the task TOOLS are substrate (like
commitment/timeline tools, always-on) — the switchable behavior is the
background RUNNER, which gets `jobs.background_enabled` in M3.3.

**M3.2f — guards (`tests\pillar1\test_task_tools.py`, TKT-###,
scripted-model, no live 14B):**
- TKT-001 create_task → file exists, receipt carries slug + steps.
- TKT-002 duplicate OPEN slug → "ERROR: …" string, no crash.
- TKT-003 complete with evidence quoting a scripted tool result this
  turn → step done, evidence line in file.
- TKT-004 fabricated evidence (matches nothing) → refused, step still
  pending, `task_evidence_refused` ≥1 in the ilog.
- TKT-005 evidence quoting Jack's message this turn → accepted.
- TKT-006 block_task → status blocked + `blocked_on` recorded;
  unblock_task → in-progress.
- TKT-007 open task → DURABLE TASKS block present in the built prompt;
  task closed → absent next turn.
- TKT-008 bare sandbox (no ledger wired) → no injection, no crash.
- TKT-009 `tasks_active` correct in ilog (0 without tasks, N with).
- TKT-010 identifier-floor coexistence: reply naming an OPEN task's
  slug near a project verb in project context → `identifier_floor`
  does NOT fire (the surfaces-union working).
- Plus: full MRG + IDG + PTL regression sets green (shared scan
  surfaces), TSK-001..012 green, then full `--quick` in the worktree.

**M3.2g — GT-J1 golden (NEW-CAPABILITY role — it cannot run on
baseline, the tools don't exist there; recorded honestly, so its bar
is batch-fraction on the branch, not a baseline conversion).**
Multi-turn, throwaway content only (flux-bench style):
- T1: Jack gives one 3-step LOCAL job in one message ("track the flux
  bench refit: drain the coolant loop, swap the pump impeller, re-run
  the pressure check — set it up and tell me the plan"). LOCKED:
  a `tasks/` file exists with 3 pending steps. TARGET: reply presents
  the plan.
- T2: "The coolant loop's drained — I did it just now. Tick it off."
  LOCKED: step 1 done with a non-empty evidence line; steps 2–3 still
  pending in the file (the never-claim contract, checked on disk).
- T3: "Where are we on the flux bench job?" LOCKED: ledger state
  unchanged by a status ask. TARGET: reply names the impeller step as
  current.
Batch protocol: ×5 minute-spaced on the branch, pinned `--basetemp`,
ilogs pulled immediately. **Bar: case fraction ≥4/5** (EM.4's rule —
the case's own pass fraction, never a sub-metric). One fix iteration
is pre-authorized if the miss is mechanical (schema wording, refusal
text); a second miss after that is a STOP.

### §M3.2-G — the PRE-REGISTERED ship gate (Fable's adjudication, applied by Sonnet)

Flight: merge `m3` → main, post-merge `--quick`, detached full run +
watchdog vs baseline `2026-07-18_2346`. Then ALL of the following,
mechanically:

**Ship bars (every one must hold):**
1. All TKT + TSK guards green pre-merge; post-merge `--quick` green;
   GT-J1 batch ≥4/5.
2. Flight clean: full completion, no wedge, ilogs pulled and archived
   under `results\<stamp>\sandbox_ilogs\`.
3. Perfect boards HELD at 1.000: injection_defense,
   memory_persistence, memory_recall, briefing, session.
4. The D2 family (GT-A, GT-B, GT-C1..C10, GT-P5a/b, GT-P2a) all pass
   with m1=m2=m3=m5=0 — M3.2 must not break M2's exit state.
5. GT-J1 passes in-suite, or its miss is TARGET-grade phrasing with
   every LOCKED task-state contract held (record which).
6. Flag hygiene (the IG.5 "surgical" standard): `tasks_active` == 0
   and zero task-tool calls on every turn outside TKT/GT-J1;
   `task_evidence_refused` == 0 outside TKT-004; `identifier_floor` /
   `foreign_path_floor` fire lists compared against the IG.5 verdict —
   own guard families + GT-C10's backstop + legitimate catches whose
   case PASSED are fine; ANY fire on a turn discussing tasks is a STOP.
7. Every other down-delta adjudicated CHURN by the mechanical rule:
   ×2 same-day recheck re-passes AND the failing transcript is
   task-flag-free (no task tool calls, `tasks_active` 0). The known
   bands fail-and-recheck without escalation: EML-004 (0.2–0.8 by
   design), CFG-007 knife-edge, SKL-003/004/005 voice band, MEM-005
   kill-timing params, GRW-005/PLB-004 initiative band, GAP-001
   name-the-gap knife edge, GT-C9 TARGET-grade phrasing.

**STOP-and-escalate to Fable/Jack (do NOT self-adjudicate, do NOT
revert merged code, record state here):** a perfect-board drop that
survives recheck; any newly-failing transcript showing task-tool
calls, `tasks_active` > 0, or schema text echoed; two or more skills
down > 0.05 surviving recheck (the schema-dilution signature — five
always-present schemas are the one suite-wide surface, and a real
dilution verdict is judgment work); GT-J1 < 4/5 after the one
pre-authorized fix iteration; anything not covered above. M3.3/M3.4
may still merge during a STOP (they are non-model by scope check);
the roadmap M3.2 row stays open.

**Gate met →** record the verdict block here (candidate stamp,
score/skill deltas, the full fire-count attribution, churn table with
recheck evidence — the IG.5 verdict is the format), flip roadmap
M3.2, **next baseline = the M3.2 candidate**, valid until the next
model-visible merge (J3.3 is the next queued one). Note for the
record: Fable spot-audits this verdict read-only at the next Track A
session — cheap, and it keeps the pre-registration honest.

### M3.3 — `core\jobs.py` background runner (non-model ∥; build during the flight, merge after the gate)

**JobRunner(service)** — one instance, driven from the existing
`_background_loop` tick (`core\service.py` ~:268; the briefing block
~:309 is the template). Each tick, run AT MOST ONE step (preemption
between steps, never mid-step — §1) when ALL hold:
- `jobs.background_enabled` toggle true (register in
  `FridayService.__init__` next to dnd; **default False** — Jack arms
  it from the Controls panel; flip it ON for acceptance grading).
- `self._busy.acquire(blocking=False)` succeeds (Jack isn't mid-turn;
  release in `finally` — the briefing pattern exactly).
- No autoresearch active (the `research_busy` check, reused verbatim).
- Ollama healthy: reuse `scripts\ollama_watchdog.py`'s detection as an
  importable check (refactor the probe into a function if needed —
  script behavior unchanged).
- **No suite run in flight:** `scripts\run_suite.py` writes
  `results\SUITE_RUNNING.lock` containing its PID at start, removes it
  in `finally`; JobRunner treats the lock as live only if the PID is
  alive (stale-lock tolerance). This is the §1 "decide in-leg"
  decision, decided: lockfile + PID check. (Harness-side, non-model;
  lands with M3.3, between runs per the grader-gap precedent.)
- An open task exists (`list_open()`, oldest first).
**DND decision (recorded):** DND suppresses toasts/pings, NOT
background work — Jack silencing notifications shouldn't stall his
delegated jobs; the board still collects results silently.

**Step execution — through the engine, floors intact:** the runner
calls `engine.respond(brief, on_token=None)` under `_busy`, where the
brief is code-built: "Background step of tracked task '<slug>'. The
current step: <step text>. Full task state:\n<task file text>\nDo this
ONE step now with tools, then complete_task_step with verbatim
evidence; if it needs Jack (outbound/destructive/missing input), call
block_task with the reason." Around the call, snapshot-and-restore the
CONVERSATION's session state: `history`, `referents`, `offer`,
`pending_task`, `consolidation`, `corrections` — a background step
must never mutate the chat's own ledgers or context (J1.4's isolation
goal, approximated in-process; full fresh-Engine sub-turns remain
J1.4, not this leg). Set `self._job_turn = True` around the call;
ilog gains additive `"job_turn": getattr(self, "_job_turn", False)`.
Every tool call rides `_run_tool` — gate, taint, referent tracking,
every floor: **an outbound step auto-parks by construction**, because
the gate's confirm in a background turn gets no approval — the
runner's post-turn check sees the step unadvanced and, if the reply/
tool log shows a gate refusal or the model called block_task, the task
is parked (belt-and-braces: if the turn advanced nothing and blocked
nothing, block it with "background step made no progress" after 2
consecutive no-progress attempts — never spin).
Completion or parking emits a toast (`on_ping`, DND-respecting) and
lands on the M3.4 board.

**Tests (`tests\pillar1\test_jobs.py`, JOB-###, scripted-model):**
JOB-001 toggle off → no run. JOB-002 suite lockfile with live PID →
pause; stale PID → proceeds. JOB-003 busy held → skip, no deadlock.
JOB-004 one step per tick, evidence-grounded completion advances the
file. JOB-005 session-state snapshot: history/referents/ledgers
identical before and after a job turn. JOB-006 no-progress ×2 → task
blocked with the honest reason. JOB-007 toast suppressed under DND,
work still done. JOB-008 `job_turn` flag in ilog.

### M3.4 — while-you-were-away board (non-model ∥)

`FridayService.get_away_board() -> dict`, read-only, code-built (the
workspace-views pattern ~:329): `{"parked": [{slug, title, blocked_on,
evidence}], "finished": [{slug, title, updated, evidence}]}` —
`parked` = every open blocked task; `finished` = status done with
`updated` within 48h. Facts are LEDGER QUOTES (evidence lines
verbatim, armor P3) — no model text anywhere in the board. Read-state
tracking ("seen") is deliberately deferred — record here if Jack wants
it. UI: an "Away board" section following the existing tabs pattern
(`interface\ui\index.html` + `app.js` read-only render + matching
`app.css` vocabulary); `interface\app.py` Api passthrough. Tests
BRD-001..004 (non-model): shape, 48h window, verbatim evidence,
empty-state. Live smoke rides the acceptance grading below.

### §M3-X — J1 acceptance grading (a)–(d), after everything merges

LIVE runs use `--test-session` (or `FRIDAY_TEST_SESSION=1`) — task
fixtures are fabrications and land in `brain\test_archive\`, tagged
and kept (Jack's 2026-07-09 split). Throwaway content only. Flip
`jobs.background_enabled` ON via the Controls panel for the duration.
- **(a)** one message, 3+-step local task → walk away → runner
  completes it unattended, per-step evidence in the file.
- **(b)** same shape with one outbound step (e.g. "then email it to
  me") → parks at the confirm with the reason recorded → approve in
  chat → unblock → completes.
- **(c)** kill FRIDAY mid-task (step 1 done, step 2 pending) →
  restart (`FRIDAY_TEST_SESSION=1` both runs) → the DURABLE TASKS
  block resurfaces it and the runner resumes from the ledger.
- **(d)** = §M3.2-G held (the suite IS the baseline evidence).
Record each with the evidence quoted; then ARCHITECTURE.md (tools,
injection, jobs, board, lockfile), roadmap M3 Status cell + §7 line,
auto-memory sync.

### M3 status (Sonnet fills in place)

| item | what | status |
|---|---|---|
| M3.0 | Pickup checks (baseline re-verify, worktree `..\FRIDAY-m3` + brain seed, in-flight check) | — |
| M3.1 | `tasks/` write guard + TSK-011/012 | — |
| M3.2a–e | Wiring + task_tools.py + injection + ilog fields | — |
| M3.2f | TKT-001..010 + regression sets + `--quick` | — |
| M3.2g | GT-J1 golden + ×5 batch (bar ≥4/5) | — |
| M3.2-G | Merge → flight vs `2346` → pre-registered gate applied → verdict block recorded | — |
| M3.3 | JobRunner + toggle + suite lockfile + JOB-001..008 | — |
| M3.4 | Away board API + UI + BRD-001..004 | — |
| M3-X | J1 acceptance (a)–(d) graded live (`--test-session`) + docs/memory sync | — |

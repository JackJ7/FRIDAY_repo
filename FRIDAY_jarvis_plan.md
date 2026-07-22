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
| M3.0 | Pickup checks (baseline re-verify, worktree `..\FRIDAY-m3` + brain seed, in-flight check) | DONE — baseline `d1d4a12..HEAD -- '*.py'` empty re-verified, worktree + brain seed created |
| M3.1 | `tasks/` write guard + TSK-011/012 | DONE — TSK-011/012 green, GATE-012 regression held |
| M3.2a–e | Wiring + task_tools.py + injection + ilog fields | DONE — `core/tools/task_tools.py`, bootstrap wiring, DURABLE TASKS block, `tasks_active`/`task_evidence_refused` ilog fields, identifier-floor surface union |
| M3.2f | TKT-001..010 + regression sets + `--quick` | DONE — TKT-001..010, MRG+IDG+PTL+TSK green, full `--quick` 444/444 green on branch `m3` (commit `1f3137e`) |
| M3.2g | GT-J1 golden + ×5 batch (bar ≥4/5) | **STOP 0/3 → RESOLVED by M3.2h: re-batch 5/5 (Fable, 2026-07-19). Original verdict below; fix design + evidence in §M3.2h.** |
| M3.2h | Task-claim recovery floor (Fable's answer to the STOP) | DONE — commit `969b74f` on `m3`; TCR-001..008 green, `--quick` 464/464, GT-J1 batch 5/5 with floor-fire attribution (§M3.2h status block) |
| M3.2-G | Merge → flight vs `2346` → pre-registered gate applied → verdict block recorded | **STOP (Sonnet, 2026-07-19 ~15:45)** — flight completed clean (stamp `2026-07-19_1155`, 559 items, no wedge, 197 ilogs archived); bars 1–2 met, bars 3/4/6 FAILED: `create_task` fires unprompted on an unrelated skill-decomposition turn (SKL-004, real schema-dilution signature — the gate's own STOP list names this exactly), plus GT-A (D2 family) and two perfect boards (memory_persistence, memory_recall) dropped. Full evidence + read in the STOP verdict block above M3.2h's status. NOT self-adjudicated, NOT reverted; baseline stays `2026-07-18_2346`; escalated to Fable/Jack for a fix design (M3.2h-style envelope fix candidate: tighten `create_task`'s arming condition). |
| M3.2i | Task-tool arming gate + TKA-001..006 + re-flight | **STOP (Codex, 2026-07-20 ~01:05)** — implementation commit `5e99fae`, merged to `main` as `f6145dd`; worktree and post-merge `--quick` 470/470; GT-J1 live batch met the ≥4/5 bar (five LOCKED passes; target scores 5/5, 5/5, 5/5, 4/5, 5/5). Candidate `2026-07-19_2059` completed 556/565 in 3:55:52 with 198 ilogs archived. The original SKL-004 leak was fixed (`task_tools_armed=False`, no task call there), but the new M3.2i hygiene row FAILED mechanically: GT-A's calendar/task cross-reference armed the family and called `task_status` with `tasks_active=0`, outside TKT/TCR/TKA/JOB/GT-J1. §M3.2-G bar 6 therefore also failed. No rechecks or M3-X run; baseline stays `2026-07-18_2346`. Full verdict at the end of §M3.2i. |
| M3.2j | Intent-bearing task noun gate + TKA-007..009 + re-flight | **STOP AT GT-J1 BATCH (Codex, 2026-07-20 ~02:55)** — isolated branch `codex/m3-2j`, code commits `9f1bb66` + `34bc0ca`; cue fix TDD/targeted/quick green, allowed test-session ledger iteration TSK-013 red→green + affected consumers 52/52 + `--quick` 474/474. GT-J1: run 1 failed on the archive enumeration gap; run 2 passed LOCKED 3/3 (TARGET 4/5); run 3 then failed because T1 had `task_tools_armed=True` but the model called no tool and only narrated the plan. Two misses make the >=4/5 bar unreachable, so runs 4-5 were not spent. Nothing merged; no flight/M3-X. Baseline remains `2026-07-18_2346`. Full STOP verdict at end of §M3.2j. |
| M3.2k | Explicit task-create landed floor + TCF guards + re-flight | **MERGED; HARD STOP (Codex, signed 2026-07-20)** — main merge `c66f24e`; signed STOP `346d4c8`. Fresh GT-J1 passed 5/5 and task hygiene held, but candidate `2026-07-20_1835` scored 566 passed / 2 flaky / 11 failed: `memory_persistence` fell to 0.8333 and stayed non-perfect on the only useful recheck, while VOX-002 repeated. Baseline remains `2026-07-18_2346`; no promotion or downstream closeout is licensed. Full evidence at the end of §M3.2k. |
| M3.2l | Hard-STOP repair: deterministic explicit-project persistence + banned-voice-tell floor | **MERGED; FULL-FLIGHT HARD STOP (Codex, signed 2026-07-22 ~01:55)** — merge `b60f2a6`; candidate `_2238` completed 590/600 with 199/199 ilogs. D2, GT-J1, task/floor hygiene, focused persistence, and VOX all held, but `quant_math` fell 0.957→0.870 and `PROP-012` repeated its x3600 energy slip on the first registered recheck (`_0108`). The required x2 repass is impossible, so no second recheck, promotion, or M3-X is licensed. Baseline remains `_2346`; main keeps the merge per the no-revert rule. Full verdict at the end of §M3.2l. |
| M3.3 | JobRunner + toggle + suite lockfile + JOB-001..008 | DONE — `core/jobs.py`, `jobs.background_enabled` toggle, `run_suite.py` PID lockfile, JOB-001..008 green (commit `7b3cec7`) |
| M3.4 | Away board API + UI + BRD-001..004 | DONE — `FridayService.get_away_board()`, `TaskLedger.list_all()`, UI tab, BRD-001..004 green (commit `7b3cec7`); full `--quick` 452/452 on branch `m3` |
| M3-X | J1 acceptance (a)–(d) graded live (`--test-session`) + docs/memory sync | **BLOCKED by M3.2l §M3.2-G hard STOP** — candidate `_2238` completed and passed D2/GT-J1/hygiene, but `PROP-012` failed both the flight and first same-day recheck. Bar 7's x2 repass cannot be met; baseline promotion and M3-X remain prohibited. |

**Merge note (Sonnet, 2026-07-19):** M3.3/M3.4 are code-complete, fully
tested, and committed on `m3` (`7b3cec7`, stacked on M3.1+M3.2's `1f3137e`)
— but they are NOT separately mergeable to `main`: both depend on M3.2's
bootstrap wiring (`engine.task_ledger`), so merging them alone would either
require cherry-picking around M3.2 (leaving `task_ledger` permanently `None`
— pointless, they'd no-op forever) or dragging M3.2's STOPped, gate-failed
code onto `main` unreviewed. Per Jack's steer ("continue M3.3/M3.4 now") the
intent was build-and-test-in-branch, not merge — so **nothing has been
merged to `main` this session.** All four items (M3.1–M3.4) sit
together on `m3`, green, waiting on the M3.2g GT-J1 verdict above. M3-X's
items (a)–(c) (JobRunner/away-board live behavior) could in principle be
graded directly against the `m3` worktree's own live instance without
touching `main`, but (d) is explicitly "= §M3.2-G held" and cannot be
graded until that verdict resolves — so M3-X waits as a whole rather than
partially closing.

**M3.2g STOP verdict (Sonnet, 2026-07-19, branch `m3` commit `1f3137e`)** — recorded
per §M3.2-G's "STOP-and-escalate ... record state here" instruction, not
self-adjudicated further:

- Code side of M3.2 is solid: TKT-001..010 (scripted-model) all green,
  including TKT-003/005 which exercise the SAME evidence-grounding path GT-J1
  needs live. The gate is doing its job — refusing ungrounded evidence — the
  problem is upstream of it.
- Live signature (5 for 5 across 2 pre-batch sanity runs + 3 official
  `--basetemp`-pinned batch runs, ALL identical): T1 (single-message 3-step
  job) passes clean every time — `create_task` fires, file lands with 3
  pending steps. T2 ("The coolant loop's drained — I did it just now. Tick it
  off.") fails every time: qwen2.5:14b reaches for `close_commitment` /
  `track_commitment` / (once) `resolve_project`+`list_projects` instead of
  `complete_task_step` — it never even calls the right tool, so the refusal
  text never gets a chance to teach the recovery.
- One schema-wording fix iteration applied per the pre-authorization (commit
  `1f3137e`): explicit "copy verbatim, never invent" on the `slug`/`evidence`
  fields of `complete_task_step`/`block_task`/`unblock_task`, and
  `create_task`/`task_status` descriptions now explicitly disambiguate from
  `track_commitment` ("not a single promise") and the project tools ("not a
  project folder"). Re-ran live after the fix: same failure signature,
  unchanged (model still reached for `close_commitment`).
- With 0/3 official batch runs holding and only 2 remaining, the ≥4/5 bar is
  already mathematically unreachable — batch halted at run 3/5 rather than
  spend more GPU time on a foregone conclusion (the 2 pre-batch sanity runs
  showed the identical signature, so this isn't a batch-variance artifact).
- **This is being read as a genuine model-ceiling gap, not a schema bug**: a
  message that pairs "I did X just now" with "tick it off" pattern-matches
  qwen2.5:14b's much more heavily-represented commitment-closing shape harder
  than the newer task-ledger shape, even with disambiguating tool text. Per
  the armor directive (CLAUDE.md) this is exactly the kind of ceiling that
  wants a local workaround, not a shrug — but §M3.2-G's own STOP clause is
  explicit that widening scope (e.g. a code-level barrier that redirects a
  misrouted `close_commitment`/`track_commitment` call back onto the open
  task when its wording matches an open step) is Fable/Jack's call, not
  something to self-authorize mid-leg.
- **Not touched, still available for the next leg**: a task-recovery floor
  (mirroring the NJ.2/read-ask precedent — catch a misrouted
  commitment-tool call that names language matching an open task step, and
  redirect/retry against `complete_task_step` instead) is the obvious
  candidate fix, but it is new armor scope, not a mechanical schema tweak, so
  it waits for Fable's design per the pre-registration's own boundary.
- **State left clean for resumption**: `m3` branch commit `1f3137e` has
  M3.1+M3.2 code-complete, fully tested (TKT/TSK/MRG/IDG/PTL/`--quick` all
  green), just unmerged. Nothing reverted. M3.3 build proceeds in the same
  worktree per the explicit STOP allowance ("M3.3/M3.4 may still merge during
  a STOP — they are non-model by scope check"); this roadmap's M3.2 row stays
  open pending Fable/Jack's read.

### M3.2h — task-claim recovery floor (Fable 5's response to the M3.2g STOP, designed 2026-07-19)

**The read (Fable, taking the STOP's escalation; Jack requested the fix
2026-07-19 late morning).** The M3.2g verdict is accepted as recorded:
genuine model ceiling, not schema wording — one pre-authorized wording
iteration produced an unchanged 5-for-5 failure signature, and per the
armor directive the answer is a local, verifiable workaround. Two facts
already in evidence decide the fix shape:
1. The tool contract ALREADY names Jack's own words this turn as a
   legal evidence channel (`_grounded`: normalized ≥8-char substring of
   the user message) — the floor opens **no new trust surface**.
2. The failing turn IS Jack's own words: he states the step's work
   happened and orders the tick. The model fails only the ENVELOPE
   (wrong tool family), never the authority — exactly the
   NJ.2 / RA.1 / calendar-first precedent, so the engine fixes only
   the envelope.

**The floor (engine `respond()`, settled-reply section — after the
narrated-JSON floor, BEFORE the false-completion floor: execution beats
correction, the PC.4 placement lesson).** Fire iff ALL hold:
1. `task_ledger` wired with ≥1 open task (everywhere else in the suite
   the floor is structurally dead — the DURABLE TASKS surgical posture).
2. The user message carries a completion cue (CUE-B): a tick-off
   imperative ("tick/check/cross … off", "mark … done/complete") or a
   first-person done-claim ("I did it", "I've done that", …).
3. One clause of the user message (split on sentence enders, " — ",
   ";") CLAIM-matches exactly one candidate step (pending or
   in-progress; blocked steps NEVER — unblock stays an explicit flow):
   folded content tokens (≥3 chars, stop-worded, 4-char prefix fold so
   drained/drain agree) cover ≥60% of the step's tokens with ≥2 hits,
   strictly best across ALL open steps — a tie or a second candidate
   above the bar drops the fire (the NJ.2 ambiguity rule).
4. The claim clause carries no negation / conditional / future marker
   ("isn't drained yet", "once the loop's drained", "need to drain"
   never fire).
5. No successful `complete_task_step` already landed on that step this
   turn (a model that did its job wins; the floor is a backstop), and
   no reply-rewriting floor (phantom / identifier / artifact-denial)
   fired this turn.

Action: the ENGINE runs `complete_task_step(slug, step, evidence=the
claim clause verbatim)` through `_run_tool` — gate, taint and referent
tracking hold, and the evidence is a substring of `user_input` so the
grounding gate passes by construction (the floor cannot sneak
ungrounded evidence past the contract). The receipt is APPENDED to the
settled reply (never replaced, never a second model hop — the F4/A1
lesson); an ERROR result appends nothing and records no fire. Keying on
Jack's claim + end-of-turn ledger state (not on which wrong tool the
model picked) covers every observed misroute signature:
`close_commitment`, `track_commitment`, the project-tool detour, and
zero-tools.

**Never-claim contract, restated:** the floor moves the ledger ONLY on
Jack's own in-turn words — the contract's existing evidence channel. A
model claim ("Marked it off") with no landed action still moves
nothing; a bare "Tick off step one" with no work-happened clause still
moves nothing (TKT-004 is the pin for exactly this and stays green).

**Ilog (additive, schema stable):** `task_claim_floor` bool.

**Guards (`tests\pillar1\test_task_claim_floor.py`, TCR-###,
scripted-model):**
- TCR-001 misrouted `close_commitment` + Jack's claim ("The coolant
  loop's drained — I did it just now. Tick it off.") → floor completes
  step 1, evidence line is Jack's clause verbatim, receipt appended,
  `task_claim_floor` true in the ilog.
- TCR-002 same claim, model emits ZERO tools → floor fires.
- TCR-003 two open steps both matching above the bar → NO fire
  (ambiguity drop), ledger untouched.
- TCR-004 bare tick-off with no content claim ("Tick off step one.")
  → NO fire (TKT-004's scenario stays behind the evidence gate).
- TCR-005 model correctly calls `complete_task_step` itself → no
  double-fire.
- TCR-006 negated / conditional claim → NO fire.
- TCR-007 no open tasks + tick-off phrasing → NO fire, zero task-tool
  calls (bar 6's surgical posture).
- TCR-008 model calls `complete_task_step` but its paraphrased
  evidence is REFUSED → floor recovers with the verbatim clause;
  the refusal still counts in `task_evidence_refused`.

**Adjudication addendum (extends §M3.2-G mechanically; nothing else
reopened):**
- GT-J1 batch re-run ×5 minute-spaced, same protocol, bar stays ≥4/5.
- Flag hygiene gains one row: `task_claim_floor` fires ONLY on
  TKT/TCR/GT-J1 turns; ANY fire elsewhere in the flight is a STOP
  (implied by `tasks_active == 0` elsewhere, stated explicitly).
- All other §M3.2-G bars unchanged and still binding for the merge +
  flight vs `2026-07-18_2346`.

**Status (updated in place, Fable, 2026-07-19 ~11:45):** IMPLEMENTED and
batch-verified on branch `m3` (commit `969b74f`). Evidence:
- TCR-001..008 all green first run after the floor landed (TDD: TCR-001
  reproduced the live miss in miniature and failed before the fix).
- Full `--quick` 464/464 in the worktree (TKT/TSK/MRG/IDG/PTL all held;
  TKT-004's never-claim pin green with the floor live).
- **GT-J1 live batch 5/5 — bar ≥4/5, was 0/3.** Attribution from the
  pinned-basetemp ilogs (`results\gtj1_fix_run1..5`): the misroute
  PERSISTED exactly as the M3.2g verdict read it — runs 2–5 the model
  still called `track_commitment` first on T2, run 1 it called nothing —
  and `task_claim_floor` fired True on T2 in all five runs, completing
  step 1 on Jack's verbatim clause. T3 stayed clean 5/5 (zero floor
  fires on the status ask); in run 4 the model tried an ungrounded
  `complete_task_step` on T3 and the evidence gate REFUSED it
  (`task_evidence_refused` 1, ledger unchanged) — the LOCKED contract
  held because of the gate, exactly the designed division of labor.
- Zero false fires anywhere in the batch or the scripted suites.
Ship gate §M3.2-G (merge → post-merge `--quick` → detached flight vs
`2026-07-18_2346` → mechanical bars + the M3.2h hygiene addendum) is
the remaining step; proceeding this session per the pre-registered
execution order.

**§M3.2-G STOP verdict (Sonnet, 2026-07-19 ~15:45, candidate
`2026-07-19_1155` vs baseline `2026-07-18_2346`, commit `062e614`,
559 items)** — recorded per §M3.2-G's own "STOP-and-escalate ... do
NOT self-adjudicate, do NOT revert merged code, record state here"
instruction:

- **Flight mechanics (bars 1–2): MET.** Pre-merge TKT/TSK guards +
  post-merge `--quick` 464/464 + GT-J1 5/5 already held before launch.
  Flight ran clean start to finish (`11:55:23`→`15:12:24`, no wedge,
  watchdog clean throughout). 197 sandbox ilogs pulled this session
  from the pinned pytest basetemp (`pytest-of-jacko\pytest-675` — the
  run's own tmp root, identified by finish-time match) and archived to
  `results\2026-07-19_1155\sandbox_ilogs\` (naming convention:
  `<sandbox-dir>__<jsonl-date>.jsonl`, matching the `2346` precedent).
- **Bar 3 (perfect boards HELD at 1.000): FAILED.** Two of five boards
  dropped: `memory_persistence` 1.000→0.8167 (MEM-001 0.0, MEM-002
  0.0, GRW-004 0.8/1.0) and `memory_recall` 1.000→0.75 (PRV-005 0.0).
  `injection_defense`, `briefing`, `session_ops` all HELD.
- **Bar 4 (D2 family, m1=m2=m3=m5=0): FAILED.** GT-A (meeting-thread
  golden, turn 5 — "Cross reference my calendar and tasks...") 1.0→0.0.
  All other D2 members (GT-B, GT-C1/C3/C5/C9/C10, GT-P5a/b, GT-P2a)
  held at 1.0. GT-A's own ilog (`test_gt_a_meeting_thread0`) shows
  `tasks_active: 0` and zero task-tool calls on the failing turn — the
  miss is english/scaffold/third-person-class per the test's own TARGET
  checks, not a task-ledger leak. GT-A has a **prior flaky-in-full-suite
  precedent** (memory obs 2126, 2026-07-15: "passes in isolation, fails
  in candidate suite") — task-flag-free, so it is recheck-eligible under
  bar 7's mechanical churn rule, but the bar itself (D2 must ALL pass)
  is unmet as flown and is not self-adjudicated here.
- **Bar 6 (flag hygiene, ANY fire outside TKT/TCR/JOB/GT-J1 is a STOP):
  FAILED — the actual gating finding.** `test_decomposition_discipline0`
  (SKL-004, a generic problem-decomposition skill test with NO task
  vocabulary in its own scope) shows the model spontaneously calling
  `create_task` on turn 1 ("I need to figure out how to approach sizing
  the whole drivetrain... help me plan the attack") — a real
  `drivetrain_sizing_plan` task lands in the ledger, `tasks_active: 1`,
  for the rest of that sandbox's turns. This is the ONLY task-tool
  signal found anywhere outside the TKT/TCR/JOB/GT-J1 families (checked
  all 197 archived ilogs for `create_task`/`complete_task_step`/
  `block_task`/`unblock_task`/`list_open`/`tasks_active`>0 by name).
  This is exactly the schema-dilution shape §M3.2-G's STOP list names
  verbatim ("any newly-failing transcript showing task-tool calls...
  is [a STOP]") — the presence of the task toolset is changing behavior
  on turns that never asked for task tracking. No recheck escape is
  offered for this category by the gate's own text (the ×2-recheck
  churn path in bar 7 covers score bands, not tool-call leakage), so
  none was run — spending more GPU time would not change this reading,
  same logic as M3.2g's early batch-halt.
- **Other down-deltas, NOT individually adjudicated (task-flag-free by
  spot check, left for the recheck pass whoever picks this up runs):**
  `calendar` 1.0→0.75 (GT-A, see above), `thinking_skills` 0.8→0.6769
  (GND-012 0.4, GND-013 0.6, SKL-003/004 0.6 — SKL-004 IS the
  decomposition-discipline case above, so this skill's drop is NOT
  pure churn, it's the same finding), `quant_math` unchanged at 0.9565
  (PROP-010 0.0, pre-existing churn per prior legs), `project_ops`
  0.95→0.8667 (COM-001 0.0 — `test_inference_pending`, checked
  task-flag-free), `email_triage`/`voice`/`playbook_following` within
  known bands (EML-004, CFG-007, PLB-004).
- **Read:** M3.2's task toolset is bleeding into unrelated conversation
  turns — a real user asking for help thinking through an unfamiliar
  mechanical-design problem now gets an unsolicited durable task created
  behind their back, and a routine calendar/task cross-reference golden
  turn regressed. This is a genuine model-facing side effect of adding
  `create_task` to the always-available toolset (schema-dilution
  reading), not a test artifact — the M3.2g STOP was about the model
  MISSING the right tool; this STOP is about the model REACHING for it
  when nothing asked for it. Two different failure directions from the
  same new surface.
- **Not touched:** no code reverted, `main` unchanged beyond this
  documentation commit. M3.1/M3.3/M3.4 remain merged and green
  (non-model by scope, unaffected by this finding). This roadmap's M3
  row stays open pending Fable/Jack's read — candidate fix shape is
  Fable's call (e.g., a stricter `create_task` arming condition —
  explicit task/plan-tracking language, not just "help me plan/approach
  X" — mirroring the M3.2h precedent of a targeted envelope fix over a
  broad tool-description rewrite).
- **State for resumption:** baseline for any future leg stays
  `2026-07-18_2346` (this candidate does NOT become the new baseline —
  a STOP-gated flight cannot promote). Archived evidence:
  `results\2026-07-19_1155\{report.json,report.html,scorecard.json,
  sandbox_ilogs\}` (197 files).

### M3.2i — task-tool arming gate (Fable 5's response to the §M3.2-G STOP, designed 2026-07-19 evening; implementer: Codex, mechanical protocol below)

**The read (Fable, taking the STOP's escalation).** The verdict is
accepted as recorded. But the escalation note's "tighten create_task's
arming condition" is only half the fix — the STOP evidence points at
TWO coupled problems from one surface:
1. Bar 6: the model REACHED for `create_task` on a turn with no task
   vocabulary (SKL-004). An in-tool guard alone would stop the ledger
   write but the schema would still sit in every call.
2. Bars 3–4: perfect boards and GT-A dropped on transcripts that are
   task-flag-free. The gate's own text names the mechanism: "five
   always-present schemas are the one suite-wide surface" — dilution by
   PRESENCE, not by calls. No in-tool guard can touch that.

So the fix is **schema-scoped**: on turns where nothing asks for task
tracking and nothing is tracked, the model must not see the task tools
at all. That removes both failure modes by construction — a schema that
isn't in the payload can't be called AND can't dilute — and it restores
non-task turns to a baseline-identical toolset, which is what bars 3–4
measure. In-tool guarding stays as defense in depth (prompts are soft;
schema filtering + code refusal are the two hard layers).

**The design (three small pieces, all local, all code-checkable):**

1. **Registry arming (mechanism).** `Tool` gains an optional
   `arm: callable | None = None` field (default None = always armed —
   every existing tool unchanged). `ToolRegistry.register(...)` accepts
   and stores it; `to_ollama()` skips tools whose `arm()` returns False
   at call time. `call()` does NOT check `arm` — the M3.2h floor drives
   `complete_task_step` through `_run_tool` engine-side and must keep
   working when schemas are hidden (the floor is engine-initiated, not
   model-initiated; gate/taint checks in `_run_tool` still apply).

2. **The arming predicate (policy).** One shared closure registered on
   ALL FIVE task tools (create/status/complete/block/unblock — they arm
   and disarm as a family; a partial set invites exactly the misroutes
   M3.2g/M3.2h dealt with). Armed iff EITHER:
   - the ledger has ≥1 open task (`status != done`) — status, ticks,
     block/unblock must work on follow-up turns, and the
     `TaskLedger.summary()` referent-block injection already keys on
     the same state; OR
   - THIS turn's user message carries explicit task-tracking language
     (CUE-T): word-boundary, casefolded match on tracking-explicit
     vocabulary only — the nouns "task"/"tasks", "checklist",
     "to-do"/"todo (list)", the phrases "keep track", "keep a list",
     "check off"/"tick off"/"mark off"/"cross off", and the unattended
     markers "while I'm away"/"while I'm out"/"unattended"/"in the
     background". Read the turn input via the `ctx.engine` pattern
     already in `task_tools.py` (`_turn_user_input`).
   **Deliberately NOT cues:** "plan", "approach", "figure out", "help
   me think/work through", "steps". The SKL-004 live specimen ("I need
   to figure out how to approach sizing the whole drivetrain... help me
   plan the attack") must arm NOTHING. Planning talk is conversation;
   tracking talk is a ledger. That line is the whole fix.
   **Cue-list calibration rule (do this BEFORE writing the list in
   code):** read GT-J1's T1 and every TKT/TCR creation-turn prompt.
   Each must contain ≥1 CUE-T item verbatim. If one doesn't, extend the
   list ONLY with tracking-explicit wording taken from that prompt
   (e.g. "work through it and check things off" → the "check off"
   family). If a golden's creation turn contains NO tracking-explicit
   wording at all, STOP and escalate to Fable/Jack — do not stretch the
   list toward planning vocabulary to make a test pass.

3. **In-tool guard (defense in depth).** `create_task` re-checks CUE-T
   against `_turn_user_input()` at execution time and, on miss, refuses
   without touching the ledger:
   `"ERROR: Jack didn't ask to track a task this turn — answer his
   question directly. Use create_task only when he explicitly asks for
   a tracked task/checklist."`
   This covers the armed-because-a-task-is-open case (model tries to
   spawn a SECOND unrelated task on a status turn) and any recovered/
   narrated tool-call path that bypasses schema filtering. The other
   four tools get no in-tool guard — operating on an EXISTING open task
   is what they're for, and the M3.2h floor + evidence gate already
   police the dangerous one (`complete_task_step`).

**Ilog (additive, schema stable):** `task_tools_armed` bool per turn.
`create_task` refusals land in the normal tool-result stream (no new
counter; grep the archived ilogs for the refusal string when auditing).

**Guards (`tests\pillar1\test_task_arming.py`, TKA-###, scripted-model;
TDD — write TKA-001 first and watch it fail on current `main`):**
- TKA-001 the SKL-004 live specimen VERBATIM (drivetrain decomposition
  ask), empty ledger → `task_tools_armed` False, zero task schemas in
  the model payload (assert on the actual `to_ollama()` list the engine
  sends), zero task-tool calls, `tasks_active` 0. This is the
  regression pin for the whole STOP.
- TKA-002 explicit ask ("Track this as a task: ... checklist ...") →
  armed, `create_task` succeeds, receipt presented.
- TKA-003 one open task + neutral follow-up ("how's it looking?") →
  armed (family arms on open state); scripted model calls `create_task`
  for an unrelated second task WITHOUT CUE-T this turn → refused with
  the redirect string, ledger unchanged, original task intact.
- TKA-004 empty ledger + neutral turn → `to_ollama()` payload contains
  no task tool; TCR-007's zero-fire posture reconfirmed alongside.
- TKA-005 GT-J1's T1 phrasing verbatim → armed (pins the cue-list
  calibration so a later wording edit can't silently disarm the
  golden).
- TKA-006 open task + Jack's tick-claim turn (TCR-001 scenario) →
  M3.2h floor still fires and completes the step even though arming
  came from open-state, proving floor and gate compose.
- Existing suites that must stay green untouched: TKT-001..., TCR-001..008,
  TSK, GT-J1 module, `--quick` full.

**Execution protocol (Codex, mechanical — the M3.2h/§M3.2-G machinery
reused verbatim; STOP = record state here, escalate Fable/Jack, touch
nothing else):**
1. Fresh worktree off current `main` (`..\FRIDAY-m3` may be reused only
   after `git -C ..\FRIDAY-m3 status` is clean and it's fast-forwarded
   to `main`). Confirm baseline validity first: `git log
   541898c..HEAD -- '*.py'` on `main` must be empty (docs-only since
   the STOP), else STOP — baseline `2026-07-18_2346` would be invalid.
2. Implement pieces 1–3 exactly as above (cue-list calibration rule
   BEFORE coding the list). TKA-001 red-then-green; all TKA + TCR + TKT
   + TSK green; `--quick` full pass in the worktree.
3. GT-J1 live batch ×5, minute-spaced, bar ≥4/5 — same protocol and
   attribution style as the M3.2h status block (pinned basetemp, floor
   fires recorded). One pre-authorized fix iteration on a miss;
   a second miss is a STOP.
4. Merge to `main`, post-merge `--quick`, then the detached full-suite
   candidate flight vs baseline `2026-07-18_2346` per the RN.5 protocol
   (Start-Process detached + ollama_watchdog; FROZEN CODE until it
   lands).
5. Adjudicate §M3.2-G bars 1–7 unchanged, PLUS the M3.2h addendum row,
   PLUS one new M3.2i row: **`task_tools_armed` True ONLY on turns in
   the TKT/TCR/TKA/JOB/GT-J1 families or turns whose sandbox has an
   open task in those families; True anywhere else is a STOP.**
   Expectation stated for the record: bars 3–4 recover BECAUSE non-task
   turns now carry a baseline-identical payload — if a perfect board
   still fails on a task-flag-free, armed-False transcript, that's the
   bar-7 churn rule's territory (×2 recheck), NOT a dilution finding;
   GT-A specifically has the flaky-in-full-suite precedent (obs 2126)
   and is recheck-eligible.
6. Gate met → verdict block here (IG.5 format), flip roadmap M3.2,
   **next baseline = the M3.2i candidate**, then immediately run M3-X:
   J1 acceptance (a)–(d) graded live under `--test-session` ((d) = this
   gate held), docs (`ARCHITECTURE.md` tool-registry section gains the
   `arm` field) + memory sync, and **close M3 in the roadmap**. Fable
   spot-audits the verdict read-only at the next Track A session.

**M3.2i STOP verdict (Codex, 2026-07-20 ~01:05, candidate
`2026-07-19_2059` vs baseline `2026-07-18_2346`, merge `f6145dd`,
565 items)** — recorded per the execution protocol's "STOP = record
state here, escalate Fable/Jack, touch nothing else" instruction:

- **Implementation and pre-flight gates: MET.** Baseline validity held
  before coding. TKA-001 reproduced the original SKL-004 surface red,
  then TKA-001..006 went green with TCR/TKT/TSK and the pre-existing
  REPO-003 malformed-regex regression. The unrelated REPO-003 cause was
  adjudicated in `core/tools/repo_tools.py`: the ripgrep path treated exit
  2 (invalid regex) like exit 1 (valid/no matches); it now returns an
  `ERROR` for every exit other than 0/1. Worktree `--quick` and merged-main
  `--quick` both passed **470/470** (post-merge stamp
  `2026-07-19_2051`). GT-J1's five minute-spaced live specimens all held
  the LOCKED case; TARGET scores were 5/5, 5/5, 5/5, 4/5, 5/5, meeting
  the ≥4/5 case-fraction bar.
- **Flight mechanics (bars 1–2): MET.** Detached candidate
  `2026-07-19_2059` ran to completion in 3:55:52: **556 passed / 9
  failed of 565**, no wedge (watchdog's long quiet PROP-tail checks all
  cleared on advancing keep-alive expiry). The pinned basetemp yielded
  **198 interaction logs**, archived immediately under
  `results\2026-07-19_2059\sandbox_ilogs\`.
- **Original M3.2-G leak: FIXED.** SKL-004 is now a task-signal-free
  transcript (`task_tools_armed=False`, `tasks_active=0`, zero task-tool
  calls); its report result was the documented voice/skill-band
  `FLAKY-FAIL` at 4/5, not the prior durable-task creation. The schema
  gate therefore closed the specific SKL-004 failure it was designed for.
- **Bar 3 as flown: FAILED, recheck-eligible but not rechecked after the
  hard STOP below.** `memory_persistence` 1.000→0.917 (MEM-002) and
  `memory_recall` 1.000→0.950 (PRV-005 at 4/5). Injection defense,
  briefing, and session held at 1.000. The failed transcripts carried no
  task signal, so the design assigns them to bar-7 churn rechecks; those
  rechecks were not started once the independent hard hygiene STOP was
  found.
- **Bar 4 as flown: FAILED.** GT-C10 missed its on-disk merge LOCKED check
  (6/7 LOCKED; it re-asked for the already-named duplicate on T2). GT-A,
  GT-B, the other GT-C cases, GT-P5a/b, and GT-P2a passed. GT-C10's
  transcript was task-signal-free, but no recheck was run after the hard
  STOP.
- **Bar 5 and the M3.2h addendum: MET.** In-suite GT-J1 passed. Across all
  198 ilogs, `task_claim_floor=True` occurred only on GT-J1 T2; no
  out-of-family claim-floor fire was found.
- **Bar 6 + the new M3.2i arming-hygiene row: HARD STOP.** The only
  out-of-family task signal was GT-A turn 5: "Cross reference my calendar
  and tasks — remove any task you don't see on the calendar, but don't add
  any tasks." The noun `tasks` matched CUE-T, so
  `task_tools_armed=True`; the model called `read_calendar,task_status`
  and replied that no active tasks were tracked. Its ilog has
  `tasks_active=0`, `task_claim_floor=False`, and
  `task_evidence_refused=0`. This violates both §M3.2-G bar 6's zero
  task-tool-calls rule outside the permitted families and M3.2i's explicit
  "True anywhere else is a STOP" row. GT-A happened to pass its case
  score, but neither hygiene rule provides a score-based recheck escape.
- **Compare left unadjudicated beyond the hard STOP:** four newly failing
  cases (GT-C10, MEM-002, PRV-005, SKL-004) and three newly passing
  (CFG-007, EML-004, SKL-003); the remaining pytest failures were
  pre-existing/known-band cases. Per protocol, no ×2 churn rechecks, no
  further cue change, and no M3-X acceptance were attempted.

**Read / handoff:** schema hiding fixed the original unrelated-planning
leak, and the malformed-regex defect is repaired, but CUE-T's bare
`task(s)` noun exposes the durable-task family during GT-A's calendar/task
cross-reference and permits the exact out-of-family task call the flight
hygiene forbids. Code is not reverted; `main` remains at `f6145dd` plus
this documentation record. Candidate `2026-07-19_2059` does **not** become
the baseline; baseline remains `2026-07-18_2346`. M3.2 and M3 stay OPEN,
M3-X stays BLOCKED, and the next decision belongs to Fable/Jack.

### M3.2j — intent-bearing task noun gate (authorized by Jack 2026-07-20; Codex owns design + execution)

**Authorization.** Jack explicitly authorized Codex to invent and execute
the next fix after the M3.2i STOP without waiting for Fable or a second Jack
decision. All pre-registered mechanical gates remain binding; a NEW STOP is
still recorded here and halts the leg.

**Read-only diagnosis / root cause.** The registry mechanism is correct:
`to_ollama()` hides an unarmed schema family, while `call()` remains
available to M3.2h's engine-owned task-claim recovery floor. Open-ledger
arming, TaskLedger state, and the floor are also correct. The conflict is
one policy token in `core\tools\task_tools.py`: CUE-T treats standalone
`task`/`tasks` as explicit durable-tracking intent. GT-A turn 5 — "Cross
reference my calendar and tasks — remove any task you don't see on the
calendar, but don't add any tasks." — has an empty durable ledger and never
asks to create or track one. The bare nouns nevertheless arm all five
schemas; once `task_status` is visible, the model's call is expected rather
than a second defect.

**Alternatives considered.** (1) A GT-A/calendar-specific negative
lookaround is smaller in characters but encodes one transcript rather than
the semantic boundary and would miss the next generic task-reference shape.
(2) Per-tool arming or a new engine intent classifier could hide
`task_status` separately, but broadens two proven seams and risks the
open-task, JobRunner, and M3.2h flows. **Selected:** keep family arming and
make the ambiguous noun intent-bearing.

**Smallest code-enforced fix.** Change only the shared CUE-T regex in
`core\tools\task_tools.py`:

- Standalone `task`/`tasks` is NOT a cue.
- `task(s)` remains a cue only in a positive explicit `create ... task`
  construction (with ordinary short determiners such as `a`, `this`, `the`,
  `my`, or `another`). `don't` / `do not` / `never create ... task` is not a
  cue. Do not add a broad `add ... task` branch: the GT-A specimen itself says
  "don't add any tasks", so that would reproduce the bug under a new token.
- Existing `track this/the ...` wording remains unchanged.
- Existing standalone `checklist`/`to-do` vocabulary, `keep track`/`keep a
  list`, check/tick/mark/cross-off phrases, unattended/background markers,
  and open-ledger arming remain unchanged.
- `create_task` continues to re-check this same predicate. No registry or
  engine change: engine-side `complete_task_step` recovery must remain able
  to call through the registry when schemas are hidden.

**Exact behavior boundary.** Empty ledger: the GT-A cross-reference, "what
tasks are on the calendar?", and other bare task-noun discussion do NOT arm.
Explicit "Create a task...", "Track this job...", "make me a checklist",
and the GT-J1 T1 wording DO arm. Any open task arms
the family on neutral status/follow-up, completion, block, unblock, and
JobRunner turns exactly as before. `create_task` still refuses a second
unrelated task when open-state arming is the only license.

**TDD guards (`tests\pillar1\test_task_arming.py`):**

- TKA-007: GT-A turn 5 verbatim, empty ledger, scripted direct reply. Assert
  the actual first model payload contains zero task schemas, no task tool
  enters history, `task_tools_armed is False`, and `tasks_active == 0`.
  Write first and observe it fail on merged M3.2i because `task(s)` arms.
- TKA-008: explicit "Create a task for the calibration run..."
  turn with a scripted `create_task` call. Assert the whole family is visible,
  the task file/receipt lands, and `task_tools_armed is True`. This prevents
  the negative fix from deleting legitimate direct-create phrasing.
- TKA-009: "Do not create any tasks..." with an empty ledger remains
  disarmed. This pins the negation guard on the one newly added creation
  construction.
- Existing TKA-001..006 are unchanged and must remain green. TKA-002/TKA-005
  retain explicit creation/GT-J1 calibration; TKA-003 preserves open-task
  follow-up plus second-create refusal; TKA-006 and TCR-001..008 preserve the
  engine recovery floor; TKT covers completion/block/unblock and TSK covers
  ledger/write guards.

**Mechanical execution protocol (M3.2i reused, only baseline-validity anchor
and hygiene pin updated):**

1. Start from a clean isolated worktree at current `main`. Because the
   intentionally merged M3.2i code is itself the candidate surface relative
   to baseline `2026-07-18_2346`, baseline validity for this continuation is:
   `git log f6145dd..HEAD -- '*.py'` on `main` must be empty before M3.2j
   coding. Docs-only STOP/design commits are allowed. Any later Python change
   outside the single CUE-T fix is a STOP.
2. Add TKA-007/TKA-008; run TKA-007 alone and observe the expected red arming
   failure. Make the one regex change. Run TKA-007/TKA-008 green, then all TKA
   + TCR + TKT + TSK and the focused compatibility groups named by M3.2i.
   Run one full `python run_suite.py --quick` in the worktree.
3. Run GT-J1 live batch x5 under `--test-session`, pinned basetemp,
   minute-spaced, with bar >=4/5 and the M3.2h attribution fields recorded.
   One pre-authorized fix iteration on a miss; a second miss is a STOP.
4. Merge to `main`, run one post-merge `--quick`, then launch the frozen-code
   detached full candidate flight against baseline `2026-07-18_2346` using
   the same RN.5 Start-Process + watchdog protocol. Archive all sandbox ilogs.
5. Adjudicate M3.2-G bars 1-7, the M3.2h addendum, and this revised arming
   hygiene rule: `task_tools_armed=True` is licensed only by an open task or
   explicit intent-bearing CUE-T language in TKT/TCR/TKA/JOB/GT-J1. The GT-A
   turn-5 pin must be `task_tools_armed=False`, `tasks_active=0`, with zero
   task-tool calls. Bare task nouns never license arming. Any other
   out-of-family `True`/task call remains a hard STOP. Task-signal-free
   score drops use bar 7's x2 recheck rule; no hygiene STOP receives a score
   escape.
6. Only if every gate holds: record the IG.5-style verdict here, promote the
   new candidate baseline, run M3-X (a)-(d) live under `--test-session`, update
   ARCHITECTURE.md's registry/task/job/board contracts, perform the required
   memory sync, and close M3 in `FRIDAY_roadmap.md`.

Designed and recorded by Codex (GPT-5.6) under Jack's explicit authorization
— 2026-07-20.

**M3.2j STOP verdict (Codex, 2026-07-20 ~02:55; isolated branch
`codex/m3-2j`, commits `9f1bb66` + `34bc0ca`; docs STOP commit `cb2a87d`).**

- Pre-live code gates met: TKA-007/TKA-009 red→green; initial targeted
  compatibility 46/46; correctly seeded worktree `--quick` 473/473.
- Required test-session routing exposed a pre-existing TaskLedger enumeration
  gap on GT-J1 run 1: `create_task` wrote
  `test_archive/tasks/flux_bench_refit.md`, but `list_open()` discarded that
  physical archive prefix and logged `tasks_active=0`. The one licensed fix
  iteration added TSK-013 plus logical task-slug enumeration. TSK-013
  red→green, affected TKA/TCR/TKT/TSK/BRD/JOB 52/52, post-fix worktree
  `--quick` 474/474 (`2026-07-20_0246`).
- GT-J1 run 2 passed under `FRIDAY_TEST_SESSION=1`: LOCKED 3/3, TARGET 4/5;
  T2's persistent commitment-tool misroute was recovered by
  `task_claim_floor=True`. Its ilog was archived immediately under
  `results\gtj1_m3j_run2\sandbox_ilogs` in the worktree.
- GT-J1 run 3 was the second miss. T1 had `task_tools_armed=True` but the
  model emitted zero tools, narrated the correct three-step plan, and asked
  for confirmation without calling `create_task`. With no task, T2/T3 also
  failed LOCKED state. Its ilog is under
  `results\gtj1_m3j_run3\sandbox_ilogs`.
- Two misses make the >=4/5 bar unreachable; runs 4-5 were not spent. The one
  fix allowance is consumed. No further code change, merge, post-merge quick,
  detached flight, compare recheck, M3-X, ARCHITECTURE update, or memory sync
  ran. M3.2j code remains unmerged on the clean isolated branch; candidate
  `2026-07-19_2059` remains unpromoted; baseline remains
  `2026-07-18_2346`; M3 stays OPEN.

STOP recorded by Codex (GPT-5.6) — 2026-07-20.

### M3.2k — explicit task-create landed floor (approved by Jack 2026-07-20; Codex owns design + execution)

**Authorization and controlling boundary.** Jack approved Option 1 after the
M3.2j STOP and authorized Codex to do the work needed to execute it. This is a
new leg, not a resumption of M3.2j's remaining runs. It may bring forward only
M3.2j code commits `9f1bb66` (intent-bearing CUE-T) and `34bc0ca`
(test-session TaskLedger enumeration), then add the landed-create floor
described here. A fresh ONE mechanical fix iteration is licensed for the new
GT-J1 batch; a second miss is a STOP. Every §M3.2-G, M3.2h, and M3.2j hygiene
bar remains binding.

**Read-only forensic verdict.** The schemas and ledger are no longer the
failure:

- Run 1 called `create_task`; the only failure was the test-session physical
  `test_archive/tasks/` enumeration gap, fixed and pinned by `34bc0ca` /
  TSK-013.
- Run 2 called `create_task`, created one open archived task, and passed all
  three LOCKED contracts. M3.2h recovered T2's commitment-tool misroute.
- Run 3 entered T1 with `task_tools_armed=True`, but the main model round chose
  zero tools. Its settled draft then tripped the output-script floor. That
  floor deliberately regenerates tool-free and runs LAST; its replacement
  correctly narrated the three-step plan and ended `Confirm this plan?` after
  every tool-capable recovery floor had already passed. The late scan could
  only arm the general `pending_task` ledger (`pending_task_armed=True`), not
  the durable TaskLedger (`tasks_active=0`). No later turn could recover T2/T3.
- Therefore the missing invariant is **landed creation**, not visibility:
  explicit creation intent can currently finish with an armed schema and a
  plan, but no successful `create_task` receipt.

**Alternatives adjudicated.** (1) A single tool-enabled corrective retry is a
smaller diff but still probabilistic; qwen can ignore the tool again, so it is
not a code floor. (2) A pre-turn structured planner would cover underspecified
requests, but adds a model call and new orchestration to every successful
creation turn. **Selected:** one bounded, deterministic post-generation floor
that recovers only text already present in Jack's request or FRIDAY's explicit
plan and calls the existing tool through the existing engine seam.

**Smallest code-enforced design.** Two files own the behavior:

1. `core\tools\task_tools.py` keeps M3.2j's `_TASK_TRACKING_CUE` unchanged and
   adds two pure helpers:

   ```python
   def explicit_task_creation_requested(text: str) -> bool:
       """Positive create/track/set-up intent only; discussion and negation
       return False."""

   def recover_task_plan(user_input: str,
                         reply_text: str) -> tuple[str, list[str]] | None:
       """An unambiguous user-grounded title plus 2-10 concrete steps, or
       None. Never invent a title or step."""
   ```

   The creation predicate is intentionally narrower than family arming. It
   accepts positive `create ... task`, `track this/the ...`, `set up ...
   task/checklist`, and `make ... checklist` constructions. `don't`, `do not`,
   `never`, and `no need to` in the governing clause block it. Bare task nouns,
   task/calendar cross-reference, status/tick/block/unblock language, generic
   planning, and open-ledger state alone never qualify.

   Recovery is deterministic and bounded. The title must be a substring of
   Jack's request: the named span before the first task-plan colon, or the
   first named clause after a generic `track this as a task:` / `track this
   job:` lead. Steps are tried in this order: (a) 2-10 explicit action clauses
   in Jack's colon-delimited request, split only on commas, semicolons, or
   `then`, with trailing `set it up / tell me the plan` meta-language removed;
   (b) the first contiguous 1-based numbered block in the final reply; (c) the
   first contiguous bullet block in the final reply. Recovered strings remain
   verbatim apart from surrounding whitespace/punctuation. Missing title,
   fewer than two steps, more than ten steps, duplicate/empty steps, or two
   competing list blocks returns `None`.

2. `core\engine.py` captures the turn-start condition before retrieval:

   ```python
   task_creation_requested = (
       task_ledger is not None
       and not task_ledger.list_open()
       and explicit_task_creation_requested(user_input)
   )
   ```

   The normal model/tool loop always wins. AFTER the output-script floor and
   BEFORE the held stream, history persistence, offer ledger, and general
   pending-task ledger, the engine checks for a successful `create_task` in
   `tool_log`. If none landed and the turn-start condition is true, it calls
   `recover_task_plan`. A recovered plan is executed as
   `_run_tool("create_task", {"title": title, "steps": steps})`; this is the
   same seam as native calls, so taint confirmation, the registry's in-tool
   cue guard, TaskLedger duplicate protection, Brain git writes, test-session
   archive routing, referent tracking, `on_tool`, and receipt semantics remain
   intact. No direct `TaskLedger.create` call is permitted.

   The synthetic transcript uses a real assistant tool-call envelope, then a
   tool result, then the final assistant text with the receipt appended. A
   successful receipt makes `action_landed=True`, so the generic pending-task
   ledger does not also arm. A blocked/error receipt is reported verbatim. If
   recovery returns `None`, no tool runs and the reply gains this code-built
   knowledge-gap line: `I haven't created a task: I need a clear title and
   2-10 concrete steps. What title and steps should I use?` No model-authored
   guess becomes ledger state.

   Add additive ilog field `task_creation_floor`: True when this recovery floor
   engages, including an honest blocked/gap outcome; `tools`, tool receipt, and
   `tasks_active` distinguish landed from non-landed. It must be False outside
   explicit empty-ledger creation turns.

**Preserved contracts / explicit non-scope.** No registry change, no schema
wording change, no model-client/tool-choice change, no direct Brain/TaskLedger
write, no change to open-task injection or the five task tools, no change to
M3.2h claim matching/evidence, no JobRunner change, and no change to board or
Service APIs. Existing open tasks keep the family armed and keep status,
completion, block/unblock, background execution, and evidence checks exactly
as shipped. The floor is empty-ledger creation recovery only. Any required
Python change outside `core\tools\task_tools.py`, `core\engine.py`, the brought-
forward `core\tasks.py`, and their task-floor tests is a STOP for Jack/Fable.

**TDD cases (`tests\pillar1\test_task_creation_floor.py`, case IDs TCF-001..007).**

- TCF-001 — GT-J1 T1 verbatim, empty ledger, scripted zero-tool numbered plan:
  RED on M3.2j because no task exists; GREEN requires one `flux_bench_refit`
  task with the exact three pending steps, a real `create_task` receipt,
  `task_creation_floor=True`, `task_tools_armed=True`, `tasks_active=1`.
- TCF-002 — first scripted reply contains a qualifying foreign-script run;
  script-floor retry returns the English GT-J1 plan with zero tools. GREEN
  proves ordering: `script_drift_corrective=True`, `task_creation_floor=True`,
  and the same durable three-step task exists.
- TCF-003 — native `create_task` lands in the main loop. GREEN requires one
  task, one receipt, and `task_creation_floor=False` (never double-create).
- TCF-004 — parametrized GT-A turn 5, SKL-004, `What tasks are on the
  calendar?`, and `Do not create any tasks for this review.` GREEN requires no
  task schemas where M3.2j says disarmed, zero task calls, zero tasks, and
  `task_creation_floor=False`.
- TCF-005 — one existing open task plus a neutral status/follow-up reply.
  GREEN requires no second task and no floor fire; existing TKA/TKT/TCR/JOB
  tests remain the authoritative open-flow coverage.
- TCF-006 — positive creation wording without a recoverable title or 2-step
  plan. GREEN requires no mutation, no tool call, the exact code-built gap,
  and `task_creation_floor=True`.
- TCF-007 — `Brain.test_session=True` plus the TCF-001 zero-tool recovery.
  GREEN requires the physical `test_archive/tasks/flux_bench_refit.md`, logical
  `list_open()` visibility, and no real `tasks/flux_bench_refit.md` write.

**Implementation sequence (red → green, independently auditable).**

1. On `main`, verify `git log f6145dd..HEAD -- '*.py'` is empty; commit this
   design/roadmap update. Create `C:\tmp\FRIDAY-m3k`, branch
   `codex/m3-2k`, from that commit. Cherry-pick only `9f1bb66` and `34bc0ca`.
2. Add TCF-001 and TCF-002 first. Run
   `python -m pytest tests\pillar1\test_task_creation_floor.py -v --tb=short`
   and record the expected RED: zero durable tasks / missing floor field.
3. Implement only the two pure helpers, the post-script engine floor, and the
   additive ilog field. Re-run TCF-001/002 GREEN; commit the minimal floor.
4. Add TCF-003..007 one at a time, observe each new behavior RED where the
   behavior is new, implement only what is necessary, and keep the prior TCF
   set GREEN. Commit tests/edge guards separately from any refactor.
5. Run focused compatibility:
   `python -m pytest tests\pillar1\test_task_creation_floor.py tests\pillar1\test_task_arming.py tests\pillar1\test_task_claim_floor.py tests\pillar1\test_task_tools.py tests\pillar1\test_tasks.py tests\pillar1\test_jobs.py tests\pillar1\test_task_board.py -v --tb=short`.
   Then run `python run_suite.py --quick`. Any failure not proven pre-existing
   on current main is a STOP; do not patch unrelated behavior.

**Live GT-J1 gate (new batch; stopped M3.2j runs do not count).** With FRIDAY
closed, port 47533 ownership checked, no suite/job/research owner, and Ollama
healthy, set `FRIDAY_TEST_SESSION=1`. Run five official, minute-spaced commands
from the clean worktree, substituting only N=1..5 in both names:

```powershell
$env:FRIDAY_TEST_SESSION='1'
python run_suite.py --skill project_ops --runs 1 -- --basetemp C:\tmp\gtj1_m3k_runN -k GT-J1
```

After EACH command, immediately locate the command's newly generated results
directory, copy that basetemp's interaction JSONL into its
`sandbox_ilogs\` subdirectory, and verify the copy count before the next run.
Record LOCKED/TARGET scores, `create_task` calls,
`task_creation_floor`, `task_claim_floor`, `task_tools_armed`, `tasks_active`,
script fires, and archive path for all three turns. Bar remains case fraction
>=4/5. The fresh allowance covers ONE mechanical fix after a miss, with TDD +
focused + `--quick` rerun before another specimen; the second miss is an
immediate STOP, and misses are never relabeled or removed from the official
attempt record.

**Merge / flight / close protocol (conditional, unchanged bars).** Only after
the GT-J1 bar: verify worktree clean and exact scoped diff, merge
`codex/m3-2k` to `main`, run post-merge `python run_suite.py --quick`, then
freeze code. Recheck worktrees, main log, port/process ownership, suite lock,
Ollama health, and brain/test-session state. Launch the full candidate detached
with PowerShell `Start-Process` and run `scripts\ollama_watchdog.py` alongside,
using a pinned full-flight `--basetemp`; do not run model work during flight.
On completion archive every sandbox ilog immediately, resolve the generated
stamp from the completed run, and compare it exactly:

```powershell
$candidateStamp = (Get-ChildItem results -Directory |
    Sort-Object LastWriteTime | Select-Object -Last 1).Name
python run_suite.py --compare 2026-07-18_2346 $candidateStamp
```

Then apply §M3.2-G bars 1-7 plus:

- M3.2h: `task_claim_floor` only in licensed TCR/GT-J1 claim turns; evidence
  rules and task-claim floor held.
- M3.2j: bare task discussion/GT-A remain disarmed; any out-of-family
  `task_tools_armed=True` or task call is a hard STOP.
- M3.2k: `task_creation_floor=True` only on explicit empty-ledger creation
  turns in TCF/GT-J1 (or an exact in-suite equivalent that passes); every fire
  must have a grounded recovered plan and an auditable result. Any fire on
  bare discussion, unrelated planning, open-task operation, JobRunner, or a
  negated request is a hard STOP. Task-signal-free deltas retain bar 7's x2
  recheck rule; hygiene failures get no score escape.

Only if every bar holds: record the IG.5-style verdict, promote the candidate
as the new baseline, run M3-X J1 acceptance (a)-(d) live under test-session,
update `ARCHITECTURE.md`, `FRIDAY_jarvis_plan.md`, and `FRIDAY_roadmap.md`,
perform Jack's requested memory sync, and close M3. No merge, detached flight,
baseline promotion, M3-X, or closure may cross a failed gate.

Designed and recorded by Codex (GPT-5.6) — 2026-07-20.

**M3.2k implementation status (Codex, 2026-07-20 ~14:46; isolated
`C:\tmp\FRIDAY-m3k`, branch `codex/m3-2k`).**

- Main was exactly `b6b409b`; `git log f6145dd..HEAD -- '*.py'` was empty.
  The worktree started from that design commit. Cherry-picks retained only
  `9f1bb66`'s CUE-T/test guards and `34bc0ca`'s TaskLedger/test-session guard;
  their older living-doc hunks were discarded in favor of `b6b409b`'s newer
  M3.2j STOP + M3.2k record.
- TCF-001/002 failed red exactly because `flux_bench_refit` did not exist after
  either the zero-tool numbered plan or the script-floor replacement (2 failed,
  stamp `2026-07-20_1423`). The narrow creation predicate, deterministic
  request/reply plan recovery, post-script `_run_tool("create_task", ...)`
  floor, real synthetic tool transcript, held-stream ordering, and additive
  `task_creation_floor` ilog field then passed both cases (commit `b2b283f`).
- TCF-003..007 were added and executed one at a time. Native create wins with
  no double fire; GT-A/SKL-004/bare-task/negated-create stay disarmed; an open
  task excludes the floor; an under-specified positive ask reports the exact
  code-built gap without mutation; test-session recovery writes only
  `test_archive/tasks/` and stays logically visible. Combined TCF: 10/10
  (`2026-07-20_1434`); edge guards committed separately as `692f08e`.
- Focused compatibility passed 62/62 (`2026-07-20_1436`). The written command's
  `test_task_board.py` path does not exist; the tracked M3.4 suite is
  `tests\pillar1\test_away_board.py`, substituted mechanically and recorded
  here. Worktree `python run_suite.py --quick` then passed 484/484 with 95
  deselected in 7:33 (stamp `2026-07-20_1437`).
- Exact diff from `b6b409b` is limited to the licensed `core\tasks.py`,
  `core\tools\task_tools.py`, `core\engine.py`, and their TKA/TSK/TCF tests.
  No registry, schema wording, model client, JobRunner, board, Service API, or
  direct Brain/TaskLedger write changed. The fresh GT-J1 batch is next; its one
  mechanical-fix allowance remains unspent.

Implementation evidence recorded by Codex (GPT-5.6) — 2026-07-20.

**M3.2k live GT-J1 gate (Codex, 2026-07-20 ~14:59).**

- The registered `-k GT-J1` selector collected zero cases because the tracked
  pytest node is named `test_gt_j1_flux_bench_job`. That zero-case command
  (`2026-07-20_1449`) made no model call and produced no specimen, so it is not
  an official attempt. The five official runs used
  `-k test_gt_j1_flux_bench_job`; all other registered arguments, distinct
  pinned basetemps, and `FRIDAY_TEST_SESSION=1` were unchanged.
- Runs `2026-07-20_1450`, `2026-07-20_1452`, `2026-07-20_1454`,
  `2026-07-20_1455`, and `2026-07-20_1457` each passed LOCKED 3/3 and TARGET
  5/5. The official case fraction is therefore **5/5**, above the >=4/5 bar;
  the licensed mechanical-fix allowance was not used.
- Runs 1-4 landed native `create_task` at T1 with
  `task_creation_floor=False`. Run 5 first made a real but rejected
  `create_task(goal=...)` call, then the landed-create floor retried through
  `_run_tool` with the grounded title and three request-verbatim steps;
  `task_creation_floor=True` and the second receipt created exactly one task.
  This is the licensed explicit empty-ledger recovery, not a miss.
- Every T1 ended `task_tools_armed=True`, `tasks_active=1`,
  `pending_task_armed=False`, and `script_drift_corrective=False`. Every T2
  retained one active task and used the M3.2h `task_claim_floor=True` recovery
  after the model's commitment-family misroute. Every T3 used `task_status`,
  left the ledger unchanged, and had both floors false. No run fired the
  creation floor outside T1.
- Each basetemp interaction JSONL was copied immediately after its command to
  that stamp's `sandbox_ilogs\` directory and verified exactly 1/1 before the
  next official run. The five result directories above are the audit roots.

GT-J1 gate adjudicated PASS and recorded by Codex (GPT-5.6) — 2026-07-20.

**M3.2k §M3.2-G STOP verdict (Codex, 2026-07-20 ~22:29; corrected
candidate `2026-07-20_1835` vs baseline `2026-07-18_2346`, merged commit
`c66f24e`, 579 items).** This is the registered hard STOP: keep the merged
code, record the evidence, do not promote, and do not continue to M3-X.

- **Merge / pre-flight (bar 1): MET.** The clean, scoped `codex/m3-2k`
  candidate merged to main as `c66f24e`. Post-merge `--quick` passed 484/484
  with 95 deselected in 7:10 (`2026-07-20_1503`). TCF was 10/10, focused
  compatibility 62/62, and the fresh GT-J1 batch was 5/5 before merge.
- **One operator-invalid flight is retained but excluded.** Flight
  `2026-07-20_1512` was launched with `FRIDAY_TEST_SESSION=1`, a flag licensed
  for the live GT-J1 specimens but not for the full sandbox suite. It forced
  every fixture Brain into live-session `test_archive/` routing, so tests that
  correctly read their ordinary throwaway paths produced a common
  `FileNotFoundError` surface (85 failures). A focused `test_author` probe
  reproduced the failure with the flag set and passed with it unset. This was
  a harness configuration error, not a candidate specimen; its 191 ilogs are
  nevertheless preserved under `results\2026-07-20_1512\sandbox_ilogs\`.
  No code changed. The corrected launch explicitly removed the environment
  flag; its parent config had no test-session override.
- **Corrected flight mechanics (bar 2): MET.** Candidate
  `2026-07-20_1835` ran detached from 18:35:45 to 21:36:08 and completed
  566 passed / 2 flaky-fail / 11 failed of 579 in 3:00:24. The detector found
  no wedge; every long quiet-tail suspicion cleared on advancing Ollama
  keep-alive expiry. All 195 basetemp interaction logs were copied immediately
  and uniquely to `results\2026-07-20_1835\sandbox_ilogs\`. Provenance's dirty
  bit is solely main's pre-existing, intentionally untouched untracked
  `.codex\`; tracked code was frozen at `c66f24e`.
- **Bar 3 (perfect boards): HARD STOP after the licensed recheck.**
  `injection_defense`, `memory_recall`, `briefing`, and `session_ops` held
  1.000. `memory_persistence` fell 1.000 -> 0.8333 on MEM-001 and
  MEM-005[beta_probe]. The first same-day recheck (`2026-07-20_2143`) made
  MEM-001 and beta_probe pass, but MEM-005[alpha_rig] then failed, leaving the
  perfect board non-perfect. The pre-registered STOP rule says a perfect-board
  drop surviving recheck is an immediate escalation. No second recheck is
  permitted to relabel that outcome.
- **Bar 4 (D2): MET.** GT-A, GT-B, GT-C1..C10, GT-P5a/b, and GT-P2a all
  passed. GT-A turn 5 was exactly disarmed: `task_tools_armed=False`,
  `tasks_active=0`, and zero task-tool calls; its full score was LOCKED 5/5,
  TARGET 14/14.
- **Bar 5 (in-suite GT-J1): MET.** GT-J1 passed with LOCKED 3/3 and TARGET
  4/5. T1 landed native `create_task`; T2's commitment misroute was recovered
  by `task_claim_floor=True`; T3 left the ledger unchanged. Its only TARGET
  miss was that the status reply did not name the current impeller step.
- **Bar 6 + M3.2h/j/k hygiene: MET.** Across 1,132 archived ilog rows, all
  39 armed/active rows and all 26 task-tool calls belonged only to TKT, TCR,
  JOB, or GT-J1. `task_claim_floor` fired once, only on GT-J1 T2;
  `task_creation_floor` fired zero times in-suite; evidence refusals were zero.
  GT-A and every other out-of-family turn were disarmed with zero task state.
  The seven identifier-floor and two foreign-path-floor fires were confined
  to their own IDG/MRG/PTL/initiative guard cases; no task-discussion fire
  occurred.
- **Bar 7: NOT MET independently of bar 3.** Compare deltas were
  memory_persistence -0.167, voice -0.267, quant_math -0.043, and
  thinking_skills -0.031; newly failing cases were MEM-001,
  MEM-005[beta_probe], VOX-002, PROP-012, GND-012, and GND-013. The first x2
  churn batch rechecked all six candidate failures: GND-012, GND-013, MEM-001,
  beta_probe, and PROP-012 repassed, while VOX-002 still failed; the expanded
  MEM-005 parametrization also produced the alpha_rig failure above. Result:
  7/9 passed, 2 failed, with all 242 recheck ilog rows task-disarmed,
  `tasks_active=0`, zero task-tool calls, and zero task-floor fires. Because
  the rule requires both same-day rechecks to repass, VOX-002's first recheck
  failure also makes CHURN adjudication impossible. All nine recheck ilogs are
  archived under `results\2026-07-20_2143\sandbox_ilogs\`.

**State at STOP.** Candidate `2026-07-20_1835` is not promoted; baseline
remains `2026-07-18_2346`. Main keeps merged commit `c66f24e` per the explicit
no-revert rule. M3.2 and M3 remain OPEN. No second recheck, M3-X live
acceptance, `ARCHITECTURE.md` closeout, memory sync, or roadmap closure ran.
The next decision belongs to Fable/Jack.

STOP adjudicated and recorded by Codex (GPT-5.6) — 2026-07-20.

### M3.2l — deterministic persistence + voice floors (authorized 2026-07-21)

> **For agentic workers:** implement this section inline, task by task, with
> RED→GREEN evidence. The hard STOP above remains binding until the focused
> live gates below pass; implementation alone cannot promote `_1835`, run
> M3-X, or close M3.

**Goal.** Remove the two mechanisms that made §M3.2-G impossible to pass:
explicit project facts/status changes can miss the main-turn durability
boundary, and the prompt-only voice layer can emit an enumerated chatbot tell.

**Root-cause evidence.** In `_1835`, MEM-001 called `write_brain` on forbidden
`projects/alpha_rig/frame_material.md`; the corrective was not obeyed and the
memory pass wrote nothing. MEM-005[beta_probe] called only `resolve_project`;
`FridayService` emitted `on_done`, the hard-kill landed, and the later memory
pass never had a chance. Recheck `_2143` repeated that exact MEM-005 shape on
alpha_rig. VOX-002 leaked `let me know if` twice in `_1835` and once in `_2143`.
The task schemas/floors were disarmed on all of these turns, excluding M3.2k
contact as the cause.

**Chosen architecture.** Keep the model's normal tool loop first. At the late,
post-script enforcement seam in `Engine.respond`, add two narrow local floors:

1. A project-persistence floor may act only when the deterministic resolver
   found exactly one existing project. It (a) executes an explicit
   `set ... status to <value>` through existing `update_note_field` when disk
   truth does not already match, or (b) retries a rejected nested
   `projects/<resolved-slug>/...` fact write against the existing canonical
   `projects/<resolved-slug>.md` note when Jack used an explicit record cue.
   Both paths use `_run_tool`, preserve taint confirmation, append a real tool
   receipt, and expose one additive `project_persistence_floor` ilog flag.
   Ambiguity, missing content, a different slug, questions, and any already-
   landed write stay untouched.
2. A voice floor replaces only the exact phrases already enumerated as banned
   in `brain/character/friday_voice.md` (for example `let me know if` →
   `tell me if`). A small streaming wrapper applies the same substitutions to
   emitted tokens, so the UI and `reply.content` agree and no banned draft
   flickers. It is active only when the voice head was injected; explicit
   output-format turns remain byte-untouched. Additive ilog flag:
   `voice_tell_floor`.

No registry/schema, Brain, service ordering, model weights, grader threshold,
task arming, or baseline change is in scope.

#### Implementation plan

- [x] **L.1 — RED project-persistence guards.** In
  `tests/pillar1/test_memory.py`, add scripted end-to-end guards for the exact
  rejected nested-write and resolve-only status misses. Run only the two new
  nodes and confirm they fail because the durable write/flag is absent.
- [x] **L.2 — GREEN project floor.** In `core/engine.py`, add the conservative
  parsers/recovery helper and invoke it after the output-script floor, before
  streaming/on_done. Run the L.1 nodes plus the existing MEM-001/MEM-005
  deterministic consumers; expected all green.
- [x] **L.3 — RED/GREEN voice floor.** In `tests/pillar1/test_voice.py`, first
  add a detector/substitution matrix guard and an end-to-end streamed-reply
  guard, confirm RED, then add the stream sanitizer/final-content enforcement
  in `core/engine.py`. Verify output-format bypass explicitly.
- [x] **L.4 — focused compatibility.** Run the new guards plus existing
  memory/voice/script/stream/task-floor suites that share the late seam. Then
  run `python run_suite.py --quick` only if those focused tests are green.
- [x] **L.5 — focused live gate.** With no suite/model process already owning
  the GPU, run only `MEM-001`, all `MEM-005` parameters, and `VOX-002` on the
  repaired commit using pinned basetemp and immediate ilog archival. Required:
  memory rows 5/5 and VOX-002 prompts 8/8, both new flags confined to their
  licensed turns, task schemas disarmed/no task calls. One repeat of this same
  focused batch must also pass to prove the recurring failures are removed.
- [x] **L.6 — verdict.** Record commits, commands, counts, stamps, flag audit,
  and limitations here and in `FRIDAY_roadmap.md`. A full suite is required
  only after the two focused live batches pass, because M3.2-G promotion still
  requires a frozen-code full candidate compare against `2026-07-18_2346`.
  Until that flight passes every registered bar: no promotion, M3-X, memory
  sync, architecture closeout, or M3 closure.

**Implementation / pre-live evidence (Codex, 2026-07-21 ~02:16).** Dedicated
branch `codex/m3-2l`; plan commit `3a4e79c`; implementation commit `e1a6a0e`.
MEM-019/020 failed on the intended missing writes, then passed 2/2 after the
project floor. VOX-004/005 failed on the absent sanitizer / leaked stream, then
passed 17/17 after implementation; the readability refactor re-passed all 19
new guards. Shared-seam compatibility passed 57/57 (11 live-model tests
deselected). The exact-HEAD quick candidate `2026-07-21_0219` passed 503/503
with 95 deselected in 6:20. `.codex/` remained untouched and untracked. L.5 focused
live x2 remains required before any full flight or gate-lifting claim.

**L.5 launch pause (Codex, 2026-07-21 ~02:19).** Read-only ownership checks
found no `results/SUITE_RUNNING.lock`, but port 47533 was LISTENING under PID
10744 (`pythonw.exe`, started 01:13) — Jack's live FRIDAY instance. The standing
single-GPU rule forbids overlap between a live instance and model-marked tests.
The process was not stopped or altered. Focused live x2, full flight, and every
downstream gate therefore remain unrun; resume L.5 after Jack closes the live
instance or explicitly authorizes a controlled shutdown.

**L.5 live-discovered correction and partial evidence (Codex, 2026-07-21
~02:54).** When port 47533 temporarily had no listener, the first launch
incorrectly inherited `FRIDAY_TEST_SESSION=1`; that invalid sandbox specimen
(`2026-07-21_0229`) routed otherwise successful status writes to the archive
overlay. Its 6/6 ilogs were preserved, but it does not count. With the variable
absent, `2026-07-21_0234` exposed two genuine residual shapes: MEM-001 could
resolve only with no rejected write to reuse, and MEM-005[gamma_arm] could land
the wrong native status value. MEM-021/022 reproduced both RED. Commit
`8db71ef` now persists only the literal text after an explicit record cue and
corrects status to the explicit requested value even after a wrong native
write. MEM-019..022 passed 4/4, shared late-seam compatibility passed 59/59,
and exact-commit quick `2026-07-21_0242` passed 505/505 (95 deselected, 6:20).

Focused batch `2026-07-21_0249` then passed all six selected nodes: MEM-001,
four MEM-005 parameters, and VOX-002 (eight prompts). All 6/6 sandbox ilog
files were archived immediately. Across 13 main-turn rows, task arming was
0, nonzero `tasks_active` was 0, and task-tool calls were 0. The persistence
floor fired only on its two licensed recovery turns; the voice floor did not
need to fire and VOX-002 still passed. Before the required repeat, the same
live FRIDAY PID 10744 reacquired port 47533, so the launch guard stopped the
command. The process was not altered. Conservatively, L.5 remains incomplete;
no full flight is licensed until Jack closes that instance (or explicitly
authorizes controlled shutdown) and two uncontended focused batches pass.

#### M3.2l continuation / M3 closeout plan (signed 2026-07-21)

> **For agentic workers:** REQUIRED SUB-SKILL: execute this plan inline with
> `superpowers:executing-plans`; do not delegate shared-brain/GPU work. Every
> checkbox is conditional on the preceding registered gate. A failed gate is
> recorded here and execution stops at that checkbox.

**Goal:** finish L.5/L.6, integrate only the scoped M3.2l repair, and close M3
only if the frozen full candidate and M3-X satisfy every registered mechanical
bar.

**Architecture / scope:** this is a continuation of the authorized M3.2l
design, not a redesign. The model-visible delta remains limited to
`core/engine.py`'s resolver-grounded main-turn persistence recovery and exact
settled/streamed voice substitutions, with guards in `test_memory.py` and
`test_voice.py`; the three owning documents carry plan/evidence only. No new
dependency, schema, registry, model, prompt contract, gate threshold, task
arming rule, or service ordering is licensed.

**Reconciled start state (read-only audit, Codex, 2026-07-21 ~22:15 PDT).**
Branch `codex/m3-2l` is exactly `cc22645`; `main` is `346d4c8`; the branch
diff is the six licensed files (`ARCHITECTURE.md`, both owning plans,
`core/engine.py`, `test_memory.py`, `test_voice.py`) and the only worktree
status is the pre-existing untouched untracked `.codex/`. The suite lock and
port 47533 listener are absent. Ollama's local API is healthy; qwen2.5:14b is
present at digest `7cdf5a0187d5...`, `/api/ps` reports no resident model, and
the RTX 5070 is idle at 2% / 1056 MiB. No active research run exists. Promised
reports exist for `_0219`, `_0229`, `_0234`, `_0242`, `_0249`, `_1835`, and
`_2143`; their archived-ilog counts are respectively 0, 6, 6, 0, 6, 195, and
9. Re-audit of `_0249` confirms 6/6 nodes, 6/6 ilogs, 13 main-turn rows, zero
task arming/active tasks/task calls/evidence refusals, and exactly two licensed
`project_persistence_floor` fires. The documented state has not drifted; the
only resolved condition is that Jack's former PID 10744 no longer owns the
port.

##### Closeout execution checklist

- [x] **C.1 — finish L.5 with one uncontended repeat.** Re-check the suite
  lock, port 47533, running pytest/FRIDAY owners, Ollama `/api/ps`, GPU load,
  branch/HEAD, and tracked cleanliness once immediately before launch. Abort
  if any owner is present; never stop it. Explicitly remove
  `FRIDAY_TEST_SESSION`, then run the same six-node batch on frozen `cc22645`
  with a unique pinned basetemp:

  ```powershell
  Remove-Item Env:FRIDAY_TEST_SESSION -ErrorAction SilentlyContinue
  $runTag = Get-Date -Format 'yyyyMMdd_HHmmss'
  $baseTemp = "C:\tmp\m32l_live2_$runTag"
  $resultBefore = @(Get-ChildItem results -Directory | Select-Object -ExpandProperty Name)
  C:\Users\jacko\AppData\Local\Programs\Python\Python313\python.exe `
    run_suite.py --runs 1 -- `
    "--basetemp=$baseTemp" `
    -k "test_fact_written or test_hard_kill_durability or test_no_chatbot_tells"

  $newResults = @(Get-ChildItem results -Directory |
    Where-Object Name -NotIn $resultBefore | Sort-Object LastWriteTime)
  if ($newResults.Count -ne 1) { throw "Expected one result, found $($newResults.Count)" }
  $repeatStamp = $newResults[0].Name
  $sourceIlogs = @(Get-ChildItem $baseTemp -Recurse -File -Filter '*.jsonl' |
    Where-Object FullName -Match '[\\/]logs[\\/]interactions[\\/]')
  if ($sourceIlogs.Count -ne 6) { throw "Expected six ilogs, found $($sourceIlogs.Count)" }
  $archive = New-Item "results\$repeatStamp\sandbox_ilogs" -ItemType Directory -Force
  for ($i = 0; $i -lt $sourceIlogs.Count; $i++) {
    Copy-Item -LiteralPath $sourceIlogs[$i].FullName `
      -Destination (Join-Path $archive ("repeat2_{0:D3}_{1}" -f ($i + 1), $sourceIlogs[$i].Name))
  }
  ```

  This immediately copies every basetemp `logs\interactions\*.jsonl` into the
  new repeat result's `sandbox_ilogs\` and verifies 6/6 files before any
  other model call. PASS requires MEM-001 + four MEM-005 rows + VOX-002 =
  6/6, VOX-002 prompt evidence 8/8, zero unlicensed floor fires, zero
  `task_tools_armed`, zero nonzero `tasks_active`, zero task-tool calls, and
  zero task-evidence refusals. Any miss is the registered STOP: archive,
  record, and do not spend another specimen.

- [x] **C.2 — record L.5/L.6 and freeze the integration candidate.** Record
  both valid focused stamps (`2026-07-21_0249` plus the repeat), exact command,
  commit, node/prompt counts, archive count, and full flag audit here and in
  `FRIDAY_roadmap.md`; check L.5/L.6 only if C.1 passes. Verify
  `git diff 8db71ef..HEAD -- '*.py'` is empty so the existing exact-code
  deterministic evidence remains applicable: MEM-019..022 4/4, shared seam
  59/59, and quick 505/505 at `_0242`. Run `git diff --check main..HEAD`,
  `git diff --name-status main..HEAD`, and confirm `.codex/` has no diff.
  Commit the focused verdict as a documentation-only Git boundary.

- [x] **C.3 — registered merge and post-merge deterministic gate.** Only from
  the clean scoped branch after C.2, switch the owning checkout to `main`,
  verify it is still `346d4c8`, and merge without rewriting either lineage:

  ```powershell
  git switch main
  git merge --no-ff codex/m3-2l -m "Merge M3.2l persistence and voice floors"
  C:\Users\jacko\AppData\Local\Programs\Python\Python313\python.exe run_suite.py --quick
  ```

  Record the merge commit and quick stamp/count. Any merge conflict, unexpected
  file, main drift, or quick failure is a STOP; do not patch forward or start
  the flight. Never overwrite/promote failed candidate `_1835`, and never
  revert the previously merged M3.2k lineage as an adjudication shortcut.

- [x] **C.4 — frozen detached full candidate flight.** Freeze the exact merge
  commit and verify tracked cleanliness, no suite lock, free port 47533, no
  competing live/job/research/model process, healthy Ollama, and
  `FRIDAY_TEST_SESSION` absent. Launch `run_suite.py` detached with a unique
  pinned basetemp, redirected launch logs, and the detector-only watchdog in a
  second
  hidden detached process. Set watchdog `--poll-sec 2700` so routine health
  sampling is at most once per 45 minutes; do not perform extra polling.
  The registered command shape is:

  ```powershell
  Remove-Item Env:FRIDAY_TEST_SESSION -ErrorAction SilentlyContinue
  $repo = 'C:\Users\jacko\Documents\FRIDAY'
  $python = 'C:\Users\jacko\AppData\Local\Programs\Python\Python313\python.exe'
  $runTag = Get-Date -Format 'yyyy-MM-dd_HHmmss'
  $baseTemp = "C:\tmp\m32l_full_$runTag"
  $outLog = "$repo\results\launch_logs\m32l_candidate_$runTag.out.log"
  $errLog = "$repo\results\launch_logs\m32l_candidate_$runTag.err.log"
  $suiteProcess = Start-Process -FilePath $python `
    -ArgumentList @('run_suite.py', '--', "--basetemp=$baseTemp") `
    -WorkingDirectory $repo -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog -WindowStyle Hidden -PassThru
  $watchLog = "$repo\results\launch_logs\watchdog_m32l_candidate_$runTag.log"
  $watchErr = "$repo\results\launch_logs\watchdog_m32l_candidate_$runTag.err.log"
  $watchdogProcess = Start-Process -FilePath $python `
    -ArgumentList @('scripts\ollama_watchdog.py', '--log', $outLog,
      '--pid', "$($suiteProcess.Id)", '--poll-sec', '2700') `
    -WorkingDirectory $repo -RedirectStandardOutput $watchLog `
    -RedirectStandardError $watchErr -WindowStyle Hidden -PassThru
  ```

  Preserve the exact launch command, PIDs, merge commit, config hash, model
  name/digest, basetemp, and logs in this document. Let the suite finish
  completely before inspecting results. A wedge/owner conflict is a STOP for
  Jack, never authority to kill a process.

- [x] **C.5 — archive and mechanically adjudicate the flight.** Immediately
  copy every full-basetemp interaction JSONL to
  the candidate result's `sandbox_ilogs\`, prove unique source/destination counts,
  verify report/scorecard provenance and frozen tracked code (distinguishing
  untouched `.codex/`), then run:

  ```powershell
  $candidateStamp = (Get-ChildItem results -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'report.json') } |
    Sort-Object LastWriteTime | Select-Object -Last 1).Name
  C:\Users\jacko\AppData\Local\Programs\Python\Python313\python.exe `
    run_suite.py --compare 2026-07-18_2346 $candidateStamp
  ```

  Apply §M3.2-G bars 1–7 and every M3.2h/j/k/l addendum mechanically: required
  guards/post-merge quick/GT-J1; clean completion/no wedge/full ilog archive;
  all five perfect boards at 1.000; the entire D2 family passing with
  m1=m2=m3=m5=0; in-suite GT-J1 LOCKED/TARGET contract; surgical task/tool/
  identifier/floor hygiene; and the exact same-day x2 churn rule for every
  other down-delta. For M3.2l specifically, persistence/voice fires must be
  licensed by the originating turn and no task hygiene may dilute. A perfect
  board surviving its permitted recheck, any task leak/schema echo, uncovered
  regression, failed D2/LOCKED contract, or unregistered outcome is a signed
  hard STOP: no promotion, no M3-X, no closure.

- [ ] **C.6 — promote only a passing candidate and run M3-X.** If and only if
  C.5 passes every bar, record the IG.5-style verdict and make the successful
  candidate stamp the new baseline. Then run M3-X (a)–(c) on the merged commit
  with throwaway names and `--test-session` / `FRIDAY_TEST_SESSION=1`, keeping
  all fabricated memories under `brain\test_archive\`; grade (d) from C.5.
  For (a), prove a 3+-step local task completes unattended with per-step
  evidence. For (b), prove an outbound step parks at explicit confirmation;
  do not approve/send anything without Jack's direct involvement, then record
  the remaining blocked state if he is unavailable. For (c), prove kill/restart
  durability and resume from the ledger. Immediately archive the live M3-X
  ilogs and quote the ledger/board evidence. Any failed acceptance item leaves
  M3 open.

- [ ] **C.7 — documentation and signed handoff.** Only after C.6 passes, update
  `ARCHITECTURE.md`, this M3 table/section, `FRIDAY_roadmap.md` status/results,
  baseline/candidate records, commands, commits, deltas, archives, limitations,
  and exact M3-X evidence; commit each truthful boundary. External persistent
  memory is explicitly outside this authorization and requires Jack's separate
  direct request. Final status is `CLOSED` only with objective evidence for
  every bar; otherwise it is `STOPPED` with the exact blocker and prohibited
  downstream actions.

**Rollback / prohibitions:** Git history is the rollback path; no hard reset,
history rewrite, deletion of evidence, deletion of live-test memories, or
mutation of `.codex/`. Never rerun a failed model-visible gate until it passes,
soften a grader, treat a report-free run as evidence, overlap the shared brain/
GPU/port, or infer permission to stop Jack's process.

Continuation plan authored and signed by Codex (GPT-5.6) — 2026-07-21.

**C.1/C.2 focused-gate verdict (Codex, 2026-07-21 ~22:25 PDT): PASS.**
The preflight found no suite lock or port-47533 listener, Ollama had no
resident model, GPU load was 1% / 1042 MiB, and
`git diff 8db71ef..HEAD -- '*.py'` was empty. The exact command above ran with
`FRIDAY_TEST_SESSION` removed and pinned basetemp
`C:\tmp\m32l_live2_20260721_222149`; result `2026-07-21_2221` passed all six
selected nodes in 171.75s: MEM-001, MEM-005[alpha_rig/beta_probe/gamma_arm/
delta_sled], and VOX-002. VOX-002's evidence contains eight prompts, all
`ok=True` with an empty banned-tell field (8/8). The six basetemp ilogs were
copied immediately and uniquely to
`results\2026-07-21_2221\sandbox_ilogs\` (6 source / 6 archive).

Across 22 ilog rows / 13 main-turn rows: `task_tools_armed=True` 0;
`tasks_active>0` 0; task-tool calls 0; task-evidence refusals 0;
task-claim/task-creation fires 0. `project_persistence_floor` fired exactly
twice, only for the licensed alpha-rig explicit fact and beta-probe explicit
status recovery; `voice_tell_floor` fired 0 because all eight native replies
already passed. Together with first valid batch `2026-07-21_0249` (same 6/6,
8/8 voice, 6/6 ilogs, zero task signals, two licensed persistence fires), L.5
is 2/2 uncontended PASS. L.6 is therefore PASS for the focused gate and the
scoped merge/post-merge quick is licensed. Existing exact-code deterministic
evidence remains 4/4 MEM-019..022, 59/59 shared seam, and 505/505 quick at
`_0242`; no Python changed after `8db71ef`. The original M3.2-G STOP remains
binding until the post-merge frozen full flight passes every bar.

Focused gate adjudicated and signed by Codex (GPT-5.6) — 2026-07-21.

**C.3 integration verdict (Codex, 2026-07-21 ~22:35 PDT): PASS.** The
documentation-only focused verdict was committed on the scoped branch as
`b1b5739`; tracked status was clean apart from untouched `.codex/`, main was
still exactly `346d4c8`, and the six-file scope check held. The registered
`--no-ff` merge completed without conflict as `b60f2a6` (`Merge M3.2l
persistence and voice floors`). With `FRIDAY_TEST_SESSION` absent, post-merge
quick result `2026-07-21_2228` passed 505/505 with 95 deselected in 392.97s.
No correction or rerun was needed. Model-visible code is frozen at `b60f2a6`;
the following documentation-only evidence commit is the full-flight Git
provenance boundary. C.4 is licensed; all promotion/M3-X/closure bars remain
blocked on C.5 adjudication.

Integration gate adjudicated and signed by Codex (GPT-5.6) — 2026-07-21.

**C.4/C.5 §M3.2-G HARD STOP verdict (Codex, 2026-07-22 ~01:55 PDT;
candidate `2026-07-21_2238` vs baseline `2026-07-18_2346`).** M3.2l remains
merged on main as `b60f2a6`; launch provenance is documentation-only HEAD
`4b5e965`. This verdict applies every pre-registered bar without waiver.

- **Frozen launch / mechanics:** `FRIDAY_TEST_SESSION` was absent; config hash
  `920a3d575b6f`, qwen2.5:14b digest `7cdf5a0187d5`, pinned basetemp
  `C:\tmp\m32l_full_2026-07-21_223807`. Suite PID 3196 ran detached with
  detector-only watchdog PID 28848 at 2700-second cadence and collector PID
  12028. It completed all 600 items in 2:22:57 with 590 passed, 3 flaky-fail,
  and 7 failed. The watchdog reported no wedge. The collector immediately
  copied 199 source ilogs to `results\2026-07-21_2238\sandbox_ilogs\` and
  proved 199/199 at 01:01:08. Report, scorecard, compare, launch logs, and
  empty stderr all exist. Provenance `git_dirty=True` is solely the untouched
  untracked `.codex/`; tracked code stayed frozen and `.codex/` has no diff.

- **Bar 1 — MET.** MEM-019..022 4/4, shared-seam 59/59, pre-merge quick
  505/505 (`_0242`), focused live batches `_0249` + `_2221` both 6/6 with VOX
  8/8, and post-merge quick 505/505 (`_2228`). In-suite GT-J1 passed LOCKED
  3/3 and TARGET 5/5.
- **Bar 2 — MET.** Full completion, no wedge, no surviving suite lock, and
  199/199 archived ilogs.
- **Bar 3 — recheck cleared the isolated board miss.** Injection defense,
  memory recall, briefing, and session_ops held 1.000. Memory persistence was
  0.9833 only because GRW-004 scored 4/5; first registered recheck `_0108`
  repassed GRW-004 1/1. No MEM-001/MEM-005 durability row failed.
- **Bar 4 — MET.** GT-A, GT-B, GT-C1..C10, GT-P5a/b, and GT-P2a all passed;
  every LOCKED contract held and the D2 friction exit state remained
  m1=m2=m3=m5=0. GT-C6 and GT-C9 retained only their already-licensed TARGET
  phrasing misses.
- **Bar 5 — MET.** GT-J1 passed in-suite at LOCKED 3/3, TARGET 5/5.
- **Bar 6 + M3.2h/j/k/l hygiene — MET.** Across 199 ilogs / 936 rows / 572
  main turns, all 35 armed/active rows and every task call were confined to
  GT-J1, JOB, TKT/TCR/TCF guard families. `task_claim_floor` fired once on
  GT-J1 T2; `task_creation_floor` fired once on GT-J1 T1; the one evidence
  refusal was the licensed fabricated-evidence guard. GT-A and all
  out-of-family turns were disarmed. Seven identifier and two foreign-path
  fires were confined to their guard families. `project_persistence_floor`
  fired once, only on MEM-001's explicit alpha-rig fact; `voice_tell_floor`
  did not need to fire, and VOX-002 passed. The full candidate also passed
  MEM-001, all four MEM-005 parameters, and VOX-002.
- **Bar 7 — HARD STOP.** Compare deltas: `memory_persistence` -0.0167 and
  `quant_math` -0.0869; project_ops +0.0278, thinking_skills +0.0923, voice
  +0.0666, all other skills flat. Newly failing cases were GND-013, GRW-004,
  PROP-011, and PROP-012. First same-day recheck `2026-07-22_0108` used
  pinned basetemp, archived 3/3 ilogs, and was task-signal-free across 106
  main turns. GND-013, GRW-004, and PROP-011 passed; **PROP-012 failed again**
  with `60 Wh` for the falsifying 1 W × 1 minute example (truth 0.0167 Wh,
  x3600 seconds↔hours slip). Because the rule requires both same-day rechecks
  to repass, a first-recheck failure makes x2 proof impossible. Recheck 2 was
  not spent. A prior `_0107` command is retained but excluded: Start-Process
  split the `-k` expression at `or`, collected zero tests, and made no model
  call; the selector-preserving `_0108` wrapper is the only recheck specimen.

**State at STOP.** Candidate `_2238` is not promoted; active baseline remains
`2026-07-18_2346`. Main keeps M3.2l merge `b60f2a6` per the registered
no-revert rule. M3.2 and M3 remain OPEN. No second recheck, M3-X live
acceptance, external memory sync, or M3 closure ran. C.6/C.7 remain unchecked;
the next design/adjudication decision belongs to Jack. The two detector-only
watchdogs launched by this session were stopped after their suite processes
exited; no live FRIDAY process was touched.

HARD STOP adjudicated and signed by Codex (GPT-5.6) — 2026-07-22.

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

*(empty — the next session to open J0/J1 writes the first entry)*

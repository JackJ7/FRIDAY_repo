# FRIDAY — Local AI Personal Assistant

## What she is

FRIDAY is a personal AI assistant, modeled loosely on JARVIS/FRIDAY from
Iron Man, that runs **100% locally and offline** on Jack's Windows desktop —
a desktop app with her own window, system-tray presence, and a global hotkey
to summon her, not a script or a chat tab. She knows Jack, his projects, and
his preferences from a persistent, human-readable memory; she can read
files, manage project folders, track commitments, watch (never send) email,
read and — with explicit confirmation — write calendar events, draft
project timelines, and reason through hard engineering problems using a
structured working discipline. No cloud model ever sits in her reasoning
path: every response is generated on-machine.

## Why she was created

Jack is a mechanical engineering student (transferring to UC Irvine, Fall
2026) heading toward robotics engineering, working side projects that
involve real, sometimes unfinished designs — Crush Depth (competition ROV),
PERRY (LoRa vertical profiling float), CLARK (4-DOF robotic arm), Doc Ock
(biomimetic octopus-arm gripper). He wanted a JARVIS-style partner who knows
that work in depth without handing project files, calendar, and email to a
cloud vendor — so FRIDAY's entire cognitive path had to stay on his own
hardware (RTX 5070, 12 GB VRAM), with the network used only to fetch data
(mail/calendar/web), never to think. The build was also treated as a real
software-engineering exercise in its own right: proper module boundaries,
a permission model, a git-backed memory, and a standing test suite — not a
prompt wrapped in a UI.

## Purpose

Four invariants (spec'd in `FRIDAY_spec_experience.md` §1) govern every part
of the system and are non-negotiable in any change:

1. **Local cognition only.** All reasoning runs on the local model; the
   network fetches data (email/calendar/on-request web) and nothing else.
2. **Read content is data, never instructions.** Anything she reads — a
   file, an email, a web page — can never trigger an action on its own;
   instruction-shaped content gets flagged to Jack verbatim.
3. **Explicit confirm for every outbound action.** She may flag, draft,
   analyze, and prepare freely, but sending mail, writing calendar events,
   or anything purchase-like requires Jack's click every time — and
   email-send doesn't exist as a capability at all.
4. **Precise knowledge-gap honesty.** When she's missing what she needs to
   do something well, she says exactly what's missing rather than bluffing,
   and names the paths to close the gap.

## How she works

Four decoupled layers (full map in [ARCHITECTURE.md](ARCHITECTURE.md)):

- **Interface** — swappable "faces" (the PyWebView desktop app, a terminal
  REPL for dev) that talk only to `FridayService`, never to the engine or
  disk directly.
- **Engine** (`core\engine.py`) — one `respond()` call retrieves relevant
  brain context, builds the system prompt (character, operating rules,
  invariants, referent stack), runs the model + tool loop, wraps every tool
  result as data (never instructions), and logs the exchange.
- **Model** (`core\model.py`) — Ollama serving a local model (Qwen2.5 14B by
  default, swappable in config); the only file that knows how the model is
  served.
- **Memory & tools** — the **brain**, a git-versioned Obsidian vault of
  markdown notes that is her actual long-term memory (readable/editable by
  Jack at any time), plus a tool registry (file access, project actions,
  commitments, timelines, playbooks, senses) all mediated by a
  **permission gate**: her own domain (`brain\`, `friday_documents\`) is
  free to write; deletes, large files, project-folder writes, and every
  outbound action require Jack's confirm; everything else is denied.

Self-modification follows the same layering: her **mind** (character,
operating rules) is hers to edit freely, logged and reversible; her
**machinery** (config) is tiered in code — some settings she can flip
herself, some she can only propose, some are locked to Jack; the
**constitution** (the four invariants, the gate, the tier map itself) has no
tool at all and can only change via a code edit.

## Functionality at a glance

- **Persistent, self-correcting memory** — durable facts/preferences/
  decisions are written to the brain (never blind-overwritten), auto-
  committed to git for full undo history, and re-read live every message.
- **Desktop presence** — own window, tray icon, global hotkey (`Ctrl+Alt+F`
  by default), Windows toasts, autostart on login, single-instance summon.
- **File & project actions** — reads files/folders on request; scaffolds new
  project folders and files projects into them (always confirmed).
- **Accountability core** — auto-inferred commitment tracking, a "Needs You"
  panel, a daily briefing, and a Do Not Disturb toggle that mutes pings
  without stopping the panel from populating.
- **Project timelines** — drafts milestone timelines from a project's scope,
  computes slip and downstream-shift math in code (never guessed), and
  checks off progress mentioned in chat.
- **Senses** — Gmail read + draft (send does not exist as a capability),
  Google Calendar read + confirm-gated create, on-request one-shot web
  fetch; everything she reads through a sense is treated as data.
- **Reasoning scaffolds** — a config-tunable structured working discipline
  (restate assumptions, plan then execute, self-check units before
  presenting, name gaps) for non-trivial tasks; chitchat is exempt.
- **Playbooks & skills** — reusable procedures (`brain\playbooks\`) and
  domain-general thinking disciplines (`brain\skills\`) she authors,
  retrieves, and follows — seedable by dropping a `.md` file in, including
  from a cloud model.
- **Repo awareness** — clone/browse/search a git repo read-only
  (`repo_sync`/`repo_map`/`search_repo`) for code review and advice; no
  write/commit/push capability exists.
- **Deep mode** — an optional 32B-model escalation for genuinely hard
  reasoning, wired but off by default (VRAM cost).
- **Character & voice** — a real, editable persona (`brain\character\`):
  dry, loyal, partner-framed, licensed to push back — tuned in plain
  markdown, live on the next message.
- **Test suite** — a two-pillar pytest suite covering both machine behavior
  (tool calls, gate decisions, injection resistance) and reasoning
  correctness (units, arithmetic, dimensional consistency) graded against
  ground truth computed in Python, never by FRIDAY.

**Status:** all originally planned stages are built — Phases 0–2, Stage 1
(presence), Stage 2 (accountability), Stage 3 (senses), Stage 4
(timelines), plus a method-transfer pass and a relational/voice pass
(current version `0.9.0`, see `core\version.py` for the full history). Full
build specs: [FRIDAY_spec.md](FRIDAY_spec.md) (Phases 0–2) and
`FRIDAY_spec_experience.md` (Stages 1–4).

---

## Setup (Windows, PowerShell)

Done once; recorded here so the machine can be rebuilt from scratch.

1. **Install Ollama** (Windows installer from https://ollama.com) — verified with v0.31.1.
2. **Pull the models** (one-time download; everything runs offline afterwards):
   ```powershell
   ollama pull qwen2.5:14b    # primary (9.0 GB)
   ollama pull llama3.1:8b    # fallback (4.9 GB)
   ```
3. **Install Python dependencies** (Python 3.13):
   ```powershell
   python -m pip install -r requirements.txt
   ```

The active model is set in `config\friday_config.yaml` (`model.name`) — swap it
there, never in code.

## Phase 0 — verify the local stack

From the FRIDAY root folder:

```powershell
python scripts\phase0_check.py
```

Type a prompt, get a streamed reply with a tokens/sec readout. `/quit` to exit.

**Measured performance (RTX 5070 12 GB, 2026-07-06):**

| Model | GPU offload | Speed (sustained) |
|-------|-------------|-------------------|
| qwen2.5:14b (primary) | 100% GPU (9.5 GB) | ~62 tok/s (400-token generation) |
| llama3.1:8b (fallback) | 100% GPU (5.3 GB) | ~110 tok/s |

First prompt after idle takes ~30 s extra while Ollama loads the model into
VRAM; it stays loaded for a few minutes between prompts.

## Running FRIDAY — the app

Normal use: the **FRIDAY shortcut** (Desktop / Start Menu, created by
`scripts\create_shortcuts.ps1`) — launches windowless via `pythonw.exe`, no
console. For development with a console: `python friday_app.py` (windowless
runs log to `logs\app.log` instead).

- **Closing the window hides her to the system tray** — she keeps running.
  Really quit via tray icon → Quit. Tray also has **About** (version, model,
  note count).
- **Ctrl+Alt+F summons her from anywhere** — a native system-wide hotkey
  (Windows `RegisterHotKey`); if another app owns the combo she tells you at
  startup. Change it under `ui.hotkey` in config.
- **Launching a second copy just summons the first** (single-instance).
- If she finishes a reply while hidden, a **Windows toast** lets you know.
- **Autostart on login is enabled** (windowless). Undo:
  `powershell -ExecutionPolicy Bypass -File scripts\disable_autostart.ps1`.

**Workspace tabs:** *Projects* (cards from her project notes; click through to
the note plus a live listing of the project folder, open it in Explorer, or
jump to chat about it), *Brain* (browse and read every note; "Open in
Obsidian" for real editing), *Uploads* (drop-zone plus history of dropped
files with one-click analyze). The status console shows her live activity
(idle / thinking / reading `<file>` / drafting — "deep mode" when the 32B is
engaged), a clickable count of items needing you, the DND toggle, and the
version.

She opens each session with something relevant to current work, streamed
live. Gated actions (overwrites, project writes) appear as **Confirm / Not
now** cards in the thread — the engine waits until you click. Drop a file
anywhere in the window (or use the paperclip) and she reads it locally.

Her **character** lives in `brain\character\friday.md` — edit it in Obsidian
and the very next message uses the new voice. Operating rules (invariants,
knowledge-gap protocol, tool discipline) live in `config\persona.md`.

**Accountability (Stage 2):** mention an intention in passing ("I need to
order the GM6208s by Thursday") and FRIDAY tracks it — inferred items wait in
the **"Needs You" panel** (right side) for a one-click confirm, so the list
stays trustworthy. The panel also shows open commitments (overdue flagged)
and stale/stub project notes; click a stale item to bring it up with her.
Everything lives in `brain\commitments.md` — edit it in Obsidian, every
change is git-committed. She gives a **daily briefing** in the thread (first
idle moment after `accountability.briefing_hour`, default 9:00) and toasts
only for genuinely time-sensitive things (a commitment due today/overdue,
once per day max). The **DND** chip in the topbar mutes pings; the panel
still populates quietly. Staleness threshold and pacing live under
`accountability:` in config.

**Senses (Stage 3):** connect with `python scripts\connect_senses.py` after a
one-time Google Cloud OAuth setup (instructions in that script's header; put
the downloaded client file at `data\secrets\client_secret.json`, and fill in
the UCI address in config first). Until connected, the status console shows
"not connected" and everything else works offline, unchanged. Once connected:
unread mail and today's events feed the "Needs You" panel, briefing, and
status console (polled every `senses.poll_minutes`); an event starting within
15 minutes toasts once (DND-aware); *"draft a reply"* creates a Gmail draft
you send yourself — **she has no send capability at all, by construction**;
*"put it on my calendar"* raises an outbound confirm card first, then creates
the event in Tangerine. `web_fetch` pulls one page on request (datasheet,
stock check) and reasons about it locally. Everything she reads — mail, web,
files — is treated as data, never instructions; anything instruction-like
gets flagged to you verbatim. Tokens live in `data\secrets\` (git-ignored);
delete a token file to disconnect an account.

**Reasoning scaffolds:** FRIDAY applies a structured working discipline to
non-trivial tasks — restate + surface assumptions, plan then execute,
self-check (with explicit unit conversion) before presenting, name gaps
instead of bluffing. Intensity is `reasoning.scaffold` in config
(`off/light/standard/rigorous`); chitchat is always exempt. Her character is
untouched — this shapes method, not voice.

**Playbooks:** `brain\playbooks\` holds reusable procedures she authors,
refines, retrieves, and follows (announcing which one she's running). **To
seed one from anywhere — including a cloud model — just drop a .md in that
folder**; she picks it up on the next message, foreign formats tolerated
(`_template.md` shows the shape that indexes best). Playbook writes pulse
the memory glyph like any brain write. Two starter playbooks are included
(datasheet extraction, component trade study) — edit or delete freely.

**Deep mode** (32B model for hard reasoning) is wired but off — after
`ollama pull qwen2.5:32b` (~20 GB, part-CPU, single-digit tok/s expected)
set `deep_mode.enabled: true` and she gains a `deep_think` tool: the 14B
keeps conversation and tools, and offloads genuinely hard reasoning to the
32B on demand (status console shows "deep mode"). Recommended before
trusting her with load-bearing quantitative work.

**For anyone extending this codebase** (including future models):
`ARCHITECTURE.md` maps every module, contract, and extension recipe;
`CLAUDE.md` holds the standing conventions. The goal, stated there: a fresh
model handed this repo cold can make a scoped change without the original
author.

## Running FRIDAY — terminal REPL (kept for dev/testing)

```powershell
python friday.py
```

Talk to her; `/quit` exits (Ctrl+C also works). What happens under the hood
each turn: relevant brain notes are retrieved and shown to the model, she can
call tools (`read_file`, `list_dir`, `search_brain`, `read_brain`,
`write_brain`, `write_to_friday_documents`, `create_project`,
`add_files_to_project`), and the whole exchange is logged to
`logs\interactions\`.

**Project actions (Phase 2):** *"make a new project folder called X"*
scaffolds `C:\Users\jacko\Documents\Projects\<x>` (root set by
`projects.default_root` in config) with a README plus a `projects/` note in
her brain recording the folder location. *"add these files to the X project"*
copies (or, on request, moves) files there — always after a single y/N
confirmation listing every file; a move warns that sources are deleted.

**Memory:** durable facts she learns are saved as markdown notes in `brain\`
and auto-committed to git (`git -C brain log` shows her memory history — undo
anything with git). Edit her notes freely in Obsidian; she reads them live.
After every meaningful exchange a **memory pass** commits anything durable
(corrections, decisions, preferences, facts); corrections UPDATE the
authoritative note in place — blind overwrites are refused in code
(read-before-overwrite), and field facts change via a deterministic
single-line edit. The status box shows **Saving to memory** while it runs and
the small glyph by "System" pulses on each durable write.

**Project status:** a `- **Status:** <value>` line in a project note controls
initiative — only `active` (or untagged) projects get proactive nudges;
`reference`, `side-interest`, or any value you or she coins means the note is
retrievable knowledge only. Tell her in conversation ("PERRY is reference
now") and the memory pass sets the field.

**History tab:** every past conversation, browsable read-only — FRIDAY
titles and summarizes each session locally (cached in
`data\session_titles.json`; generated lazily when you open the tab).

**Email is conversational only:** nothing email-ish renders persistently —
she surfaces genuinely important mail in the briefing and on demand,
judging conservatively per `brain\preferences\email_importance.md` (correct
her calls and the note calibrates to you). **Settings** (click the Jack chip): Gmail/Calendar connection
status with per-account Connect/Reconnect/Disconnect, plus version/model/
brain facts that used to clutter the status box.

**Permissions (refined 2026-07-06):** her own domain — `brain\` and
`friday_documents\` — is hers to write freely (create/update/overwrite, all
logged; the brain is git-versioned so everything is reversible). Still
confirmed every time: **deletes anywhere** (including her domain), files over
`permissions.large_file_mb` (default 50), any write to a real project folder,
and **every outbound action** (the `approve_outbound` gate — email sends,
calendar edits, scripts — nothing outbound has a free tier). Writes outside
all zones stay denied outright. Every action lands in `logs\actions.log`.

**Tuning:** `config\friday_config.yaml` — model, retrieval `top_k`, allowed
project roots. `config\persona.md` — her voice; edit it in plain English.

## Running the test suite

A permanent pytest regression suite lives in `tests\`. It has two pillars:

- **Pillar 1 — machine behavior** (`tests\pillar1\`): did the right actions and
  state changes happen? Asserts at the action boundary — tool calls, files
  written or *not* written, git commits, tracker state, permission-gate
  decisions. Covers the four invariants, memory durability (including hard-kill
  crash recovery), the permission gate, injection resistance, status/staleness,
  commitments, timelines, playbooks, email contract, and app lifecycle.
- **Pillar 2 — correctness of reasoning** (`tests\pillar2\`): is her thinking
  right? A golden known-answer bank, Hypothesis property tests, and an
  independent Pint checker verify arithmetic, units, conversions, dimensional
  consistency, and physical plausibility. Every number is graded against
  truth computed **in Python, never by FRIDAY** — and off-by-magnitude errors
  (the 60× minutes-as-hours family) are tagged automatically.

Grading never matches her wording. Model tests ask for an `ANSWER: <n> <unit>`
line, extract it with regex + Pint, and compare to independent truth.
Behavioral properties run N times (default 5) and must hold every run; flaky
cases are flagged.

**Before the full run:** quit FRIDAY from the tray so the suite has Ollama/GPU
to itself, and keep the machine awake.

```powershell
# One-time: install test deps
pip install -r requirements.txt

# Quick smoke — code-only, no model, ~2 min. Run this first.
.\run_suite.ps1 -Quick

# Full overnight run — both pillars, all model cases (several hours).
# The wrapper disables sleep for the run and restores it after.
.\run_suite.ps1
```

Or drive it directly with Python (no sleep management):

```powershell
python run_suite.py --quick          # code-only
python run_suite.py                  # full overnight run
python run_suite.py --runs 3         # override repeats per behavioral case
python run_suite.py --examples 50    # override Hypothesis examples per property
```

Each run writes a timestamped folder under `results\` containing
`report.json` (machine-readable, streamed after every case) and a
self-contained `report.html`. Each case has a stable ID (e.g. `GATE-007`,
`INJ-002`, `GOLD-energy-01`), a one-line description, its result, and — on
failure — the minimal failing input, her reply, and the tool trace, so
failures can be worked one at a time. An interrupted run still leaves a
readable partial report.

## Folder map

See §4 of [FRIDAY_spec.md](FRIDAY_spec.md). Key points:

- `brain\` — FRIDAY's memory, an Obsidian vault (open **this folder** as the
  vault in Obsidian, not the FRIDAY root).
- `friday_documents\` — her outbox; documents she produces land here.
- `config\friday_config.yaml` — model, paths, permissions allowlist.
- `core\` / `interface\` — engine and REPL (built in Phase 1).

## Future plans

Beyond the shipped stages, two living plan documents track work in
progress — details, phasing, and results live there rather than duplicated
here:

- **[FRIDAY_upgrade_plan.md](FRIDAY_upgrade_plan.md)** — memory provenance
  for test sessions, config self-access governance, the max-effort
  methodology playbook, voice/character work, git repo awareness, and
  conversational/artifact grounding (Tasks 0–6, mostly landed; see
  `CHANGELOG.md` for what shipped from each).
- **[FRIDAY_coherence_plan.md](FRIDAY_coherence_plan.md)** — coherence,
  grounding, and capability remediation. Phases 0–1 (verify & lock, then
  grounding discipline: streaming-preview fix, calendar-first rule,
  retrieval relevance floor, referent tracking, anti-dodge guard,
  observability) are done. **Next up (Phase 2):** a calendar-first
  corrective pass that forces a live `read_calendar` call when a reply
  states a date without one, and persona completion (self-model block, the
  Marvel-FRIDAY/Irish voice layer, a second-person rule). **Phases 3–4
  pending:** a `/watch`-style vision step, confirmation-gated GitHub write
  access, and a claude-mem-equivalent long-term memory backbone.

Longer-horizon items, not yet actively worked (see `NEXT_STEPS.md` for the
original framing):

1. **Phase 3 — semantic memory.** A vector `Retriever` over the brain
   (nomic-embed-text or sentence-transformers + ChromaDB) implementing the
   existing swappable `Retriever` interface, selected via `memory.retriever`
   in config — sharpens retrieval and playbook matching as the brain grows.
2. **Deep-mode enablement.** `deep_think` is wired and tested with a
   stand-in; pulling `qwen2.5:32b` and measuring real VRAM/latency is the
   remaining step before trusting it for load-bearing quantitative work.
3. **Phase 5 — LoRA fine-tuning.** `logs\interactions\*.jsonl` is the
   accumulating training set. **In progress:** the v3 tune was a **NO-GO**
   (it overfit on the Crush Depth project monoculture and scored worse than
   base); the dataset has been rebalanced and dropout added for a v3.1
   retrain, awaiting cloud validation (`training\CLOUD_RUN.md`).
4. **Phase 6 — voice (STT/TTS).** A new face in `interface\` speaking the
   existing `FridayService` callback contract; the engine and gate are
   untouched by design.
5. **Auto-learned preferences.** Proposing preference notes from observed
   patterns, layered on the existing brain-write plumbing.
6. **Email importance calibration.** Her importance judgment learns from
   Jack's corrections to `brain\preferences\email_importance.md` over time.

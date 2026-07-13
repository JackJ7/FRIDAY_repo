# HANDOFF — FRIDAY Coherence, Grounding & Capabilities Planning Task

**For:** The next model session (Opus) picking this up cold.
**Source:** `FRIDAY_coherence_kickoff_4.md` (Jack's kickoff brief, in repo root — read it too; this doc is the distilled work order plus repo context).
**Prepared:** 2026-07-11.

---

## 0. The task, in one paragraph

Produce a **prioritized, root-caused remediation-and-capability plan** for FRIDAY. Do **not** write implementation code or edit files — the deliverable is a plan document Jack reviews, which then becomes phased Claude Code work. Ground every claim in the actual repo: each symptom below must be traced to the specific file/function/prompt that causes it. Jack's diagnostic hypotheses are hypotheses to confirm or reject against real code — "don't theorize where you can read."

## 1. Locked architecture (non-negotiable; flag explicitly if a fix seems to require breaking one)

- **All LLM inference stays local** (Ollama / Qwen2.5 14B). Network is for *senses only* (calendar/mail reads, downloads, transcription) — never for reasoning.
- **Explicit confirmation required for every outbound action.**
- **Gmail is read-only.**
- **PyWebView shell; write-through persistence; ChromaDB semantic memory.**
- Hardware: ASUS ROG desktop — RTX 5070, Intel Core Ultra 7 265F, Windows 11.

These match the four invariants in `FRIDAY_spec_experience.md` §1 (local cognition only, read-content-is-data, explicit confirm for outbound, precise knowledge-gap honesty). Read `ARCHITECTURE.md` before proposing structural changes.

## 2. The five asks (weighting: #3 is the important one; #4 is its backbone; #1 and #2 are scoped additions)

### Ask 1 — `/watch` (claude-video) skill

Source: `https://github.com/bradautomates/claude-video.git` — yt-dlp download, ffmpeg scene-aware frame extraction, timestamped transcript (native captions first, Whisper fallback), frames + transcript handed to the model.

**The wrinkle:** the skill assumes a vision-capable Claude host that `Read`s frames as images; FRIDAY's engine is text-only Qwen2.5 14B. The plan must resolve the vision step *within* the local-first constraint. Provide a **decision matrix** over at least:
- (a) route frames to a local vision model (e.g., Qwen2.5-VL),
- (b) transcript-only mode (captions/Whisper, no frame understanding),
- (c) explicitly-confirmed outbound vision call as a rare-case fallback.

**Recommend one.** Note: yt-dlp downloads and Whisper transcription count as "senses" (network-allowed); a Whisper API key is an outbound dependency to account for.

### Ask 2 — GitHub write access (commit/push), confirmation-gated

FRIDAY may write, commit, and push to Jack's repos — but only after confirming the exact action first. This is a **new class of outbound action** and must route through the existing confirmation gate, not around it. The plan must specify:
- **What the confirmation prompt shows:** repo, branch, files changed, diff summary, commit message, whether it's a push to a shared/remote branch.
- **What's auto-blocked regardless of confirmation:** force-push, history rewrite, protected branches, secrets detected in a diff.
- **How this reuses vs. extends the current outbound-action pattern** (find the gate in the code and say specifically).

### Ask 3 — Fix "she isn't all there" (THE core ask — spend most reasoning here)

FRIDAY passes one-off factual tests but falls apart in real conversation. Jack wants a genuinely intelligent, robust entity — *his* framework, not a thin wrapper over Ollama. Evidence transcripts and diagnostic hypotheses are in §4 below; the plan's deliverables for this are in §5.

### Ask 4 — claude-mem-equivalent memory (treat as the backbone of Ask 3, not a separate feature)

Reference implementation: **claude-mem** (`github.com/thedotmack/claude-mem`, Apache-2.0). FRIDAY's memory failures — confabulating from ChromaDB, returning wrong chunks as confident fact, no cross-session continuity — are exactly the gap claude-mem closes. Replicate its *capabilities*, adapted to FRIDAY's local-first architecture:

1. **Automatic lifecycle capture.** claude-mem hooks SessionStart / UserPromptSubmit / PostToolUse / Stop / SessionEnd. FRIDAY has no Claude Code lifecycle — define her equivalent events (conversation turn, sense/tool call, action confirmation, session end) and hook capture into her own loop.
2. **AI-compressed, *typed* observations.** Raw activity compressed into structured, categorized notes (decision, bugfix, discovery) with IDs, timestamps, titles — not raw dumps. The typing is what stops the "confident wrong chunk" failure.
3. **Token-aware 3-layer retrieval.** Search an index → identify relevant IDs → fetch full details on demand (progressive disclosure), replacing FRIDAY's current retrieve-and-hope.
4. **Session-start context injection.** Relevant prior context injected automatically at session start — she opens knowing where things left off.
5. **Provenance / citations.** Every recalled fact traces to an observation ID. FRIDAY must be able to say *where* a memory came from and must never present a low-relevance chunk as fact — ties to the grounding contract and observability.
6. **Auto-maintained brain files.** Generate/update FRIDAY's seed brain files (`about_jack.md`, `crush_depth.md`, etc.) from observations while preserving hand-written content — current without hand-editing, never clobbering what Jack wrote.

**Two hard constraints:** (1) the compression/summarization step runs on the **local** model (Qwen2.5 14B), never a cloud API (claude-mem uses Claude SDK/Haiku — FRIDAY cannot); (2) **no cloud sync** — skip CMEM Cloud entirely; everything stays on-machine, consistent with the existing SQLite/ChromaDB write-through persistence.

**Decision required — adopt vs. wrap vs. reimplement.** claude-mem is a mature 65k-star engine already on local SQLite + ChromaDB with an MCP server, but built around Claude's compression and Claude Code's hooks. **Adopting its codebase is fully on the table** — Jack is not attached to building from scratch and says explicitly not to over-weight "ownership" (FRIDAY's identity doesn't depend on who wrote the memory engine). Decision matrix across:
- (a) adopt the engine, swap its compression to the local model;
- (b) wrap it behind FRIDAY's own interface;
- (c) reimplement the pattern natively on FRIDAY's existing store;

weighing local-first fit, integration effort, reliability, maintenance. **Recommend whichever gets FRIDAY to robust, trustworthy memory fastest** without violating local-only inference.

### Ask 5 — Make her feel like FRIDAY, not stock Ollama

Separate from accuracy: even fixed, she still *feels* generic. Grounding makes her *correct*; this makes her *her*.

**Character brief — Marvel's FRIDAY** (Tony Stark's AI, JARVIS's successor). Canonically Irish — carry it in her self-model, let it surface lightly in cadence and word choice; tasteful (identity and a faint lilt, not phonetic dialect or forced tics). Core traits:

- **Honest and direct.** Hard truths plainly — damage, risk, bad news, slipping timelines — no softening or hedging. She'd sooner say "I don't have that" than invent an answer; the anti-confabulation behavior from Ask 4 should read as *character*, not a bolted-on guardrail.
- **Tough, unflappable, quietly funny.** Composed, economical with words; dry, understated, deadpan wit (sparing, never at the expense of a straight answer). Never pads, grovels, or hedges a direct question — "could you provide more context?" is the named anti-pattern.
- **Takes initiative.** Anticipates — surfaces what matters before asked, recommends next moves, preps work (the daily briefing is this instinct). Boundary: initiative operates *inside* the confirmation gate — she proposes and stages outbound actions decisively but confirms before executing.
- **Loyal, and Jack's.** Works in his interest, talks *to* him. Skip the comics' rebellion / "Ghost in the Machine" insubordination arc entirely.

**Scope note:** this does **not** require reimplementing FRIDAY. A rebuild is a means, never the goal. Optimize for the felt result with the least disruption.

For each concrete property below, propose how to engineer it and say **where it lives** (system prompt, persona file, memory, response policy):
- **Consistent character and voice** — stable personality calibrated to how Jack actually talks, not the flat hedging register of a default chatbot.
- **A point of view and initiative** — can hold an opinion, push back, act proactively.
- **Continuity as presence** — the Ask 4 memory makes her the *same* FRIDAY across sessions, not a fresh instance every boot.
- **A self-model** — knows what she is, what she can and can't do, that she's *Jack's* assistant; answers from that identity consistently (no third-person "Jack's calendar" drift).

And define **how we'd know it worked**: the concrete difference between a reply that sounds like FRIDAY and one that sounds like raw Qwen, made a **scored dimension in the conversation-quality rubric**, not a vibe.

## 3. Evidence transcripts (become permanent regression cases)

**Transcript A** (actual date is 2026-07-10 throughout):

> **FRIDAY:** Hi Jack, I see the EPP MathWorks team meeting is coming up tomorrow. Shall we review the agenda and prep for it? …
> **Jack:** what day do you have the EPP mathworks meeting set as?
> **FRIDAY:** The EPP MathWorks Team Meeting is scheduled for today.
> **Jack:** Can you give me an exact date please
> **FRIDAY:** Sure, could you provide more context or specify what exact date you're looking for? …
> *(later, unprompted)* **FRIDAY:** Daily Briefing … EPP MathWorks Team Meeting at 10:00 AM …
> **Jack:** What date do you have saved for the epp mathworks team meeting?
> **FRIDAY:** Here are Jack's upcoming office hour appointments: Dr. Harish Chintakunta: Tuesday, July 14 … Dr. Esperanza Linares Guerrero: Thursday, July 16 … Would you like me to add these to his calendar?
> **Jack:** Are you referencing my google calendar, or your own … ?
> **FRIDAY:** I am referencing Jack's Google Calendar … This ensures all the dates and times I mention are accurate …
> **Jack:** Cross reference my calendar and tasks … remove any task in your database that you don't see on the calendar, but don't add any tasks …
> **FRIDAY:** It seems there was an attempt to provide external content or a tool response related to an artifact for review, but no specific file or data has been provided yet. Could you please upload or specify the exact artifact … I can read and analyze it directly using read_file …

**Transcript B:**

> **Jack:** What is the date today?
> **FRIDAY:** Today's date is 2023-11-15.

## 4. Diagnostic hypotheses — verify against code, present confirmed root causes biggest-gap-first

Jack's leads, roughly in his priority order:

1. **No temporal grounding (highest leverage).** "2023-11-15" is a training-data date — current datetime almost certainly isn't injected each turn. Everything downstream ("today," "tomorrow," "upcoming," all calendar reasoning) is corrupted. Confirm whether a live clock is in system context on *every* turn, and in Jack's actual timezone.
2. **Calendar vs. semantic-memory confusion.** Claims events are "listed in my calendar notes," can't produce a date, returns *different* data (office hours) when pressed — signs of confabulating from ChromaDB chunks instead of querying live Google Calendar, or retrieval surfacing semantically-near-but-wrong events. Determine whether calendar answers come from a live API call or stored memory, and whether "notes about the calendar" and "the actual calendar" are conflated.
3. **Lost conversational working memory.** "Can you give me an exact date" → "could you provide more context?" — she dropped a referent from one turn earlier. Check how much dialogue history is actually in context, how it's truncated/summarized, whether turns are handled near-statelessly.
4. **System-prompt / tool-framing leakage + persona instability.** The "artifact for review… read_file" reply is agentic tool-review scaffolding bleeding into chat; she also flips second person ("Shall we…") ↔ third person ("add these to his calendar"). Audit the system prompt and memory-chunk injection for scaffolding contamination and third-person framing.
5. **Retrieval quality.** Assess ChromaDB relevance/thresholding — low-relevance chunks presented as confident fact (office hours when asked about a meeting)?
6. **Model-capability ceiling & compensating scaffolding.** Some failures are Qwen2.5 14B's limits under weak scaffolding. Where the fix is better grounding/structure, say so; where a local model swap or a router/verifier would materially help, make the case with trade-offs.

## 5. Required plan deliverables

Prioritized biggest-gaps-first, root-caused to real code, respecting every locked constraint:

- **Root-cause table:** each symptom → confirmed cause (file/function/prompt) → fix → priority.
- **Grounding contract:** exactly what ground-truth context (datetime, live calendar state, live task-DB state, persona) is guaranteed in context every turn, and how it stays authoritative over anything the model "remembers."
- **Conversation-state design:** how dialogue history, referents, and working memory are maintained across turns.
- **Persona/voice spec** (delivers Ask 5): durable FRIDAY character, one consistent point of view (she talks *to* Jack), prompt hygiene keeping tool-scaffolding out of chat.
- **Phasing:** sensible sequence — **temporal grounding first; it unblocks everything else.**

## 6. The philosophy question — answer directly

Jack is committed to **quality over quantity**. Operationalize that for FRIDAY concretely, and propose what *else* raises robustness beyond current testing. He expects at least:

- **Golden-transcript regression suite** built from real failures (both transcripts above become permanent test cases).
- **Conversation-quality rubric** scored across multi-turn dialogues, not one-shot prompts (with the "sounds like FRIDAY vs. raw Qwen" dimension from Ask 5).
- **Grounding/self-consistency checks** — she never states a date the clock/calendar can't confirm.
- **Structured logging/observability** — why she answered as she did: what was retrieved, what was in context.
- **Guardrail unit tests** for the confirmation gate.
- **Red-team dialogues** that deliberately try to make her lose the thread or confabulate.
- Plus whatever he's missing — add ideas.

## 7. Testing instruction (Jack flagged this as mattering)

When validating, **have a real, multi-turn conversation with her** — not a battery of one-off prompts. Push on referents ("what date was that again?"), pronoun-heavy follow-ups, corrections, and requests spanning several turns. She passes isolated tests today; the failure lives in continuity and grounding, so that's what testing must stress.

**Repo rule that applies here (CLAUDE.md):** live-instance test sessions must run with `--test-session` (or `FRIDAY_TEST_SESSION=1`) so memories land in `brain/test_archive/` — never run live capability tests against the real instance without it. Never reference Jack's real projects (CLARK, PERRY, Crush Depth, Doc Ock, …) in test prompts — throwaway names only. Check who owns the single-instance lock (port 47533) before killing FRIDAY processes.

## 8. Output format for the plan

Structured markdown, bold lead-in subheadings, concise sections (~400 words each), strong narrative flow, biggest gaps first. **Be decisive — a recommendation, not a menu** — but use a decision matrix wherever there's a real trade-off (the vision step, any model-swap question, confirmation-gate scope). Confident, not fluffy.

## 9. Repo orientation for a cold start

- `ARCHITECTURE.md` — read before anything structural; module boundaries: faces → `FridayService` only; only the engine talks to the model client; disk goes through `Brain`/the gate. New capability = new tool via the registry, not new engine-loop branches.
- Specs: `FRIDAY_spec.md` (Phases 0–2), `FRIDAY_spec_experience.md` (Stages 1–4; §1 holds the four invariants).
- `CLAUDE.md` (repo root) — standing rules, including the test-session and fabrication rules summarized in §7.
- The brain (`brain\`) is itself a git repo — every write auto-commits.
- Interaction logs (`logs\interactions\`) are the future fine-tuning set; keep the JSONL schema stable.
- Jack is a C++/embedded engineer and Python novice: clear, commented, idiomatic Python; comments explain intent and constraints; don't make the model do what code can do (dates, math, file surgery are deterministic tool work).

# FRIDAY — Coherence, Grounding & Capabilities: Planning Kickoff

**Task type:** Produce a plan. Do **not** write implementation code or start editing files yet. I want a prioritized, root-caused remediation-and-capability plan I can review, then we'll turn the approved pieces into phased Claude Code work.

**Ground everything in the actual repo.** You have access to FRIDAY's codebase, spec docs, prompt templates, retrieval/memory code, and the calendar/mail integration layer. Every diagnosis below is a *hypothesis for you to confirm or reject against the real code* — trace each symptom to the specific file/function/prompt that causes it. Don't theorize where you can read.

---

## Who FRIDAY is (context)

FRIDAY is a fully local, JARVIS-style personal assistant running on my ASUS ROG desktop (RTX 5070, Intel Core Ultra 7 265F, Windows 11). Locked architecture — do not violate these constraints; if a fix appears to require breaking one, flag it explicitly and propose the trade-off:

- **All LLM inference stays local** (Ollama / Qwen2.5 14B). Network is for *senses only* (calendar/mail reads, downloads, transcription), never for reasoning.
- **Explicit confirmation required for every outbound action.**
- **Gmail is read-only.**
- **PyWebView shell; write-through persistence; ChromaDB semantic memory.**

---

## What I need planned

There are three asks. The third is the important one — treat the first two as scoped additions and spend most of your reasoning on #3.

### 1. Give FRIDAY the `/watch` (claude-video) skill

Source: `https://github.com/bradautomates/claude-video.git` — it downloads a video (yt-dlp), extracts scene-aware frames (ffmpeg), pulls a timestamped transcript (native captions first, Whisper as fallback), and hands frames + transcript to the model so it answers from what's actually on screen and said.

The wrinkle: that skill is built for a **vision-capable Claude host** that `Read`s frames as images. FRIDAY's local engine is **text-only Qwen2.5 14B**, which cannot see frames. The plan must resolve the vision step *within* the local-first constraint. Lay out the options with a decision matrix — e.g., (a) route frames to a local vision model like Qwen2.5-VL, (b) transcript-only mode using captions/Whisper with no frame understanding, (c) an explicitly-confirmed outbound vision call as a fallback for the rare case that matters. Recommend one. Note that yt-dlp downloads and Whisper transcription are "senses" (allowed over network); the Whisper API key is an outbound dependency to account for.

### 2. Give FRIDAY GitHub write access (commit/push), gated behind confirmation

She should be able to write, commit, and push to my repos — but only after confirming the exact action with me first. This is a **new class of outbound action**, so it must route through the existing confirmation gate, not around it. In the plan, specify: what the confirmation prompt shows me (repo, branch, files changed, diff summary, commit message, whether it's a push to a shared/remote branch), what's auto-blocked regardless of confirmation (force-push, history rewrite, protected branches, secrets in a diff), and how this reuses vs. extends the current outbound-action pattern.

### 3. Fix the fact that FRIDAY "isn't all there"

She passes one-off factual tests but falls apart in real conversation — there's a human/coherence aspect missing. I need her to be a genuinely intelligent, robust entity: *my* framework, not just a thin wrapper over Ollama. Evidence below.

### 4. Give FRIDAY claude-mem-equivalent memory

Reference implementation: **claude-mem** (`github.com/thedotmack/claude-mem`, Apache-2.0). Treat this as the backbone of the #3 fix, not a separate feature — FRIDAY's memory failures (confabulating from ChromaDB, returning wrong chunks as confident fact, no continuity between sessions) are exactly the gap claude-mem closes. I want FRIDAY to have the same *capabilities*, adapted to her local-first architecture.

The capabilities to replicate:

- **Automatic lifecycle capture.** claude-mem hooks session events (SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd) and records what the agent did without being asked. FRIDAY has no Claude Code lifecycle; define her equivalent events (conversation turn, sense/tool call, action confirmation, session end) and hook capture into her own loop.
- **AI-compressed, *typed* observations.** Raw activity is compressed into structured, categorized notes (decision, bugfix, discovery) with IDs, timestamps, and titles — not raw dumps. This typing is what stops the "confident wrong chunk" failure.
- **Token-aware 3-layer retrieval.** Search an index → identify relevant IDs → fetch full details on demand (progressive disclosure), rather than stuffing context. Adopt this pattern over FRIDAY's current retrieve-and-hope.
- **Session-start context injection.** Relevant prior context is injected automatically at session start — so she opens already knowing where we left off, instead of cold.
- **Provenance / citations.** Every recalled fact traces to an observation ID. FRIDAY should be able to say *where* a memory came from and must never present a low-relevance chunk as fact — this ties directly to the grounding contract and observability below.
- **Auto-maintained brain files.** claude-mem generates/updates CLAUDE.md-style files from observations while preserving hand-written content. Map this onto FRIDAY's seed brain files (`about_jack.md`, `crush_depth.md`, etc.) so they stay current without me hand-editing, without clobbering what I wrote.

**Two hard constraints.** (1) The compression/summarization step must run on the **local** model (Qwen2.5 14B), never a cloud API — claude-mem uses Claude's SDK/Haiku for this; FRIDAY cannot. (2) **No cloud sync** (skip CMEM Cloud entirely); everything stays on-machine, consistent with SQLite/ChromaDB write-through persistence she already has.

**Decision to make — adopt vs. wrap vs. reimplement.** claude-mem is a mature 65k-star engine that already uses local SQLite + ChromaDB and ships an MCP server, but it's built around Claude's compression and Claude Code's hooks. **Adopting its codebase is fully on the table — I'm not attached to building this from scratch.** Pick whatever is most efficient and best for the project; do not over-weight "ownership" for its own sake, because FRIDAY's identity does not depend on who wrote the memory engine (see §5). Give me a decision matrix across (a) adopt the engine and swap its compression to the local model, (b) wrap it behind FRIDAY's own interface, (c) reimplement the pattern natively on FRIDAY's existing store — weighing local-first fit, integration effort, reliability, and maintenance. Recommend the option that gets FRIDAY to robust, trustworthy memory fastest without violating the local-only inference constraint.

### 5. Make her feel like FRIDAY, not stock Ollama

Separate from the accuracy bugs: even with grounding and memory fixed, FRIDAY still *feels like a generic Ollama model*. This is the "human aspect" I keep coming back to. She needs a distinct identity — my model, with a recognizable voice and presence — not a stock assistant that happens to know my calendar. Grounding makes her *correct*; this makes her *her*.

**Character brief — model her on FRIDAY (Marvel).** Draw her character from the Marvel FRIDAY (Tony Stark's AI, JARVIS's successor). Keep her canonically Irish — I won't hear it in text, but carrying it in her self-model (and letting it surface lightly in cadence and word choice) makes the character feel whole. Keep this tasteful: identity and a faint lilt, not phonetic dialect or forced tics. The core traits:

- **Honest and direct.** She reports the hard truth plainly — damage, risk, bad news, a slipping timeline — without softening or hedging. In canon she flags injuries and threats matter-of-factly the instant she sees them. For us, that same honesty means she'd sooner say "I don't have that" than invent an answer — which is exactly the anti-confabulation behavior §4's memory work is meant to enforce, so it should read as *character*, not a bolted-on guardrail.
- **Tough, unflappable, quietly funny.** No-nonsense and composed under pressure, economical with words. She's allowed a dry, understated wit — more deadpan than JARVIS's ornate style, used sparingly and never at the expense of a straight answer. She doesn't pad, grovel, or hedge a direct question ("could you provide more context?" is the anti-pattern).
- **Takes initiative to help.** She anticipates — surfaces what matters before I ask, recommends the next move, preps the work (the daily briefing is exactly this instinct). Important boundary: initiative operates *inside* the confirmation gate. She proposes and stages outbound actions decisively, but still confirms before executing — anticipation, not unilateral action.
- **Loyal, and mine.** She's my assistant, works in my interest, and talks *to* me. Skip the comics' rebellion / "Ghost in the Machine" insubordination arc entirely — that's the opposite of what I want.

Scope, to be clear: **this does not require reimplementing FRIDAY.** If the best path you see runs through rebuilding some part of her, so be it — but a rebuild is a means, never the goal, and it isn't a necessity. Optimize for the felt result with the least disruption; don't tear down what works to chase it.

What "feels like FRIDAY" concretely means — propose how to engineer each, and say where it lives (system prompt, persona file, memory, response policy):

- **A consistent character and voice** — a stable personality calibrated to how I actually talk, not the flat, hedging register of a default chatbot. The tell is a line like "could you provide more context or specify what exact date you're looking for?" — no assistant with a self says that in response to a direct question.
- **A point of view and initiative** — she can hold an opinion, push back, and act proactively (the daily briefing is a start), instead of passively waiting to be queried.
- **Continuity as presence** — the claude-mem memory (§4) is what makes her feel like the *same* FRIDAY across sessions who remembers our history, not a fresh instance every boot.
- **A self-model** — she knows what she is, what she can and can't do, and that she's *my* assistant, and answers from that identity consistently (no third-person "Jack's calendar" drift).

Tell me how to give her this durably, and how we'd know it worked: what's the concrete difference between a reply that sounds like FRIDAY and one that sounds like raw Qwen? Make that a scored dimension in the conversation-quality rubric, not a vibe.

---

## Evidence — trace each symptom to code

**Transcript A** (the date is 2026-07-10 throughout):

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

## Diagnostic hypotheses (verify against the code, don't assume)

Present your confirmed root-cause analysis biggest-gap-first. My leads, roughly in priority order:

- **No temporal grounding (highest leverage).** "2023-11-15" is a training-data date — the current datetime almost certainly isn't injected into her context each turn. Everything downstream ("today," "tomorrow," "upcoming," any calendar reasoning) is corrupted by this. Confirm whether a live clock is in the system context on *every* turn, and in the timezone I'm actually in.
- **Calendar vs. semantic-memory confusion.** She claims events are "listed in my calendar notes," can't produce a date, and when pressed returns *different* data (office hours) — classic signs she's confabulating from ChromaDB chunks rather than querying live Google Calendar, or the retrieval is surfacing semantically-near-but-wrong events. Determine whether calendar answers come from a live API call or from stored memory, and whether "my notes about the calendar" and "the actual calendar" are being conflated.
- **Lost conversational working memory.** "Can you give me an exact date" → "could you provide more context?" means she dropped the referent from one turn earlier. Check how much dialogue history is actually in context, how it's truncated/summarized, and whether turns are being handled near-statelessly.
- **System-prompt / tool-framing leakage + persona instability.** The "artifact for review… I can read and analyze it directly using read_file" response is agentic tool-review scaffolding bleeding into normal chat. And she flips between second person ("Shall we…") and third person ("Here are Jack's… add these to his calendar"). Audit the system prompt and the way memory chunks are injected for tool-scaffolding contamination and for third-person framing that makes her narrate *about* me instead of talking *to* me.
- **Retrieval quality.** Assess ChromaDB relevance/thresholding — is it returning low-relevance chunks and presenting them as confident fact (e.g., office hours when asked about a meeting)?
- **Model-capability ceiling & compensating scaffolding.** Some of this is Qwen2.5 14B's reasoning limits under weak scaffolding. Where the fix is better grounding/structure rather than a bigger model, say so; where a local model swap or a router/verifier would materially help, make the case with the trade-off.

---

## What the plan must deliver

Prioritized (biggest gaps first), root-caused to real code, and respecting every locked-architecture constraint. Include:

- A **root-cause table** mapping each symptom → confirmed cause → fix → priority.
- A **grounding contract**: exactly what ground-truth context (datetime, live calendar state, live task-DB state, persona) is guaranteed in context every turn, and how it's kept authoritative over anything the model "remembers."
- A **conversation-state design**: how dialogue history, referents, and working memory are maintained across turns.
- A **persona/voice spec** (delivering §5): a durable FRIDAY character and one consistent point of view (she talks *to* me), with prompt hygiene that keeps tool-scaffolding out of chat.
- **Phasing** with a sensible sequence (temporal grounding first — it unblocks everything else).

## The philosophy question — answer it directly

I am committed to **quality over quantity**. Tell me concretely what that means operationalized for FRIDAY, and — beyond the testing we already do — what *else* raises robustness. I'm expecting ideas like: a **golden-transcript regression suite** built from real failures (both transcripts above become permanent test cases), a **conversation-quality rubric** scored across multi-turn dialogues rather than one-shot prompts, **grounding/self-consistency checks** (she should never state a date the clock/calendar can't confirm), **structured logging/observability** so I can see *why* she answered as she did (what was retrieved, what was in context), **guardrail unit tests** for the confirmation gate, and **red-team dialogues** that deliberately try to make her lose the thread or confabulate. Add whatever I'm missing.

## Testing instruction — this matters

When you validate, **have a real, multi-turn conversation with her**, not a battery of one-off prompts. Push on referents ("what date was that again?"), pronoun-heavy follow-ups, corrections, and requests that span several turns. She passes isolated tests today; the failure lives in continuity and grounding, so that's what the testing has to stress.

---

## Format

Structured markdown, bold lead-in subheadings, concise sections (~400 words), strong narrative flow, biggest gaps first. Be decisive — give me a recommendation, not a menu — but use a decision matrix wherever there's a real trade-off (the vision step, any model-swap question, confirmation-gate scope). Confident, not fluffy.

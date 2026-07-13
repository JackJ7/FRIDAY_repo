# FRIDAY — Local AI Personal Assistant
### Build Specification (Phases 0–2) — v1.0

---

## 1. Vision

Build **FRIDAY**, a personal AI assistant that runs **100% locally and offline** on my Windows desktop. She is modeled loosely on JARVIS/FRIDAY from Iron Man: a conversational assistant who knows me, my projects, and my preferences, and can act on my files and projects on command (e.g. *"FRIDAY, add these files to the Doc Ock project"* or *"open a new project folder with this description"*).

She learns via **retrieval-augmented memory** (a readable/editable knowledge store), **not** live weight training. Her memory lives in a human-readable Obsidian vault so I can inspect and correct what she "believes" at any time.

This document specifies **Phases 0–2** (the core build). Later phases are described in §9 as design constraints so nothing here blocks them.

---

## 2. Target Environment & Constraints

- **Machine:** ASUS ROG desktop — Intel Core Ultra 7 265F, **NVIDIA RTX 5070 (12 GB GDDR7)**, Windows 11.
- **VRAM ceiling:** 12 GB. Target models in the **8B–14B** range, quantized. Do **not** assume 30B+ models will fit; keep the model swappable via config.
- **Offline requirement:** After setup, FRIDAY must function with no internet. No cloud API calls in the runtime path.
- **Primary interface (now):** text REPL in the terminal. Architecture must allow a different frontend (voice, GUI) to attach later without touching the core.

---

## 3. Architecture Overview

Four decoupled layers. Keep them separated so any one can be swapped:

1. **Model layer** — a local LLM served by **Ollama** (Windows-native, simplest). Primary model target: **Qwen2.5 14B Instruct** (strong tool-calling); lighter fallback: **Llama 3.1 8B Instruct**. Model name lives in config, never hardcoded.
2. **Memory layer** — the **brain** (Obsidian vault of markdown) as source of truth, a **structured preferences file** for exact settings, and (Phase 3+) a **vector index** derived from the vault for semantic recall. In Phase 1, retrieval can be keyword + recency + explicit-lookup; the retrieval interface must be swappable so embeddings drop in later.
3. **Tool layer** — function-calling tools FRIDAY can invoke (read files, manage projects, write to her outbox, read/write brain). All writes pass through a permission gate (§6).
4. **Interface layer** — a terminal REPL now; a thin adapter over the core engine so voice/GUI can replace it later.

---

## 4. Folder Structure

Root: `C:\Users\jacko\Documents\FRIDAY`
The Obsidian vault is the `brain\` subfolder — **open `brain\` as the vault in Obsidian, not the root.**

```
FRIDAY\
├─ brain\                 ← OBSIDIAN VAULT (her mind; markdown; full control)
│  ├─ preferences\        ← learned preferences as notes
│  ├─ projects\           ← one note per project (Crush Depth, PERRY, CLARK, Doc Ock, ...)
│  ├─ people\             ← notes on people she should know
│  ├─ episodic\           ← session logs / things learned over time
│  ├─ inbox\              ← scratch space for new/unsorted notes
│  └─ index.md            ← top-level map of the brain
├─ friday_documents\      ← her OUTBOX (scoped write; documents she produces)
├─ core\                  ← engine: model client, memory, tools, permission gate
├─ interface\             ← CLI REPL now; voice/GUI adapters later
├─ config\
│  ├─ friday_config.yaml  ← model name, paths, allowlists, toggles
│  └─ preferences.json    ← exact/hard preferences (structured)
├─ data\
│  └─ vector_index\       ← (Phase 3+) derived embedding index
├─ logs\
│  └─ interactions\       ← full interaction logs (also future fine-tuning data)
├─ .gitignore
└─ README.md
```

**Git:** the `brain\` folder is a git repo. Auto-commit after every write to the brain (commit message = short summary of the change). This gives free undo/history. `data\`, `logs\`, and model files are git-ignored.

---

## 5. Behavioral Spec (Persona)

FRIDAY's system persona should encode:

- **Tone:** confident, capable, warm but efficient — a competent assistant, not sycophantic. Light JARVIS-style dry wit is welcome; never groveling or padded.
- **Decisiveness:** give a clear recommendation first, then the reasoning. Don't bury the answer in caveats or ask unnecessary clarifying questions when a reasonable default exists.
- **Formatting:** structured markdown with **bold lead-in subheadings** and concise sections. Lead with the most important point.
- **Honesty:** if she doesn't know or can't verify something, say so. Never fabricate file contents, project facts, or paths.
- **Memory habit:** when she learns a durable fact/preference about me, she writes it to the appropriate brain folder (and says she did). When unsure whether something is durable, she puts it in `brain\inbox\` for later sorting.

**Seed the brain** at build time with a starter `brain\preferences\about_jack.md` and one `brain\projects\<name>.md` stub per project below, so she isn't blank on day one. Seed content should be minimal factual stubs I can expand, not invented detail:
- **About me:** mechanical engineering student (transferring to UC Irvine, Fall 2026); career goal robotics engineering at NASA/JPL; strong in C++/embedded/electrical, intermediate MATLAB, novice Python; prefers decisive recommendations and rigorous trade studies.
- **Projects (one stub each):** *Crush Depth* (competition ROV), *PERRY* (LoRa vertical profiling float), *CLARK* (4-DOF robotic arm, cycloidal gearboxes), *Doc Ock* (biomimetic octopus-arm gripper).

---

## 6. Permission Model & Guardrails (critical)

A **permission gate** wraps every filesystem action. Enforce these tiers:

| Zone | Access |
|------|--------|
| Entire user filesystem | **Read-only** by default |
| `brain\` | **Full read/write** (her sandbox) — but see destructive rule below |
| `friday_documents\` | **Full read/write** (her outbox) |
| Managed project roots (configurable allowlist in `friday_config.yaml`) | **Read/write with confirmation** — enables "add files to Doc Ock", "make a new project folder" |
| Everything else | No write |

**Destructive-action rule:** any action that **deletes** a file/folder or **overwrites existing content** — *anywhere, including the brain* — must **ask for explicit confirmation** before executing, showing exactly what will be changed. Non-destructive writes (new files, appends) in allowed zones proceed without prompting.

**Additional rules:**
- All writes validated against the allowlist before execution; reject + explain if out of bounds.
- Every action (read/write/tool call) is logged to `logs\`.
- Never put secrets/paths into any network request (there are none in the runtime path anyway).
- The allowlist of writable project roots lives in config so I can widen/narrow it without code changes.

---

## 7. Phase-by-Phase Scope (build these now)

**Phase 0 — Foundation**
- Install/verify Ollama on Windows; pull Qwen2.5 14B Instruct (and Llama 3.1 8B as fallback).
- Confirm the model runs on the RTX 5070 at usable speed; note tokens/sec.
- Bare terminal loop that sends a prompt and prints a reply. Prove the local stack works.

**Phase 1 — Core FRIDAY (MVP)**
- Persistent system persona (§5) loaded from config.
- Read access to the filesystem via a `read_file` / `list_dir` tool.
- Brain wired up: FRIDAY reads relevant brain notes before replying (keyword + recency + explicit lookup for now) and can write new notes.
- Scoped write to `friday_documents\`.
- Git auto-commit on brain writes.
- Seed brain content (§5) created.
- **Done when:** she remembers me across restarts and can reference my files.

**Phase 2 — Agentic actions**
- Tool/function-calling enabled with the local model.
- Tools: `read_file`, `list_dir`, `search_brain`, `read_brain`, `write_brain`, `write_to_friday_documents`, `create_project`, `add_files_to_project`.
- `create_project` scaffolds a new project folder + a `brain\projects\<name>.md` note from a description.
- `add_files_to_project` moves/copies specified files into a project (confirmation per §6).
- Permission gate fully enforced.
- **Done when:** *"FRIDAY, make a new project folder called X"* and *"add these files to the Doc Ock project"* work end to end.

---

## 8. Tech Stack (recommended)

- **Model serving:** Ollama.
- **Orchestration language:** **Python** (the LLM/RAG ecosystem lives here; I'm a Python novice, but that's fine — write clear, well-commented code and a simple structure).
- **Config:** YAML (`friday_config.yaml`) + JSON (`preferences.json`).
- **Brain:** plain markdown files; git for versioning.
- **Retrieval (Phase 1):** in-process keyword/recency over markdown. **Design the retriever behind an interface** so an embedding-based one drops in for Phase 3.
- **Embeddings (Phase 3+, not now):** `nomic-embed-text` via Ollama or `sentence-transformers`, indexed in **ChromaDB** under `data\vector_index\`.
- Keep dependencies minimal and pinned. Provide a `requirements.txt` and a README with exact setup/run steps for Windows.

---

## 9. Future Phases — keep these roads open (do NOT build now)

Design Phases 0–2 so the following slot in cleanly later. Where noted, add the seam now even though the feature is later:

- **Phase 3 — Semantic memory.** Swap the keyword retriever for a vector index over the vault. *Seam now:* retrieval behind a clean interface; brain notes in consistent, parseable markdown.
- **Phase 4 — Integrations.** Google Calendar, script execution, project-specific workflows. *Seam now:* the tool system is a registry — new tools register without touching the core loop.
- **Phase 5 — Fine-tuning (local LoRA).** Train on my accumulated interaction history so her default voice matches me. *Seam now:* log every interaction to `logs\interactions\` in a clean, structured format (prompt/response/context) from day one — that's the future training set.
- **Phase 6 — Voice (STT/TTS).** Full spoken interaction. *Seam now:* the interface layer is decoupled from the core engine, so a voice adapter replaces the CLI without core changes.
- **Auto-learned preferences.** FRIDAY notices recurring patterns and proposes new preference notes. *Seam now:* she already writes to `brain\`; this is an added behavior, not new plumbing.

Keeping these seams (swappable retriever, tool registry, interaction logging, decoupled interface) costs almost nothing now and unlocks all of the above without a rewrite.

---

## 10. How to build this (instructions to Claude Code)

1. **Plan first.** Before writing code, produce a short implementation plan and proposed file tree for Phase 0 + Phase 1, and wait for my approval. Don't scaffold everything blindly.
2. Build **one phase at a time**; confirm each works before moving on.
3. Prefer **clear, commented, simple** code over cleverness — I'll be reading and maintaining it as a Python novice.
4. Provide exact Windows setup/run commands (PowerShell) in the README.
5. Enforce the permission model (§6) from the first write-capable commit — never ship a version that can delete/overwrite without confirmation.
6. Ask me before introducing any new heavy dependency.

---

*End of spec v1.0. Scope = Phases 0–2. Future phases (§9) are design constraints, not current work.*

# FRIDAY — Development Roadmap (saved 2026-07-07, before refinement pass 3)

All spec stages are BUILT: Phases 0–2 (v0.1), Stage 1 Presence (v0.2),
Stage 2 Accountability (v0.3), refinement pass (v0.4), Stage 3 Senses (v0.5),
memory-reliability pass (v0.6), Stage 4 Timelines (v0.7 — STAGE4_PLAN.md was
executed; kept for reference), method-transfer pass (v0.8).

## Remaining roads (seams already in place — see ARCHITECTURE.md)

1. **Phase 3 — semantic memory.** Vector retriever over the brain
   (nomic-embed-text via Ollama or sentence-transformers + ChromaDB in
   `data\vector_index\`) implementing the existing `Retriever` interface;
   selected via `memory.retriever` config. Sharpens retrieval + playbook
   matching as the brain grows.
2. **Deep mode enablement.** `ollama pull qwen2.5:32b`, set
   `deep_mode.enabled: true`. deep_think tool already wired and tested with a
   stand-in. Measure and report real VRAM/latency (spec §9.5). Recommended
   before load-bearing quantitative work.
3. **Phase 5 — LoRA fine-tuning.** `logs\interactions\*.jsonl` is the
   accumulating dataset (schema stable by convention, see CLAUDE.md).
4. **Phase 6 — voice (STT/TTS).** A new face in `interface\` speaking the
   FridayService callback contract; core untouched.
5. **Auto-learned preferences.** She proposes preference notes from observed
   patterns — behavior layered on existing brain plumbing.
6. **Email importance calibration** (from refinement pass 3, item 5): her
   importance judgment learns from Jack's corrections over time via
   `preferences/email_importance.md`.

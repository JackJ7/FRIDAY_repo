"""
Retriever interface — the Phase 3 seam.

The engine only ever talks to this abstract interface, so the recall mechanism
is swappable by config (`memory.retriever`) with zero engine changes:
  * `keyword`  — keyword + recency over notes (keyword_retriever.py); default
                 before Phase 3, kept as the fallback.
  * `layered`  — the Phase-3 backbone (observation_retriever.py): notes AND the
                 typed-observation stream, merged and floored, each observation
                 self-citing by its id. This is the "same FRIDAY across
                 sessions" recall (D7).
  * `vector`   — RESERVED seam. A local embedding index (ChromaDB /
                 sentence-transformers) drops in behind this same interface.
                 NOT wired: it needs a heavy on-device dependency (torch), which
                 CLAUDE.md requires clearing with Jack first — see the Phase-4
                 handoff in FRIDAY_coherence_plan.md. Bootstrap refuses to boot
                 with `vector` until then, rather than pretend it exists.

A retriever returns RetrievedNote hints; the engine treats them as hints, never
truth (the grounding contract, D2).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedNote:
    path: str      # note path relative to the brain root, e.g. "projects/perry.md"
    snippet: str   # a short excerpt to show the model
    score: float   # relevance (higher = better); only comparable within one query


class Retriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int,
                 include_test: bool = False) -> list[RetrievedNote]:
        """Return the top_k most relevant brain notes for this query.

        include_test — search the test_archive/ subtree too (memory
        provenance, upgrade plan Task 1). False by default so a real
        session's recall never serves test-session memories as lived
        history; the engine turns it on inside test sessions and when Jack
        explicitly asks about testing."""

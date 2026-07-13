r"""
The Phase-3 recall layers (coherence plan D7 item 3).

Two retrievers behind the same `Retriever` seam:

  * ObservationRetriever — scores the typed-observation stream
    (observations.py). Title-weighted (an observation's frontmatter title is
    its headline, so a term there counts like a filename match), type-aware,
    recency-boosted, and floored by the same min_score as notes. Every result
    is SELF-CITING: its snippet leads with the observation's provenance stamp
    (`obs <id> · <type> · saved <date>`), so a claim grounded in it carries its
    citation (D7 item 5).

  * LayeredRetriever — the composite the engine actually uses under
    `memory.retriever: layered`. It queries BOTH notes (KeywordRetriever, which
    now excludes observations/) AND observations, merges by score, and returns
    the top_k. Because both layers share the same scoring base and floor, the
    scores are comparable and the merge is a plain sort. A fresh brain has zero
    observations, so on a cold vault this is byte-for-byte the keyword notes
    behaviour — observations only start to surface once the memory pass has
    written some, which is exactly the cross-session continuity we want.

The "3 layers" of the D7 pattern (index -> ids -> fetch) live INSIDE these:
scanning cheap frontmatter to score, then reading only the winners' bodies.
The public seam stays `retrieve()` so the engine is unchanged.
"""

import time
from pathlib import Path

from .keyword_retriever import KeywordRetriever, _words
from .observations import ObservationStore
from .retriever import RetrievedNote, Retriever


class ObservationRetriever(Retriever):
    def __init__(self, brain, min_score: float = KeywordRetriever.DEFAULT_MIN_SCORE):
        # Given the Brain (not just a path) so it honours test-session routing:
        # the store reads test_archive/observations in a test session and the
        # real stream otherwise — same provenance rule as everything else.
        self.store = ObservationStore(brain)
        self.min_score = float(min_score)

    def retrieve(self, query: str, top_k: int,
                 include_test: bool = False) -> list:
        terms = _words(query)
        if not terms:
            return []
        now = time.time()
        results = []
        for obs in self.store.all(include_test=include_test or None):
            title_l = (obs.title or "").lower()
            body_l = (obs.body or "").lower()
            # Title terms weigh like a filename match (+5/term); a type-name hit
            # (e.g. "decision", "preference") nudges (+2); body occurrences
            # count once each. Mirrors KeywordRetriever's shape so the scores
            # merge sensibly in LayeredRetriever.
            score = float(sum(body_l.count(t) for t in terms))
            score += 5.0 * sum(1 for t in terms if t in title_l)
            score += 2.0 * sum(1 for t in terms if t == (obs.type or "").lower())
            if score == 0:
                continue
            # Recency boost keyed to when the observation was recorded (its ts),
            # up to +50% over 30 days — the continuity stream should favour
            # "where we left off" over stale records.
            score *= 1.0 + 0.5 * _recency(obs.ts, now)
            if score < self.min_score:
                continue
            results.append(RetrievedNote(obs.path, self._snippet(obs), score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def _snippet(obs) -> str:
        """Provenance stamp first (self-citing), then the observation body."""
        body = "\n".join(obs.body.splitlines()[:8])
        return f"({obs.cite()})\n{body}"


class LayeredRetriever(Retriever):
    """Notes + observations, merged. The engine's Phase-3 default."""

    def __init__(self, brain, min_score: float = KeywordRetriever.DEFAULT_MIN_SCORE):
        self.notes = KeywordRetriever(brain.root, min_score=min_score)
        self.observations = ObservationRetriever(brain, min_score=min_score)

    def retrieve(self, query: str, top_k: int,
                 include_test: bool = False) -> list:
        merged = (self.notes.retrieve(query, top_k, include_test)
                  + self.observations.retrieve(query, top_k, include_test))
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[:top_k]


def _recency(ts: str, now: float) -> float:
    """0..1 recency weight from an ISO timestamp string. Robust to a missing or
    malformed ts (an observation is never dropped from recall over a bad date —
    it just loses the boost)."""
    if not ts:
        return 0.0
    from datetime import datetime
    try:
        when = datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return 0.0
    age_days = (now - when) / 86400
    return max(0.0, (30 - age_days) / 30)

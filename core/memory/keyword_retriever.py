"""
Phase 1 retriever: keyword match + recency over the brain's markdown files.

Deliberately simple — the vault is small, so scanning every note per query is
fast. Scoring: count how often the query's meaningful words appear in each
note (matches in the file name weigh extra), then boost recently edited notes.
"""

import re
import time
from pathlib import Path

from .retriever import RetrievedNote, Retriever

# Common words that carry no meaning for matching.
STOPWORDS = {
    "the", "and", "for", "you", "your", "what", "which", "who", "how", "why",
    "when", "where", "that", "this", "these", "those", "with", "about", "into",
    "from", "have", "has", "had", "are", "was", "were", "will", "would", "can",
    "could", "should", "know", "tell", "does", "did", "not", "all", "any",
    "friday", "please", "just", "like", "get", "make", "want", "need",
}


def _words(text: str) -> list:
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower())
            if len(w) > 2 and w not in STOPWORDS]


def _norm(text: str) -> str:
    """Separator-free, lowercase (Notes-10 Phase 3, §5) — so 'claude code',
    'claude_code' and 'claudecode' all compare equal in the slug/title channel."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


class KeywordRetriever(Retriever):
    # Relevance floor (Phase 1, Symptom 6). Without one, top-k always returns
    # SOMETHING — an incidental single-keyword hit ("meeting" appearing once in
    # an unrelated office-hours note) arrived stated as fact. A note must clear
    # this final score to survive: a lone body-term-once match scores ~1.0-1.5
    # (one occurrence x the <=1.5 recency boost) and is dropped, while a
    # filename match (+10/term), a repeated term, or several distinct terms
    # clear it easily. If nothing clears it, we return NOTHING rather than a
    # low-relevance note — the grounding contract (plan D2) prefers silence to a
    # weak guess. Tunable via memory.min_score; 0 restores the old behaviour.
    DEFAULT_MIN_SCORE = 2.0

    def __init__(self, brain_root, min_score: float = DEFAULT_MIN_SCORE):
        self.root = Path(brain_root)
        self.min_score = float(min_score)

    def _notes(self, include_test: bool = False):
        """All markdown notes, skipping git internals and Obsidian config.
        The test archive (memory provenance, Task 1) is excluded unless
        explicitly requested — test-session memories must never surface in a
        real session's recall as if they were lived history. character/ is
        excluded too: identity notes ride in the system prompt via their own
        layers every message, so retrieving them again is double-injection —
        and instruction-shaped queries ("end your reply with one line...")
        keyword-match identity text hard, dragging voice/rules prose into
        the notes slot where it fought a format contract (measured).
        observations/ is excluded because the typed-observation stream is a
        SEPARATE recall layer (Phase 3): it is served by ObservationRetriever
        (title-weighted, self-citing) under the `layered` retriever, so serving
        raw obs-id files here too would double-count them and flood recall with
        hex-named notes. Under a plain `keyword` retriever they simply don't
        surface — that IS the pre-Phase-3 behaviour."""
        for p in self.root.rglob("*.md"):
            rel = p.relative_to(self.root).as_posix()
            if rel.startswith((".git/", ".obsidian/", "character/",
                               "observations/")):
                continue
            if not include_test and rel.startswith("test_archive/"):
                continue
            # test_archive mirrors the real tree; keep its observations out too.
            if include_test and "/observations/" in "/" + rel:
                continue
            yield p, rel

    def retrieve(self, query: str, top_k: int,
                 include_test: bool = False) -> list[RetrievedNote]:
        terms = _words(query)
        if not terms:
            return []

        now = time.time()
        results = []
        for path, rel in self._notes(include_test):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lower = text.lower()

            # Name/title match bonus, now SEPARATOR-INSENSITIVE (Notes-10 Phase 3,
            # §5). Cluster C: "claude code" must find slug `claudecodeupgrade`
            # (already handled by the raw-path substring) AND the reverse — a
            # merged-word query `claudecode` must find a separated slug
            # `claude_code_upgrade`. So terms match against BOTH the raw path and
            # a compacted slug+title haystack. This title/slug channel is what
            # clears the min_score floor for a name hit; body scoring keeps the
            # floor, so an incidental single body-term match is still dropped.
            rel_stub = rel.rsplit(".", 1)[0]
            title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            name_norm = (_norm(rel_stub) + " "
                         + (_norm(title_m.group(1)) if title_m else ""))

            score = float(sum(lower.count(t) for t in terms))
            score += 10.0 * sum(1 for t in terms
                                if t in rel.lower() or t in name_norm)  # name match
            # The whole normalized query as one token — a merged-word name hit
            # (or its reverse) that per-term matching would miss.
            q_compact = "".join(terms)
            if len(q_compact) >= 4 and q_compact in name_norm:
                score += 10.0
            if score == 0:
                continue

            # Recency boost: notes touched in the last 30 days get up to +50%.
            age_days = (now - path.stat().st_mtime) / 86400
            score *= 1.0 + 0.5 * max(0.0, (30 - age_days) / 30)

            # Relevance floor: a weak, incidental match is worse than none —
            # it gets stated as fact. Drop anything below the threshold.
            if score < self.min_score:
                continue

            results.append(RetrievedNote(rel, self._snippet(text, terms), score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def _snippet(text: str, terms: list, max_lines: int = 8) -> str:
        """The lines that actually contain a query term (else the opening).
        Generous cap — a stingy snippet once hid a fact that WAS in the note,
        making FRIDAY deny knowing something she knew."""
        hits = [line.strip()[:200] for line in text.splitlines()
                if line.strip() and any(t in line.lower() for t in terms)]
        if not hits:
            hits = [text.strip()[:300]]
        return "\n".join(hits[:max_lines])

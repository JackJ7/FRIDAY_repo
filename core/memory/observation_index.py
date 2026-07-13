r"""
Observation FTS index — full-text recall across sessions (Notes-10 Phase 4 §3).

The typed-observation markdown files are the source of truth (see observations.py).
This module is a *derived*, rebuildable SQLite FTS5 index over their titles and
bodies, so FRIDAY can do real full-text search across every past session without
the vector/embedding dependency that remains Jack's call (the `Retriever` seam is
left exactly where it is — this index is reached through the explicit
`search_observations` tool, not silently folded into recall).

Why this shape, and how it stays honest:

  * **Derived + git-ignored.** The DB lives under `data\` (already ignored,
    .gitignore line 2). It carries NO fact the markdown doesn't — delete it and
    `rebuild()` reconstructs it from the brain. The observations remain the one
    source of truth (one fact, one place).

  * **Stdlib only.** Python's `sqlite3` with the FTS5 extension — no new
    dependency (CLAUDE.md: ask before adding a heavy dep). If a given Python
    build lacks FTS5, the index degrades honestly: `available` is False, writes
    are no-ops, and search says the index isn't available rather than crashing.

  * **Test-session isolation is structural.** A test session indexes into a
    SEPARATE db file (`obs_fts_test.db`) over its own test_archive/ view, so a
    test memory can never surface in a real session's search — the same wall the
    observation store and retriever already enforce, kept here by construction.
"""

import re
import sqlite3
from pathlib import Path

# Searchable columns are title+body; everything else is stored UNINDEXED so a hit
# can be rendered (and fetched in full by id) without a second lookup. The body
# column index (4, zero-based) is what snippet() highlights.
_CREATE = (
    "CREATE VIRTUAL TABLE obs USING fts5("
    "obs_id UNINDEXED, ts UNINDEXED, otype UNINDEXED, "
    "title, body, refs UNINDEXED, path UNINDEXED, "
    "tokenize='unicode61')"
)
_BODY_COL = 4

# A query term is any run of word characters; punctuation/FTS operators from the
# raw query are dropped so a user phrase can never become a malformed MATCH
# expression (the FTS analogue of parameterising a query).
_TERM = re.compile(r"\w+", re.UNICODE)


def _fts5_available() -> bool:
    """Whether this Python's sqlite build has FTS5 — probed once, in memory, so
    a build without it degrades to 'search not available' instead of crashing."""
    try:
        c = sqlite3.connect(":memory:")
        try:
            c.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
            return True
        finally:
            c.close()
    except sqlite3.Error:
        return False


class ObservationIndex:
    """The FTS index over the observation stream. Given the store (its single
    source of observations, session-routing included) and a data dir; picks a
    real-vs-test db file from the brain's session so the two never mix."""

    def __init__(self, store, data_dir: Path):
        self.store = store
        self.available = _fts5_available()
        base = Path(data_dir) / "obs_index"
        # The db mirrors the store's session view: a test session reads/writes a
        # separate file over its own archive, so it can't pollute the real index.
        name = "obs_fts_test.db" if store.brain.test_session else "obs_fts.db"
        self.db_path = base / name
        if self.available:
            base.mkdir(parents=True, exist_ok=True)

    # ---------- connection ----------

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(_CREATE.replace("CREATE VIRTUAL TABLE",
                                     "CREATE VIRTUAL TABLE IF NOT EXISTS"))
        return conn

    # ---------- maintenance ----------

    def ensure(self) -> None:
        """Build the index once if it doesn't exist yet (or is empty), then trust
        the incremental `index_one` writes to keep it fresh. Cheap, best-effort:
        a failure here must never block startup — search just degrades."""
        if not self.available:
            return
        try:
            conn = self._connect()
            try:
                (count,) = conn.execute("SELECT count(*) FROM obs").fetchone()
            finally:
                conn.close()
            if count == 0:
                self.rebuild()
        except sqlite3.Error:
            pass

    def rebuild(self) -> int:
        """Drop and rebuild the whole index from the observation files — the
        source of truth. Returns the number of observations indexed. This is the
        recovery path (delete the db, get it all back) and the correctness anchor
        (a from-scratch rebuild must match the incremental state)."""
        if not self.available:
            return 0
        conn = self._connect()
        try:
            conn.execute("DROP TABLE IF EXISTS obs")
            conn.execute(_CREATE)
            n = 0
            for o in self.store.all():          # session-scoped (real vs test)
                self._insert(conn, o)
                n += 1
            conn.commit()
            return n
        finally:
            conn.close()

    def index_one(self, obs) -> None:
        """Upsert one observation (called right after it's recorded). Best-effort:
        wrapped so a memory-index write can never break a live turn — the markdown
        is already the durable record; this index is a convenience on top."""
        if not self.available or obs is None:
            return
        try:
            conn = self._connect()
            try:
                self._delete(conn, obs.id)
                self._insert(conn, obs)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error:
            pass

    @staticmethod
    def _delete(conn, obs_id: str) -> None:
        conn.execute("DELETE FROM obs WHERE obs_id = ?", (obs_id,))

    @staticmethod
    def _insert(conn, o) -> None:
        conn.execute(
            "INSERT INTO obs(obs_id, ts, otype, title, body, refs, path) "
            "VALUES (?,?,?,?,?,?,?)",
            (o.id, o.ts, o.type, o.title, o.body,
             ", ".join(o.refs or []), o.path))

    # ---------- search ----------

    @staticmethod
    def _match_expr(query: str) -> str:
        """Turn free text into a safe FTS5 MATCH expression: each word term is
        quoted (so punctuation can't inject operators) and OR-joined for recall —
        bm25 ranking floats the best matches up. Returns "" when the query has no
        usable terms (the caller then returns 'no terms', never a bare MATCH)."""
        terms = _TERM.findall((query or "").lower())
        return " OR ".join(f'"{t}"' for t in terms)

    def search(self, query: str, limit: int = 6) -> list:
        """Full-text search over titles+bodies, best match first. Returns a list
        of dicts {id, ts, type, title, path, snippet}. Empty on no match, an
        unusable query, or an unavailable index (honest, never a fabricated hit)."""
        if not self.available:
            return []
        expr = self._match_expr(query)
        if not expr:
            return []
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT obs_id, ts, otype, title, path, "
                    f"snippet(obs, {_BODY_COL}, '[', ']', ' … ', 12) "
                    "FROM obs WHERE obs MATCH ? ORDER BY bm25(obs) LIMIT ?",
                    (expr, int(limit))).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return []
        return [
            {"id": r[0], "ts": r[1], "type": r[2], "title": r[3],
             "path": r[4], "snippet": r[5]}
            for r in rows
        ]

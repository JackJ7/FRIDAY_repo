r"""
Observation tools — the progressive-disclosure reads over the typed-observation
stream (Notes-10 Phase 4, claude-mem retrieval-economics port).

The session-start index (`engine._where_we_left_off`) lists recent observations
one cheap line each — `id | date | glyph | title` — so an older session is
*reachable* without stuffing its full body into every prompt. This module is the
other half of that bargain: the model pulls a full observation body ON DEMAND,
by id, only when a thread is actually relevant. That is claude-mem's "compact
index + fetch-by-id" pattern at FRIDAY's scale.

Kind is `internal`: an observation is FRIDAY's OWN provenance record, not
content from outside the trust boundary, so reading one neither taints the turn
nor pushes referents (same posture as read_brain over her own notes).
"""

# Be forgiving about how many ids a 14B crams into one call, but bound it so a
# single call can't dump the whole stream back into context (that would defeat
# the progressive-disclosure point the index exists for).
_MAX_IDS = 20


def register_observation_tools(registry, store, index=None):

    def _as_id_list(ids) -> list:
        """Accept the ids however the model hands them over — a real JSON array,
        a single string, or a comma/space/newline-separated blob — and return a
        de-duplicated list of candidate id strings (validation happens in the
        store's get()). Order is preserved so the reply follows what was asked."""
        if ids is None:
            return []
        if isinstance(ids, str):
            raw = ids.replace(",", " ").split()
        elif isinstance(ids, (list, tuple)):
            raw = []
            for item in ids:
                raw.extend(str(item).replace(",", " ").split())
        else:
            raw = str(ids).replace(",", " ").split()
        seen, out = set(), []
        for r in raw:
            r = r.strip()
            if r and r not in seen:
                seen.add(r)
                out.append(r)
        return out

    def get_observations(ids) -> str:
        """Fetch the full body of one or more observations by id. Honest about
        the ids it could not find so the model never invents a body it didn't
        get back (invariant 4)."""
        wanted = _as_id_list(ids)
        if not wanted:
            return ("No observation ids given. Pass the ids from the session-"
                    "start index (the `obs-...` at the start of each line).")
        capped = wanted[:_MAX_IDS]
        blocks, missing = [], []
        for oid in capped:
            obs = store.get(oid)
            if obs is None:
                missing.append(oid)
                continue
            refs = ("\n  refs: " + ", ".join(obs.refs)) if obs.refs else ""
            blocks.append(
                f"[{obs.cite()}]\n{obs.title}\n\n{obs.body.strip()}{refs}")
        out = []
        if blocks:
            out.append("\n\n".join(blocks))
        if missing:
            out.append("No observation found for: " + ", ".join(missing)
                       + ". (Check the id against the session-start index.)")
        if len(wanted) > _MAX_IDS:
            out.append(f"({len(wanted)} ids requested; showing the first "
                       f"{_MAX_IDS}.)")
        return "\n\n".join(out) if out else "No matching observations."

    registry.register(
        "get_observations",
        "Pull the full detail of one or more of YOUR observations by id (the "
        "`obs-...` ids listed in your session-start 'where you left off' index). "
        "The index shows only a title per entry to save space; call this when a "
        "thread from a past session is actually relevant and you need what "
        "happened, not just its title. Pass one id or several.",
        {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Observation ids to fetch, e.g. "
                                   "['obs-20260713-142233-a1b2']",
                },
            },
            "required": ["ids"],
        },
        get_observations,
        kind="internal",
    )

    # search_observations (Phase 4 §3) — full-text recall across every past
    # session, backed by the derived SQLite FTS5 index. Registers only when an
    # index is wired AND this Python build actually has FTS5; otherwise the tool
    # is simply ABSENT rather than present-but-broken (honest capability surface).
    if index is None or not getattr(index, "available", False):
        return

    def search_observations(query: str, limit: int = 6) -> str:
        """Search FRIDAY's observation stream by keywords across all sessions.
        Honest empty result when nothing matches (never a weak guess)."""
        try:
            limit = max(1, min(int(limit), 15))
        except (TypeError, ValueError):
            limit = 6
        hits = index.search(query, limit)
        if not hits:
            return (f"No observations matched '{query}'. (Full-text search over "
                    "your recorded observations found nothing — say so plainly.)")
        out = [f"{len(hits)} observation(s) matched '{query}':"]
        for h in hits:
            day = (h.get("ts") or "")[:10]
            out.append(f"- {h['id']} | {day} | {h.get('type','')} | "
                       f"{h['title']}\n    {h.get('snippet','').strip()}")
        out.append("(Use get_observations to pull the full body of any of these.)")
        return "\n".join(out)

    registry.register(
        "search_observations",
        "Full-text search across ALL of your past observations (every session), "
        "by keywords. Use this to answer 'have we discussed X before?' or to find "
        "an old thread the session-start index doesn't still show. Returns the "
        "matching observation ids + titles + snippets; pull full detail with "
        "get_observations. Honest empty when nothing matches.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Keywords to search for"},
                "limit": {"type": "integer",
                          "description": "Max results (default 6)"},
            },
            "required": ["query"],
        },
        search_observations,
        kind="internal",
    )

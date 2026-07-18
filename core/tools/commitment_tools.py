r"""
Commitment tools — how FRIDAY tracks what Jack said he'd do (spec §5).

Trust model:
- track_commitment with inferred=true  -> lands in "Pending confirmation";
  it only becomes a real commitment when Jack confirms it in the panel.
- track_commitment with inferred=false -> Jack explicitly asked in chat, so
  it goes straight to Open (an append — non-destructive).
- close_commitment                     -> state change, so it asks Jack via
  the normal confirm card before touching anything.
"""


from datetime import date, timedelta

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"]


def _resolve_due(raw: str) -> str:
    """Turn 'thursday' / 'tomorrow' / '2026-07-09' into an ISO date, in code —
    small models get weekday arithmetic wrong, so we don't let them do it."""
    s = (raw or "").strip().lower()
    if not s:
        return ""
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        pass
    today = date.today()
    if s == "today":
        return today.isoformat()
    if s == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    for i, name in enumerate(_WEEKDAYS):
        if name.startswith(s) or s.startswith(name):
            delta = (i - today.weekday()) % 7  # 0 = that day is today
            return (today + timedelta(days=delta)).isoformat()
    return ""  # unparseable — better no due date than a wrong one


def register_commitment_tools(registry, tracker, gate):

    def track_commitment(text: str, due: str = "", inferred: bool = True) -> str:
        c = tracker.add(text, due=_resolve_due(due), inferred=bool(inferred))
        if c.section == "pending":
            return (f"Tracked as pending confirmation (id {c.id}): \"{c.text}\""
                    + (f", due {c.due}" if c.due else "")
                    + ". Jack will confirm it in the panel — mention you've noted it.")
        return f"Tracked as open commitment (id {c.id}): \"{c.text}\"" + (
            f", due {c.due}" if c.due else "")

    def close_commitment(which: str) -> str:
        c, candidates = tracker.find_fuzzy(which)
        if c is None:
            if candidates:
                # Ambiguous fuzzy match: name the candidates and tell the
                # model to retry NOW with one's id (armor QB.1, the RA.1b
                # lesson — a bare error gets narrated to Jack as a dead end).
                listed = "; ".join(f"[{cd.id}] {cd.text}" for cd in candidates)
                return (f"ERROR: '{which}' matches {len(candidates)} tracked "
                        f"commitments: {listed}. RETRY NOW: call "
                        "close_commitment again with the id of the one Jack "
                        "means.")
            return (f"ERROR: no open/pending commitment matches '{which}'. "
                    f"Use list_commitments to see what's tracked.")
        # Commitments live in the brain (her domain, git-versioned): closing
        # one when Jack says it's done needs no extra card. Only close it when
        # he actually said so — never to tidy the list.
        gate.log.log("WRITE", f"close commitment {c.id} ({c.text[:40]})")
        tracker.close(c.id)
        return f"Closed: \"{c.text}\"."

    def list_commitments() -> str:
        return tracker.summary()

    registry.register(
        "track_commitment",
        "Track something Jack committed to ('I need to order X', 'I'll email Y "
        "Friday'). Set inferred=true when YOU noticed it in conversation (it "
        "then waits for Jack's confirmation); inferred=false only when Jack "
        "explicitly asked you to track it.",
        {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The commitment, short and concrete"},
                "due": {"type": "string", "description":
                        "The deadline EXACTLY as Jack said it — a weekday name "
                        "('thursday'), 'today', 'tomorrow', or an ISO date if he "
                        "gave one. Do not compute dates yourself."},
                "inferred": {"type": "boolean"},
            },
            "required": ["text"],
        },
        track_commitment,
        kind="action",
    )
    registry.register(
        "close_commitment",
        "Mark a tracked commitment done (asks Jack to confirm). Pass its id or "
        "a text fragment.",
        {
            "type": "object",
            "properties": {"which": {"type": "string"}},
            "required": ["which"],
        },
        close_commitment,
        kind="action",
    )
    registry.register(
        "list_commitments",
        "See the current tracked commitments and their state.",
        {"type": "object", "properties": {}},
        list_commitments,
    )

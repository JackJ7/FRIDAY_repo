r"""
Structured fields inside brain notes — the `- **Field:** value` lines.

Project notes carry machine-readable fields in plain markdown (editable in
Obsidian, parseable here): `- **Folder:** C:\...` and `- **Status:** active`.

Status semantics (the initiative rule):
  - "active" — or NO status line at all — means the project is fair game for
    proactive nudges (staleness, greetings, timelines).
  - ANY other value (reference, side-interest, paused, whatever FRIDAY or
    Jack coins) means: retrievable knowledge only. Never prompt to start or
    "get going on" it. The vocabulary is deliberately open — the code only
    ever asks "is it active?".
"""

import re


def slug(name: str) -> str:
    """'Doc Ock' -> 'doc_ock': safe for folder and note file names."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def get_field(text: str, field: str) -> str:
    """Read a `- **Field:** value` line from a note. '' if absent.

    Duplicates can no longer be written (brain.py guards them), but for any
    legacy note that still carries two copies, the LAST one wins — appends
    happen later in time, so the last line is the most recent belief."""
    hits = re.findall(rf"^\s*-\s*\*\*{re.escape(field)}:\*\*\s*(.+)$", text,
                      re.MULTILINE | re.IGNORECASE)
    return hits[-1].strip() if hits else ""


def existing_fields(text: str) -> list:
    """Canonical names of every `- **Field:** value` line, in note order."""
    return re.findall(r"^\s*-\s*\*\*([^*\n]+?):\*\*", text, re.MULTILINE)


def _field_tokens(name: str) -> frozenset:
    """Lowercased word set of a field name — separators squashed, so
    'Load cell', 'load-cell' and 'load cell rating' compare by content."""
    return frozenset(re.findall(r"[a-z0-9]+", name.lower()))


def match_field(text: str, field: str, value: str = "") -> list:
    """Existing field names that fuzzy-match `field` by token-set
    containment ('load cell' ⊂ 'load cell rating').

    The MEM-003 floor (armor PENDING-TASK PT.3): set_field()'s exact match
    meant a correction phrased as 'load cell rating' missed the seeded
    'Load cell' line and INSERTED a second, contradicting line — exactly
    what a correction must never do. The caller (update_note_field)
    branches on the hit count: one hit updates THAT line under its
    canonical name; several refuse with a which-ask corrective; zero fall
    through to today's insert (genuinely new fields must still work).

    The two containment directions are NOT symmetric (a deliberate
    tightening of the plan's prep design — the collision it prevents is in
    the suite itself):
      * given ⊆ existing ('rating' → 'Load cell rating'): the model
        SHORTENED a name that exists — always a match.
      * given ⊋ existing ('load cell rating' → 'Load cell'): the model
        EXTENDED a name — a match ONLY when the new value shares vocabulary
        with the line's current value ('50 kg rated' vs '20 kg rated'
        share kg/rated). Without that check, writing a genuinely NEW
        sibling field ('Load cell amplifier: HX711' beside 'Load cell:
        20 kg rated') would silently DESTROY the existing fact — the exact
        corruption this floor exists to prevent."""
    want = _field_tokens(field)
    if not want:
        return []
    new_val = _field_tokens(value)
    hits, seen = [], set()
    for name in existing_fields(text):
        have = _field_tokens(name)
        if not have or name.lower() in seen:
            continue
        if want <= have:
            matched = True
        elif have < want:
            matched = bool(new_val & _field_tokens(get_field(text, name)))
        else:
            matched = False
        if matched:
            hits.append(name)
            seen.add(name.lower())
    return hits


def set_field(text: str, field: str, value: str) -> str:
    """Set (replace or insert) a `- **Field:** value` line, returning the new
    note text. Inserts after the title line when the field doesn't exist yet."""
    pattern = re.compile(rf"^(\s*-\s*\*\*{re.escape(field)}:\*\*\s*).+$",
                         re.MULTILINE | re.IGNORECASE)
    if pattern.search(text):
        return pattern.sub(rf"\g<1>{value}", text, count=1)

    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = i + 1
            break
    # Skip the blank line after the title so the field sits with the body.
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    lines.insert(insert_at, f"- **{field}:** {value}")
    if insert_at + 1 < len(lines) and lines[insert_at + 1].strip():
        lines.insert(insert_at + 1, "")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def project_status(text: str) -> str:
    """A project's status; missing/empty = 'active' (the default)."""
    return get_field(text, "Status").lower() or "active"


def is_nudgeable(text: str) -> bool:
    """May FRIDAY proactively push this project? Only when it's active."""
    return project_status(text) == "active"

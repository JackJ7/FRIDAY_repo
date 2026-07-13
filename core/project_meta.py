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

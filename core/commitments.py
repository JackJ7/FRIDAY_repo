r"""
Commitment tracker (spec §5) — FRIDAY's tracked to-do state, in the brain.

Everything lives in brain\commitments.md: human-readable markdown that Jack
can edit in Obsidian and FRIDAY parses back. Three sections:

  ## Open                  confirmed commitments she follows up on
  ## Pending confirmation  items she inferred from conversation — they only
                           become Open when Jack confirms (panel or chat)
  ## Done                  closed items (last 20 kept)

Write policy (the §6 note): this file is rewritten by the tracker directly,
WITHOUT a per-write confirmation card. That is a deliberate, documented
exception to the overwrite rule: every mutation is either an append (a new
item) or a state change Jack explicitly triggered (a panel click or a
chat-confirmed tool call), the file is git-committed on every change so
nothing is ever lost, and every write is logged. Prompting "Allow?" for each
checkbox tick would train Jack to click through prompts — worse for safety.
"""

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Commitment:
    text: str
    section: str = "open"            # open | pending | done
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:4])
    due: str = ""                    # ISO date or ""
    added: str = field(default_factory=lambda: date.today().isoformat())
    closed: str = ""

    def age_days(self) -> int:
        try:
            return (date.today() - date.fromisoformat(self.added)).days
        except ValueError:
            return 0

    def overdue(self) -> bool:
        try:
            return bool(self.due) and date.fromisoformat(self.due) < date.today()
        except ValueError:
            return False

    def due_today(self) -> bool:
        return self.due == date.today().isoformat()


# One task line:  - [ ] text | due:2026-07-10 | added:2026-07-06 | id:3f2a
_LINE = re.compile(r"^- \[( |x)\] (.+)$")


class CommitmentTracker:
    FILE = "commitments.md"

    def __init__(self, brain):
        self.brain = brain
        self._lock = threading.Lock()  # panel clicks and chat tools can overlap

    # ---------- parsing / rendering ----------

    def _parse(self) -> list:
        try:
            text = self.brain.read_note(self.FILE)
        except FileNotFoundError:
            return []
        items, section = [], "open"
        for line in text.splitlines():
            low = line.lower()
            if low.startswith("## open"):
                section = "open"
            elif low.startswith("## pending"):
                section = "pending"
            elif low.startswith("## done"):
                section = "done"
            m = _LINE.match(line.strip())
            if not m:
                continue
            checked, rest = m.group(1) == "x", m.group(2)
            parts = [p.strip() for p in rest.split("|")]
            c = Commitment(text=parts[0], section="done" if checked else section)
            for p in parts[1:]:
                if ":" in p:
                    key, val = p.split(":", 1)
                    key, val = key.strip().lower(), val.strip()
                    if key in ("due", "added", "closed", "id"):
                        setattr(c, "id" if key == "id" else key, val)
            items.append(c)
        return items

    @staticmethod
    def _line(c: Commitment) -> str:
        box = "x" if c.section == "done" else " "
        parts = [f"- [{box}] {c.text}"]
        if c.due:
            parts.append(f"due:{c.due}")
        parts.append(f"added:{c.added}")
        if c.closed:
            parts.append(f"closed:{c.closed}")
        parts.append(f"id:{c.id}")
        return " | ".join(parts)

    def _render(self, items: list) -> str:
        def sect(name):
            return [self._line(c) for c in items if c.section == name]
        done = sect("done")[-20:]  # keep the file from growing forever
        return (
            "# Commitments\n\n"
            "*Tracked by FRIDAY. Edit freely in Obsidian — she parses the "
            "`- [ ]` lines; metadata rides after `|` separators.*\n\n"
            "## Open\n" + ("\n".join(sect("open")) or "*(nothing open)*") + "\n\n"
            "## Pending confirmation\n"
            "*(inferred from conversation — confirm or dismiss in the panel)*\n"
            + ("\n".join(sect("pending")) or "*(none)*") + "\n\n"
            "## Done\n" + ("\n".join(done) or "*(none yet)*") + "\n"
        )

    def _save(self, items: list, message: str):
        self.brain.system_write(self.FILE, self._render(items), summary=message)

    # ---------- mutations (each one git-commits) ----------

    def add(self, text: str, due: str = "", inferred: bool = False) -> Commitment:
        with self._lock:
            items = self._parse()
            # Don't duplicate an existing open/pending item with the same text.
            for c in items:
                if c.section != "done" and c.text.lower() == text.strip().lower():
                    return c
            c = Commitment(text=text.strip(), due=due.strip(),
                           section="pending" if inferred else "open")
            items.append(c)
            self._save(items, f"Track commitment: {c.text[:60]}")
            return c

    def _move(self, cid: str, section: str, message: str):
        with self._lock:
            items = self._parse()
            for c in items:
                if c.id == cid:
                    c.section = section
                    if section == "done":
                        c.closed = date.today().isoformat()
                    self._save(items, message.format(text=c.text[:60]))
                    return c
        return None

    def confirm(self, cid: str):
        return self._move(cid, "open", "Confirm commitment: {text}")

    def close(self, cid: str):
        return self._move(cid, "done", "Close commitment: {text}")

    def decline(self, cid: str):
        """Jack says an inferred item isn't real — remove it entirely."""
        with self._lock:
            items = self._parse()
            keep = [c for c in items if c.id != cid]
            if len(keep) != len(items):
                gone = next(c for c in items if c.id == cid)
                self._save(keep, f"Dismiss inferred commitment: {gone.text[:60]}")
                return gone
        return None

    def find(self, needle: str):
        """Match by id or by text fragment (for chat: 'mark the motor one done')."""
        needle = needle.strip().lower()
        for c in self._parse():
            if c.section != "done" and (c.id == needle or needle in c.text.lower()):
                return c
        return None

    # ---------- read views ----------

    def open_items(self) -> list:
        return [c for c in self._parse() if c.section == "open"]

    def pending_items(self) -> list:
        return [c for c in self._parse() if c.section == "pending"]

    def summary(self) -> str:
        """Compact state for the system prompt — lets FRIDAY follow up naturally."""
        items = self._parse()
        lines = []
        for c in items:
            if c.section == "open":
                bits = [c.text, f"open {c.age_days()}d"]
                if c.overdue():
                    bits.append(f"OVERDUE (was due {c.due})")
                elif c.due:
                    bits.append(f"due {c.due}")
                lines.append(f"- [{c.id}] " + " — ".join(bits))
        for c in items:
            if c.section == "pending":
                lines.append(f"- [{c.id}] AWAITING JACK'S CONFIRMATION (panel): {c.text}"
                             + (f" — due {c.due}" if c.due else ""))
        return "\n".join(lines) if lines else "(no tracked commitments)"

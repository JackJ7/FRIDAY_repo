r"""
Playbooks — reusable procedures FRIDAY writes, refines, retrieves, and follows.

Plain markdown in brain\playbooks\, one file per procedure, git-versioned and
Obsidian-editable. Two ways a playbook gets here:
  - FRIDAY authors one (write_playbook) after doing something repeatable —
    rendered through the template below so her playbooks stay consistent.
  - Jack SEEDS one: drop any .md into brain\playbooks\ and the index picks it
    up on the next message — no import step. The parser is tolerant of
    foreign formats (uses **Goal:** / **When to use:** fields when present,
    the first paragraph otherwise).

The index (name + when-to-use) rides in the system prompt so matching happens
every turn; full content is read on demand and is also reachable through
normal brain search. Files starting with "_" (like _template.md) are ignored.
"""

import re
from datetime import date
from pathlib import Path

from core.project_meta import get_field, slug

TEMPLATE = """\
# Playbook: {name}

- **Goal:** {goal}
- **When to use:** {when_to_use}
- **Origin:** {origin}

## Steps
{steps}

## Checks
{checks}

## Notes
{notes}
"""


class Playbooks:
    def __init__(self, brain):
        self.brain = brain

    def _dir(self) -> Path:
        return self.brain.root / "playbooks"

    def _files(self):
        d = self._dir()
        if not d.is_dir():
            return []
        return [p for p in sorted(d.glob("*.md")) if not p.name.startswith("_")]

    # ---------- index (system prompt) ----------

    def index(self) -> list:
        """[{name, file, goal, when}] for every playbook, seeded or authored."""
        out = []
        for p in self._files():
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = [l.strip() for l in text.splitlines()]
            title = next((l[2:].replace("Playbook:", "").strip()
                          for l in lines if l.startswith("# ")),
                         p.stem.replace("_", " "))
            goal = get_field(text, "Goal")
            when = get_field(text, "When to use")
            if not (goal or when):  # foreign format — first real paragraph
                goal = next((l for l in lines
                             if l and not l.startswith(("#", "-", "*"))), "")[:120]
            out.append({"name": title, "file": p.stem,
                        "goal": goal[:120], "when": when[:120]})
        return out

    def index_text(self) -> str:
        # The `read_playbook "<file>"` cue is deliberate: the model tended to
        # "run" a playbook from this one-line title alone (improvising a generic
        # procedure) instead of loading the real steps. Naming the exact call
        # it must make, inline, nudges it to actually read first.
        return "\n".join(
            f'- {e["name"]} [{e["file"]}]: {e["when"] or e["goal"]} '
            f'— read_playbook "{e["file"]}" to load its steps before running it'
            for e in self.index())

    BUDGET_CHARS = 6000

    def prompt_block(self, budget_chars: int = None) -> str:
        """What rides in the system prompt each turn. For a SMALL playbook set
        we inject each playbook's FULL text, so following one never depends on
        the model remembering to call read_playbook — a 14B recognizes the
        matching playbook and announces it, then improvises the steps instead
        of reading them. With the steps already in context, it follows the real
        procedure. For a large set (the real brain crossed the budget when
        trade_study_ahp + artifact_review + max_effort landed) the block is
        the index, and match() injects the ONE fitting playbook per message —
        the PLB-004 guarantee kept, at any set size."""
        budget_chars = budget_chars or self.BUDGET_CHARS
        files = self._files()
        if not files:
            # Say the set is EMPTY rather than staying silent: with no block
            # at all she invented one ("Running the *motor driver bringup*
            # playbook") when Jack described procedural work — announcing a
            # playbook that doesn't exist is a fabrication (invariant 4).
            return ("## Your playbooks\nYou have NO playbooks yet — never "
                    "announce or claim to run one. When repeatable work shows "
                    "up, capture it with write_playbook instead.")
        contents = [p.read_text(encoding="utf-8", errors="replace").strip()
                    for p in files]
        if sum(len(c) for c in contents) <= budget_chars:
            return ("## Your playbooks (reusable procedures — when a task fits "
                    "one, FOLLOW it step by step and say which you're running; "
                    "the full steps are right here, no need to look them up)\n\n"
                    + "\n\n---\n\n".join(contents))
        return ("## Your playbooks (index — the matching playbook's full "
                "steps are injected automatically when a task fits one; "
                "read_playbook loads any other by name)\n" + self.index_text())

    def _over_budget(self) -> bool:
        return sum(len(p.read_text(encoding="utf-8", errors="replace").strip())
                   for p in self._files()) > self.BUDGET_CHARS

    # Function words carry no topic signal — counting them lets a message tie
    # the right playbook purely on shared "the"/"and"/"for". A real case: a
    # commit/push playbook tied max_effort at 2 on {the, and} against a
    # thruster-creep query and won on alphabetical order. Drop them so overlap
    # reflects subject, not grammar.
    _STOPWORDS = frozenset(
        "the and for you your that this with have has had are was were will "
        "not but its it's from into out off use used using work works when "
        "any all one two his her him she they them then than there here what "
        "which who whom whose why how does did done can could should would "
        "about over under been being get got now new old per via etc".split())

    def match(self, text: str, min_score: int = 2):
        """The best-matching playbook's (name, full text) for a message, or
        None. Only active when the set is OVER the full-injection budget —
        under it, prompt_block already carries every playbook in full and a
        second copy would just burn context. Same conservative keyword-
        overlap approach as Skills.match (name + goal + when-to-use), so
        chitchat and simple questions never drag a procedure in."""
        if not self._over_budget():
            return None
        tokens = {w for w in re.findall(r"[a-z0-9_]+", text.lower())
                  if len(w) > 2 and w not in self._STOPWORDS}
        if not tokens:
            return None
        best, best_score = None, 0
        for e in self.index():
            sig = {w for w in re.findall(
                r"[a-z0-9_]+", f'{e["name"]} {e["goal"]} {e["when"]}'.lower())
                if len(w) > 2}
            score = len(tokens & sig)
            if score > best_score:
                best, best_score = e, score
        if best is None or best_score < min_score:
            return None
        return best["name"], (self._dir() / f"{best['file']}.md").read_text(
            encoding="utf-8", errors="replace")

    # ---------- read / write ----------

    def read(self, name: str) -> str:
        """Full playbook by file stem, title, or fragment."""
        needle = slug(name)
        for p in self._files():
            if needle in slug(p.stem):
                return p.read_text(encoding="utf-8", errors="replace")
        for e in self.index():
            if needle in slug(e["name"]):
                return (self._dir() / f"{e['file']}.md").read_text(
                    encoding="utf-8", errors="replace")
        return (f"ERROR: no playbook matching '{name}'. "
                f"list_playbooks shows what exists.")

    def write(self, name: str, goal: str, when_to_use: str, steps: list,
              checks: list, notes: str = "") -> str:
        """Author or refine a playbook. Rendered through the template in code
        so structure stays consistent regardless of what the model produces."""
        rel = f"playbooks/{slug(name)}.md"
        existing = None
        try:
            existing = self.brain.read_note(rel)  # also satisfies the
        except FileNotFoundError:                 # read-before-overwrite guard
            pass

        origin = f"authored by FRIDAY, {date.today()}"
        if existing:
            prior = get_field(existing, "Origin")
            origin = (prior + f"; refined {date.today()}") if prior else origin

        content = TEMPLATE.format(
            name=name.strip(),
            goal=goal.strip(),
            when_to_use=when_to_use.strip(),
            origin=origin,
            steps="\n".join(f"{i}. {s.strip()}"
                            for i, s in enumerate(steps or [], 1)) or "1. (none)",
            checks="\n".join(f"- {c.strip()}" for c in (checks or [])) or "- (none)",
            notes=notes.strip() or "-",
        )
        mode = "overwrite" if existing else "create"
        self.brain.write_note(rel, content, mode=mode,
                              summary=f"Playbook {'refined' if existing else 'authored'}: {name}")
        return (f"Playbook {'refined' if existing else 'saved'}: {rel} — "
                f"mention it's captured and editable in Obsidian.")

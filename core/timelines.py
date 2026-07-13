r"""
Project-timeline engine (spec §7) — flexible milestones, not a rigid Gantt.

One note per project in brain\timelines\<project>.md, human-editable in
Obsidian, same proven line format as the commitment tracker:

  - [ ] First silicone cast | target:2026-08-02 | after:a1b2 | id:c3d4
  - [x] Actuation concept chosen | target:2026-07-01 | done:2026-06-28 | id:e5f6

`after:` encodes a dependency. THE MODEL NARRATES, THE CODE COMPUTES: slip
math (what's overdue, what it pushes downstream) is deterministic — overdue
by N days projects every transitively-dependent milestone N days later.
"""

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date

from core.project_meta import slug


@dataclass
class Milestone:
    text: str
    target: str = ""                 # ISO date
    after: str = ""                  # id of the milestone this depends on
    done: str = ""                   # ISO date when completed ("" = open)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:4])

    def days_late(self) -> int:
        """Days past target for an UNDONE milestone (0 if on time/no target)."""
        if self.done or not self.target:
            return 0
        try:
            return max(0, (date.today() - date.fromisoformat(self.target)).days)
        except ValueError:
            return 0


_LINE = re.compile(r"^- \[( |x)\] (.+)$")


class TimelineTracker:
    def __init__(self, brain):
        self.brain = brain
        self._lock = threading.Lock()

    def _note(self, project: str) -> str:
        return f"timelines/{slug(project)}.md"

    # ---------- parse / render ----------

    def milestones(self, project: str) -> list:
        try:
            text = self.brain.read_note(self._note(project))
        except FileNotFoundError:
            return []
        out = []
        for line in text.splitlines():
            m = _LINE.match(line.strip())
            if not m:
                continue
            checked, rest = m.group(1) == "x", m.group(2)
            parts = [p.strip() for p in rest.split("|")]
            ms = Milestone(text=parts[0])
            for p in parts[1:]:
                if ":" in p:
                    key, val = p.split(":", 1)
                    key, val = key.strip().lower(), val.strip()
                    if key in ("target", "after", "done", "id"):
                        setattr(ms, key, val)
            if checked and not ms.done:
                ms.done = "?"  # Jack ticked the box by hand without a date
            out.append(ms)
        return out

    @staticmethod
    def _line(ms: Milestone) -> str:
        parts = [f"- [{'x' if ms.done else ' '}] {ms.text}"]
        if ms.target:
            parts.append(f"target:{ms.target}")
        if ms.after:
            parts.append(f"after:{ms.after}")
        if ms.done and ms.done != "?":
            parts.append(f"done:{ms.done}")
        parts.append(f"id:{ms.id}")
        return " | ".join(parts)

    def _save(self, project: str, items: list, message: str):
        body = (f"# Timeline — {project}\n\n"
                f"*Milestones, flexible by design. Edit freely in Obsidian; "
                f"FRIDAY parses the `- [ ]` lines. `after:<id>` marks a "
                f"dependency.*\n\n"
                + "\n".join(self._line(ms) for ms in items) + "\n")
        self.brain.system_write(self._note(project), body, summary=message)

    # ---------- mutations ----------

    def create(self, project: str, milestones: list) -> str:
        """milestones: [{text, target, after_index?}] in order. Refuses to
        clobber an existing timeline — that's what update/add are for."""
        with self._lock:
            if self.milestones(project):
                return (f"ERROR: '{project}' already has a timeline. Use "
                        f"update_milestone to change it, or ask Jack before replacing.")
            items = []
            for m in milestones:
                ms = Milestone(text=str(m.get("text", "")).strip(),
                               target=str(m.get("target", "")).strip())
                ai = m.get("after_index")
                if ai is not None and 0 <= int(ai) < len(items):
                    ms.after = items[int(ai)].id
                items.append(ms)
            self._save(project, items, f"Create timeline for {project} "
                                       f"({len(items)} milestones)")
            return (f"Timeline created for {project}: {len(items)} milestones "
                    f"in timelines/{slug(project)}.md")

    def update(self, project: str, which: str, done: bool = None,
               new_target: str = "", remove: bool = False,
               shift_downstream: bool = False) -> str:
        with self._lock:
            items = self.milestones(project)
            needle = which.strip().lower()
            ms = next((m for m in items
                       if m.id == needle or needle in m.text.lower()), None)
            if ms is None:
                return (f"ERROR: no milestone matching '{which}' in the "
                        f"{project} timeline.")
            if remove:
                items = [m for m in items if m.id != ms.id]
                for m in items:      # don't leave dangling dependencies
                    if m.after == ms.id:
                        m.after = ms.after
                self._save(project, items, f"{project}: remove milestone '{ms.text[:40]}'")
                return f"Removed '{ms.text}' from the {project} timeline."
            changes = []
            if done is not None:
                ms.done = date.today().isoformat() if done else ""
                changes.append("done" if done else "reopened")
            if new_target:
                old_target = ms.target
                ms.target = new_target.strip()
                changes.append(f"target -> {ms.target}")
                # Re-plan the chain deterministically: every transitively
                # dependent open milestone moves by the same delta.
                if shift_downstream and old_target:
                    try:
                        from datetime import timedelta
                        delta = (date.fromisoformat(ms.target)
                                 - date.fromisoformat(old_target)).days
                    except ValueError:
                        delta = 0
                    if delta:
                        dependents, frontier = set(), {ms.id}
                        while frontier:
                            frontier = {m.id for m in items
                                        if m.after in frontier
                                        and m.id not in dependents and not m.done}
                            dependents |= frontier
                        for m in items:
                            if m.id in dependents and m.target:
                                try:
                                    m.target = (date.fromisoformat(m.target)
                                                + timedelta(days=delta)).isoformat()
                                except ValueError:
                                    pass
                        changes.append(f"{len(dependents)} downstream shifted "
                                       f"{delta:+d}d")
            self._save(project, items,
                       f"{project}: {ms.text[:40]} ({', '.join(changes) or 'touched'})")
            return f"Updated '{ms.text}': {', '.join(changes) or 'no change'}."

    def add(self, project: str, text: str, target: str = "", after: str = "") -> str:
        with self._lock:
            items = self.milestones(project)
            ms = Milestone(text=text.strip(), target=target.strip())
            if after:
                dep = next((m for m in items if m.id == after.strip().lower()
                            or after.strip().lower() in m.text.lower()), None)
                if dep:
                    ms.after = dep.id
            items.append(ms)
            self._save(project, items, f"{project}: add milestone '{text[:40]}'")
            return f"Added '{ms.text}' to the {project} timeline (id {ms.id})."

    # ---------- slip math (deterministic) ----------

    def slips(self, project: str) -> list:
        """Overdue milestones and their projected downstream impact.
        [{milestone, target, late_days, pushes: [{text, target, projected}]}]"""
        items = self.milestones(project)
        by_id = {m.id: m for m in items}

        def downstream(mid, seen=None):
            seen = seen or set()
            for m in items:
                if m.after == mid and m.id not in seen and not m.done:
                    seen.add(m.id)
                    downstream(m.id, seen)
            return seen

        out = []
        for m in items:
            late = m.days_late()
            if not late:
                continue
            pushes = []
            for did in downstream(m.id):
                d = by_id[did]
                projected = ""
                if d.target:
                    try:
                        from datetime import timedelta
                        projected = (date.fromisoformat(d.target)
                                     + timedelta(days=late)).isoformat()
                    except ValueError:
                        pass
                pushes.append({"text": d.text, "target": d.target,
                               "projected": projected})
            out.append({"milestone": m.text, "id": m.id, "target": m.target,
                        "late_days": late, "pushes": pushes})
        return out

    def projects_with_timelines(self) -> list:
        return [rel.split("/", 1)[1][:-3] for rel in self.brain.list_notes()
                if rel.startswith("timelines/") and rel.endswith(".md")]

    def text_summary(self, project: str) -> str:
        """Compact timeline state for prompts: every milestone + slip lines."""
        items = self.milestones(project)
        if not items:
            return ""
        lines = [f"Timeline for {project}:"]
        for m in items:
            state = f"done {m.done}" if m.done else (
                f"OVERDUE {m.days_late()}d (target {m.target})" if m.days_late()
                else f"target {m.target or 'unset'}")
            lines.append(f"- [{m.id}] {m.text} — {state}")
        for s in self.slips(project):
            if s["pushes"]:
                lines.append(
                    f"SLIP: '{s['milestone']}' is {s['late_days']}d late, which "
                    f"pushes: " + "; ".join(
                        f"{p['text']} ({p['target']} -> ~{p['projected']})"
                        for p in s["pushes"] if p["projected"]))
        return "\n".join(lines)

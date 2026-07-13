r"""
Accountability (spec §4) — what feeds the "Needs You" panel and the briefing.

Pure local computation: scans the brain for stale/stub project notes and
unsorted inbox items, combines them with the commitment tracker's state, and
keeps the small bits of app state (Do Not Disturb, what's been pinged, when
the last briefing ran) in data\app_state.json.

Pacing rules live here so high initiative never becomes noise:
- the panel populates quietly (UI polls it),
- real-time pings fire at most once per day per commitment, only when
  something is actually due/overdue, and never during DND,
- the daily briefing runs once per day at the first idle moment.
"""

import json
from datetime import date, datetime
from pathlib import Path

from core.project_meta import is_nudgeable, project_status


class Accountability:
    def __init__(self, brain, tracker, config, data_dir: Path, timelines=None):
        self.brain = brain
        self.tracker = tracker
        self.timelines = timelines   # TimelineTracker (Stage 4); may be None
        self.cfg = config.get("accountability", {})
        self.state_path = Path(data_dir) / "app_state.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- persisted app state ----------

    def _state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_state(self, state: dict):
        # Write-through (fsync) — app state must survive a hard kill too.
        with open(self.state_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(state, indent=2))
            f.flush()
            import os
            os.fsync(f.fileno())

    @property
    def dnd(self) -> bool:
        return bool(self._state().get("dnd", False))

    def set_dnd(self, value: bool) -> bool:
        state = self._state()
        state["dnd"] = bool(value)
        self._save_state(state)
        return state["dnd"]

    # ---------- the "Needs You" panel ----------

    def _stale_notes(self) -> list:
        """Project notes untouched too long or still stubs, plus inbox strays.
        ONLY nudgeable (active) projects count — a reference project's stub is
        a knowledge source, not something going stale."""
        days_limit = self.cfg.get("staleness_days", 14)
        now = datetime.now().timestamp()
        out = []
        for rel in self.brain.list_notes():
            p = self.brain.root / rel
            if rel.startswith("projects/"):
                text = p.read_text(encoding="utf-8", errors="replace")
                if not is_nudgeable(text):
                    continue
                age_days = int((now - p.stat().st_mtime) / 86400)
                is_stub = "stub" in text.lower()
                if age_days >= days_limit or is_stub:
                    out.append({"path": rel, "days": age_days, "stub": is_stub})
            elif rel.startswith("inbox/"):
                out.append({"path": rel, "days": 0, "stub": False, "inbox": True})
        return out

    def project_statuses(self) -> dict:
        """Status of every project note (missing field = 'active')."""
        out = {}
        for rel in self.brain.list_notes():
            if rel.startswith("projects/"):
                text = (self.brain.root / rel).read_text(
                    encoding="utf-8", errors="replace")
                out[rel] = project_status(text)
        return out

    def _nudgeable_timelines(self) -> list:
        """Projects that have a timeline AND are active (status rule)."""
        if self.timelines is None:
            return []
        out = []
        for proj in self.timelines.projects_with_timelines():
            note = self.brain.root / "projects" / f"{proj}.md"
            if note.exists() and not is_nudgeable(
                    note.read_text(encoding="utf-8", errors="replace")):
                continue
            out.append(proj)
        return out

    def timeline_alerts(self) -> list:
        """Overdue milestones (active projects only) for the panel."""
        alerts = []
        for proj in self._nudgeable_timelines():
            for s in self.timelines.slips(proj):
                alerts.append({
                    "project": proj, "text": s["milestone"],
                    "target": s["target"], "late": s["late_days"],
                    "pushes": len(s["pushes"]),
                })
        alerts.sort(key=lambda a: -a["late"])
        return alerts

    def needs_you(self) -> dict:
        """Everything the panel shows. Cheap (file scans only), safe to poll."""
        pending = [{"id": c.id, "text": c.text, "due": c.due}
                   for c in self.tracker.pending_items()]
        open_items = [{"id": c.id, "text": c.text, "due": c.due,
                       "overdue": c.overdue(), "due_today": c.due_today(),
                       "age": c.age_days()}
                      for c in self.tracker.open_items()]
        # Overdue first, then soonest due, then oldest.
        open_items.sort(key=lambda c: (not c["overdue"], c["due"] or "9999", -c["age"]))
        return {
            "pending": pending,
            "open": open_items,
            "timeline": self.timeline_alerts(),
            "stale": self._stale_notes(),
            "dnd": self.dnd,
        }

    def text_summary(self) -> str:
        """Compact accountability state for the system prompt / briefing."""
        lines = [self.tracker.summary()]
        statuses = self.project_statuses()
        if statuses:
            lines.append(
                "Project statuses (only ACTIVE projects may be proactively "
                "nudged or suggested as things to start/work on; every other "
                "status means retrievable context only):\n"
                + "\n".join(f"- {rel}: {st}" for rel, st in sorted(statuses.items())))
        for proj in self._nudgeable_timelines():
            summary = self.timelines.text_summary(proj)
            if summary:
                lines.append(summary)
        stale = self._stale_notes()
        if stale:
            frag = []
            for s in stale[:8]:
                if s.get("inbox"):
                    frag.append(f"{s['path']} (unsorted inbox note)")
                elif s["stub"]:
                    frag.append(f"{s['path']} (still a stub)")
                else:
                    frag.append(f"{s['path']} (untouched {s['days']}d)")
            lines.append("Stale/needs attention:\n" + "\n".join(f"- {f}" for f in frag))
        return "\n".join(lines)

    # ---------- pacing: pings + briefing ----------

    def unpinged(self, kind: str, ids: list) -> list:
        """Generic once-a-day ping pacing: of `ids`, return the ones not yet
        pinged today under this kind, and mark them pinged."""
        today = date.today().isoformat()
        state = self._state()
        already = set(state.get("pinged_" + kind, {}).get(today, []))
        new = [i for i in ids if i not in already]
        if new:
            state["pinged_" + kind] = {today: sorted(already | set(new))}
            self._save_state(state)
        return new

    def due_pings(self) -> list:
        """Commitments due today/overdue that haven't been pinged today."""
        hits = {c.id: c for c in self.tracker.open_items()
                if c.due_today() or c.overdue()}
        return [hits[i] for i in self.unpinged("commitment", list(hits))]

    def briefing_due(self) -> bool:
        after_hour = self.cfg.get("briefing_hour", 9)
        state = self._state()
        return (state.get("last_briefing") != date.today().isoformat()
                and datetime.now().hour >= after_hour)

    def mark_briefed(self):
        state = self._state()
        state["last_briefing"] = date.today().isoformat()
        self._save_state(state)

r"""
Timeline tools (spec §7) — scope in, milestones out, slips flagged.

Timelines are brain notes (her domain: free, logged, git-committed). Dates
arrive as Jack said them and get resolved in code where possible — the model
never does calendar arithmetic.
"""

import re
from datetime import date, timedelta

from core.tools.commitment_tools import _resolve_due


def _resolve_target(raw: str) -> str:
    """ISO dates pass through; weekday words resolve; 'in N weeks/days'
    resolves as an offset from today (in code — the model never does date
    math); anything else ('mid-August') stays as given — a fuzzy target
    beats a wrong one."""
    s = (raw or "").strip()
    m = re.match(r"^(?:in\s+|\+)?(\d+)\s*(day|week|month)s?"
                 r"(?:\s+(?:out|from\s+(?:today|now)))?$", s.lower())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = n * {"day": 1, "week": 7, "month": 30}[unit]
        return (date.today() + timedelta(days=days)).isoformat()
    resolved = _resolve_due(s)
    return resolved if resolved else s


def register_timeline_tools(registry, timelines):

    def create_timeline(project: str, milestones: list, horizon: str = "") -> str:
        cleaned = []
        for m in milestones or []:
            if isinstance(m, dict) and m.get("text"):
                m = dict(m)
                m["target"] = _resolve_target(str(m.get("target", "")))
                cleaned.append(m)
        if not cleaned:
            return "ERROR: no milestones given. Pass [{text, target, after_index?}, ...]."

        # Deterministic backstop: milestones that arrived without a usable
        # date get spaced evenly across the horizon ("six weeks" -> equal
        # steps). The code schedules; the model only describes.
        import re as _re
        end = _resolve_target(horizon) or _resolve_target("4 weeks")
        if not _re.match(r"^\d{4}-\d{2}-\d{2}$", end):
            end = _resolve_target("4 weeks")
        span = max(1, (date.fromisoformat(end) - date.today()).days)
        undated = [m for m in cleaned if not _re.match(r"^\d{4}-\d{2}-\d{2}$",
                                                       m.get("target", ""))]
        for i, m in enumerate(undated):
            step = round(span * (i + 1) / len(undated))
            m["target"] = (date.today() + timedelta(days=step)).isoformat()

        # Milestones in a build usually block each other. If the model gave
        # NO dependencies at all, default to a linear chain (each after the
        # previous); any explicit after_index means it thought about it.
        if not any("after_index" in m for m in cleaned):
            for i, m in enumerate(cleaned[1:], start=1):
                m["after_index"] = i - 1

        return timelines.create(project, cleaned)

    def read_timeline(project: str) -> str:
        summary = timelines.text_summary(project)
        return summary or (f"No timeline for '{project}' yet. Build one with "
                           f"create_timeline when Jack gives you the scope.")

    def update_milestone(project: str, which: str, done: bool = None,
                         new_target: str = "", remove: bool = False,
                         shift_downstream: bool = False) -> str:
        return timelines.update(project, which, done=done,
                                new_target=_resolve_target(new_target),
                                remove=bool(remove),
                                shift_downstream=bool(shift_downstream))

    def add_milestone(project: str, text: str, target: str = "", after: str = "") -> str:
        return timelines.add(project, text, target=_resolve_target(target), after=after)

    registry.register(
        "create_timeline",
        "Create a milestone timeline for an ACTIVE project from its scope. "
        "Milestones in order, EACH with a target: use offsets like 'in 1 "
        "week', 'in 3 weeks' (resolved to real dates in code) spaced "
        "realistically across Jack's stated horizon, or a date as he said "
        "it. Optional after_index (0-based) marks which earlier milestone "
        "this one depends on. Cover the whole scope; pad for print failures "
        "and shipping — realistic, not a fantasy Gantt.",
        {"type": "object", "properties": {
            "project": {"type": "string"},
            "milestones": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"},
                "target": {"type": "string", "description":
                           "REQUIRED: 'in 2 weeks' style offset or a date"},
                "after_index": {"type": "integer"}},
                "required": ["text", "target"]}},
            "horizon": {"type": "string", "description":
                        "When Jack should have the whole thing, as he said it "
                        "('six weeks', a date) — used to space any missing dates"}},
         "required": ["project", "milestones", "horizon"]},
        create_timeline,
        kind="action",
    )
    registry.register(
        "read_timeline",
        "A project's timeline: every milestone, its state, and any slips with "
        "downstream impact (computed, not guessed).",
        {"type": "object", "properties": {"project": {"type": "string"}},
         "required": ["project"]},
        read_timeline,
    )
    registry.register(
        "update_milestone",
        "Change one milestone: done=true when Jack says it's finished, "
        "new_target to re-plan a date, remove=true to drop it. `which` is the "
        "milestone id or a text fragment. shift_downstream=true moves every "
        "dependent milestone by the same delta IN CODE — use it when Jack "
        "says to shift the rest accordingly; never claim downstream moved "
        "unless you set this or updated them yourself. Report dates from the "
        "tool result, not from memory.",
        {"type": "object", "properties": {
            "project": {"type": "string"}, "which": {"type": "string"},
            "done": {"type": "boolean"}, "new_target": {"type": "string"},
            "remove": {"type": "boolean"}, "shift_downstream": {"type": "boolean"}},
         "required": ["project", "which"]},
        update_milestone,
        kind="action",
    )
    registry.register(
        "add_milestone",
        "Add one milestone to an existing timeline (after = id/text of the "
        "milestone it depends on, optional).",
        {"type": "object", "properties": {
            "project": {"type": "string"}, "text": {"type": "string"},
            "target": {"type": "string"}, "after": {"type": "string"}},
         "required": ["project", "text"]},
        add_milestone,
        kind="action",
    )

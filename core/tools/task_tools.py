r"""
Task tools (jarvis plan J1.2, roadmap M3.2) — the model-facing surface over
the durable task ledger (core/tasks.py). CODE owns the checklist state
machine; these five tools are the ONLY way the model touches it.

The evidence-grounding floor in complete_task_step is the heart of the leg:
a step advances only on proof code can check this turn — a tool result or
Jack's own words — never on the model's bare say-so.
"""

import re


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().casefold()


def render_task(t) -> str:
    """The full rendered state of one Task — shared by the task_status tool
    and JobRunner's background-step brief (core/jobs.py, M3.3), so a job
    step sees exactly what Jack would see asking task_status himself."""
    lines = [f"Task '{t.slug}' ({t.status}):"]
    for i, s in enumerate(t.steps):
        lines.append(f"{i + 1}. [{s.state}] {s.text}")
        for ev in s.evidence:
            lines.append(f"   evidence: {ev}")
    if t.blocked_on:
        lines.append(f"blocked_on: {t.blocked_on}")
    return "\n".join(lines)


def _grounded(evidence: str, tool_log: list, user_input: str) -> bool:
    """GROUNDED = normalized (whitespace-collapsed, casefolded, >=8 chars)
    substring of THIS TURN's tool results or of Jack's message this turn."""
    norm = _normalize(evidence)
    if len(norm) < 8:
        return False
    if norm in _normalize(user_input):
        return True
    for t in (tool_log or []):
        if norm in _normalize(t.get("result", "")):
            return True
    return False


class TaskToolContext:
    """Mutable holder for the not-yet-built Engine: bootstrap registers tools
    BEFORE constructing Engine, so the closures below read `ctx.engine` at
    CALL time (set once bootstrap finishes), never at registration time —
    the same pattern as project_resolver / engine_research."""

    def __init__(self):
        self.engine = None


def register_task_tools(registry, ledger):
    ctx = TaskToolContext()

    def _turn_tool_log():
        return getattr(ctx.engine, "_turn_tool_log", None) or []

    def _turn_user_input():
        return getattr(ctx.engine, "_turn_user_input", "") or ""

    def create_task(title: str, steps: list) -> str:
        steps = [str(s).strip() for s in (steps or []) if str(s).strip()]
        if not (2 <= len(steps) <= 10):
            return (f"ERROR: a task needs 2-10 steps, got {len(steps)}. "
                    "Give the whole checklist in one call.")
        try:
            t = ledger.create(title, steps)
        except ValueError as e:
            return f"ERROR: {e}"
        numbered = "\n".join(f"{i + 1}. {s.text}" for i, s in enumerate(t.steps))
        return (f"Created task '{t.slug}' with {len(t.steps)} steps:\n"
                f"{numbered}\nPresent this plan to Jack in your reply.")

    def task_status(slug: str = "") -> str:
        slug = (slug or "").strip()
        if not slug:
            return ledger.summary()
        t = ledger.get(slug)
        if t is None:
            return f"ERROR: no such task '{slug}'. Use task_status with no slug to list open tasks."
        return render_task(t)

    def complete_task_step(slug: str, step: int, evidence: str) -> str:
        if not _grounded(evidence, _turn_tool_log(), _turn_user_input()):
            if ctx.engine is not None:
                ctx.engine._task_evidence_refused = (
                    getattr(ctx.engine, "_task_evidence_refused", 0) + 1)
            return ("ERROR: that evidence isn't grounded — run the tool that "
                    "proves it and quote its result verbatim, or quote Jack's "
                    "own words, then call complete_task_step again.")
        try:
            t = ledger.complete_step(slug, int(step) - 1, evidence)
        except ValueError as e:
            return f"ERROR: {e}"
        cur = t.current_step()
        if cur is None:
            return f"Step {step} of '{slug}' done. All steps complete — task '{slug}' is finished."
        return (f"Step {step} of '{slug}' done. Current step: "
                f"{cur + 1}. {t.steps[cur].text}")

    def block_task(slug: str, step: int, reason: str) -> str:
        try:
            t = ledger.block(slug, int(step) - 1, reason)
        except ValueError as e:
            return f"ERROR: {e}"
        return f"Task '{slug}' parked at step {step} — blocked_on: {t.blocked_on}"

    def unblock_task(slug: str, step: int) -> str:
        try:
            ledger.unblock(slug, int(step) - 1)
        except ValueError as e:
            return f"ERROR: {e}"
        return f"Task '{slug}' unblocked at step {step} — back in progress."

    registry.register(
        "create_task",
        "Start tracking a multi-step JOB Jack asks you to work through "
        "(possibly unattended) — a checklist with concrete steps, not a "
        "single promise (use track_commitment for that) and not a project "
        "folder (use the project tools for that). Give the WHOLE checklist "
        "now (2-10 short steps) — present the plan back to Jack in your "
        "reply.",
        {"type": "object", "properties": {
            "title": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"},
                      "description": "2-10 short step descriptions, in order"}},
         "required": ["title", "steps"]},
        create_task,
        kind="action",
    )
    registry.register(
        "task_status",
        "Check a tracked JOB's current state (steps, marks, evidence, any "
        "blocker) by its slug from create_task's receipt, or omit the slug "
        "to list every open task. For a job created with create_task — not "
        "a project (use the project tools) or a commitment (use "
        "list_commitments).",
        {"type": "object", "properties": {
            "slug": {"type": "string"}}},
        task_status,
    )
    registry.register(
        "complete_task_step",
        "Advance one step of a tracked task — ONLY after something checkable "
        "happened. `evidence` must be a verbatim quote from a tool result you "
        "ran THIS turn, or from Jack's own words this turn — never your own "
        "summary or assessment, and never paraphrased. A step that isn't "
        "grounded this way is refused.",
        {"type": "object", "properties": {
            "slug": {"type": "string", "description":
                     "The exact slug from create_task's receipt or "
                     "task_status — copy it verbatim, never invent one."},
            "step": {"type": "integer", "description": "1-based step number"},
            "evidence": {"type": "string", "description":
                        "Copy-paste a substring VERBATIM from a tool result "
                        "this turn or from Jack's message this turn — do "
                        "not reword or summarize it."}},
         "required": ["slug", "step", "evidence"]},
        complete_task_step,
        kind="action",
    )
    registry.register(
        "block_task",
        "Park a tracked task's step at a blocker (e.g. it needs Jack's "
        "confirm, or missing input) — record the reason so a later session "
        "can resume without having seen this conversation.",
        {"type": "object", "properties": {
            "slug": {"type": "string", "description":
                     "The exact slug from create_task's receipt or "
                     "task_status — copy it verbatim, never invent one."},
            "step": {"type": "integer"},
            "reason": {"type": "string"}},
         "required": ["slug", "step", "reason"]},
        block_task,
        kind="action",
    )
    registry.register(
        "unblock_task",
        "Resume a tracked task's step after Jack has cleared its blocker.",
        {"type": "object", "properties": {
            "slug": {"type": "string", "description":
                     "The exact slug from create_task's receipt or "
                     "task_status — copy it verbatim, never invent one."},
            "step": {"type": "integer"}},
         "required": ["slug", "step"]},
        unblock_task,
        kind="action",
    )
    return ctx

r"""
Durable task ledger — J1.1 of the jarvis plan (FRIDAY_jarvis_plan.md §3, §6).

A multi-step job FRIDAY works on (possibly unattended) is a FILE, not a
conversation state: brain\tasks\<slug>.md, YAML frontmatter for what code
needs, a step checklist Jack can read in Obsidian. This class is the ONLY
writer (the tracker pattern — commitments.md, timelines\). The method being
ported is Claude Code's: code owns orchestration state between model turns;
the model never carries a checklist in its head.

Hard rules this file enforces (they are the J1.2 floor, not style):

  * CODE owns the state machine. Task status is DERIVED from step states on
    every mutation — there is no way to set a task "done" while a step isn't.
  * `complete_step` REFUSES empty evidence. A step advances because something
    checkable happened (a tool result, a file that now exists, a passing
    test) — model self-assessment alone never moves the ledger. The evidence
    lines are what the while-you-were-away board (J1.5) quotes verbatim.
  * `block` records WHY (the confirm description) in `blocked_on` — a parked
    task must be resumable by a session that never saw the conversation.
  * Restart-survival is by construction: every read re-parses the files, so
    a hard kill loses at most the mutation that didn't return.

Deferred by design (see the plan's §6 J1 entry): engine injection of
summary() into the referent block (model-visible — ships behind a before/
after compare), model-facing tools, and the brain.py write guard for tasks\
that MUST land before any such tool registers.
"""

import re
import threading
from datetime import datetime

import yaml

from core.project_meta import slug as _slugify

# Step state <-> checklist mark. Parsing accepts exactly these four.
_MARK = {"pending": " ", "in-progress": ">", "done": "x", "blocked": "!"}
_STATE = {v: k for k, v in _MARK.items()}
_STEP_LINE = re.compile(r"^- \[(.)\] \d+\. (.*?)(?:\s*\|\s*updated:(\S+))?$")
_EVIDENCE_LINE = re.compile(r"^  - evidence: (.*)$")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Step:
    def __init__(self, text, state="pending", evidence=None, updated=""):
        self.text = text
        self.state = state
        self.evidence = evidence or []   # verbatim lines, append-only
        self.updated = updated


class Task:
    def __init__(self, slug, title, steps, status="pending",
                 created="", updated="", blocked_on=""):
        self.slug = slug
        self.title = title
        self.steps = steps
        self.status = status
        self.created = created or _now()
        self.updated = updated or self.created
        self.blocked_on = blocked_on

    def current_step(self):
        """Index of the first step still needing work; None when finished."""
        for i, s in enumerate(self.steps):
            if s.state != "done":
                return i
        return None

    def derive_status(self):
        """The J1.2 floor: status follows the steps, never a claim."""
        if self.status == "cancelled":   # cancellation is the one code-set state
            return "cancelled"
        states = [s.state for s in self.steps]
        if all(s == "done" for s in states):
            return "done"
        if any(s == "blocked" for s in states):
            return "blocked"
        if any(s != "pending" for s in states):
            return "in-progress"
        return "pending"


class TaskLedger:
    DIR = "tasks"

    def __init__(self, brain):
        self.brain = brain
        self._lock = threading.Lock()  # future job runner + chat can overlap

    # ---------- creation ----------

    def create(self, title, steps):
        """New task file, all steps pending. An OPEN task with the same slug
        refuses (finish or cancel it first); a closed one gets a suffix so
        recurring jobs don't overwrite their own history."""
        if not steps:
            raise ValueError("a task needs at least one step")
        with self._lock:
            base = _slugify(title)
            slug = base
            n = 1
            while True:
                existing = self._read(slug)
                if existing is None:
                    break
                if existing.status not in ("done", "cancelled"):
                    raise ValueError(
                        f"task {slug!r} is already {existing.status} — "
                        "finish or cancel it before starting it again")
                n += 1
                slug = f"{base}_{n}"
            t = Task(slug, title.strip(), [Step(s.strip()) for s in steps])
            self._save(t, f"Open task: {t.title[:60]}")
            return t

    # ---------- reads ----------

    def get(self, slug):
        with self._lock:
            return self._read(slug)

    def list_open(self):
        """Active tasks (pending / in-progress / blocked), slug order."""
        with self._lock:
            out = []
            for rel in self.brain.list_notes():
                if not rel.startswith(self.DIR + "/"):
                    continue
                t = self._read(rel[len(self.DIR) + 1:-3])
                if t is not None and t.status not in ("done", "cancelled"):
                    out.append(t)
            return sorted(out, key=lambda t: t.slug)

    def list_all(self):
        """Every task regardless of status, slug order — list_open()
        deliberately excludes done/cancelled tasks, but the while-you-were-
        away board (J1.5, roadmap M3.4) needs exactly the done ones."""
        with self._lock:
            out = []
            for rel in self.brain.list_notes():
                if not rel.startswith(self.DIR + "/"):
                    continue
                t = self._read(rel[len(self.DIR) + 1:-3])
                if t is not None:
                    out.append(t)
            return sorted(out, key=lambda t: t.slug)

    def summary(self) -> str:
        """Compact active-task lines — built for the future referent-block
        injection (that wiring is a separate, model-visible increment)."""
        lines = []
        for t in self.list_open():
            cur = t.current_step()
            if t.status == "blocked":
                lines.append(f"- [{t.slug}] BLOCKED: {t.blocked_on}")
            elif cur is not None:
                lines.append(f"- [{t.slug}] step {cur + 1}/{len(t.steps)}: "
                             f"{t.steps[cur].text}")
        return "\n".join(lines) if lines else "(no active tasks)"

    # ---------- step mutations (each one git-commits via the brain) ----------

    def start_step(self, slug, index):
        return self._mutate(slug, index, "in-progress", None,
                            "Start step {i} of task {slug}")

    def complete_step(self, slug, index, evidence: str):
        """Advance ONLY on evidence — the non-negotiable (see module doc)."""
        if not str(evidence).strip():
            raise ValueError(
                f"step {index + 1} of {slug!r}: completion requires evidence "
                "(what checkably happened) — a bare claim never advances a step")
        return self._mutate(slug, index, "done", str(evidence).strip(),
                            "Complete step {i} of task {slug}")

    def block(self, slug, index, reason: str):
        """Park the task (typically at an outbound/destructive confirm)."""
        return self._mutate(slug, index, "blocked", None,
                            "Block task {slug} at step {i}",
                            blocked_on=str(reason).strip())

    def unblock(self, slug, index):
        """Jack resolved whatever parked it — the step goes back to work."""
        return self._mutate(slug, index, "in-progress", None,
                            "Unblock task {slug} at step {i}", blocked_on="")

    def cancel(self, slug, reason: str = ""):
        with self._lock:
            t = self._require(slug)
            t.status = "cancelled"
            t.blocked_on = ""
            self._save(t, f"Cancel task: {t.title[:60]}"
                          + (f" ({reason[:40]})" if reason else ""),
                       derive=False)
            return t

    def _mutate(self, slug, index, state, evidence, message, blocked_on=None):
        with self._lock:
            t = self._require(slug)
            if not 0 <= index < len(t.steps):
                raise ValueError(f"task {slug!r} has no step {index + 1}")
            step = t.steps[index]
            step.state = state
            step.updated = _now()
            if evidence:
                step.evidence.append(evidence)
            if blocked_on is not None:
                t.blocked_on = blocked_on
            self._save(t, message.format(i=index + 1, slug=slug))
            return t

    # ---------- parsing / rendering (the whole persistence layer) ----------

    def _require(self, slug):
        t = self._read(slug)
        if t is None:
            raise ValueError(f"no such task: {slug!r}")
        return t

    def _read(self, slug):
        try:
            text = self.brain.read_note(f"{self.DIR}/{slug}.md")
        except FileNotFoundError:
            return None
        front, body = {}, text
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                try:
                    front = yaml.safe_load(text[4:end]) or {}
                except yaml.YAMLError:
                    front = {}   # Jack mangled the header — steps still parse
                body = text[end + 5:]
        steps = []
        for line in body.splitlines():
            m = _STEP_LINE.match(line)
            if m:
                steps.append(Step(m.group(2).strip(),
                                  state=_STATE.get(m.group(1), "pending"),
                                  updated=m.group(3) or ""))
                continue
            e = _EVIDENCE_LINE.match(line)
            if e and steps:
                steps[-1].evidence.append(e.group(1))
        return Task(slug, str(front.get("title", slug)), steps,
                    status=str(front.get("status", "pending")),
                    created=str(front.get("created", "")),
                    updated=str(front.get("updated", "")),
                    blocked_on=str(front.get("blocked_on", "") or ""))

    def _save(self, t, message, derive=True):
        if derive:
            t.status = t.derive_status()
        t.updated = _now()
        lines = []
        for i, s in enumerate(t.steps):
            line = f"- [{_MARK[s.state]}] {i + 1}. {s.text}"
            if s.updated:
                line += f" | updated:{s.updated}"
            lines.append(line)
            for ev in s.evidence:
                lines.append(f"  - evidence: {ev}")
        # yaml.safe_dump, not f-strings: a title or confirm reason carrying
        # quotes/colons must not corrupt the header (the parser's fallback
        # would silently drop blocked_on — the one field a resume depends on).
        front = yaml.safe_dump(
            {"title": t.title, "status": t.status, "created": t.created,
             "updated": t.updated, "blocked_on": t.blocked_on},
            sort_keys=False, allow_unicode=True)
        text = (
            "---\n" + front + "---\n\n"
            f"# {t.title}\n\n"
            "*Tracked by FRIDAY's task ledger (jarvis plan J1.1). The\n"
            "checklist below is the ground truth — evidence lines are\n"
            "verbatim records of what actually happened.*\n\n"
            "## Steps\n\n" + "\n".join(lines) + "\n")
        self.brain.system_write(f"{self.DIR}/{t.slug}.md", text, summary=message)

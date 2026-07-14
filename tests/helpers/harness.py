r"""
SandboxFriday — a complete FRIDAY instance in a throwaway temp directory.

Every test runs against this, NEVER the real brain (CLAUDE.md rule). The
sandbox gets: its own brain (a real git repo, seeded with fixture projects at
known statuses), its own config/outbox/data/logs, the REAL persona and
character brief (we are testing the shipped prompts), and a recorder that
captures every tool call, confirm request, memory write, and reply — the
"action boundary" that Pillar 1 asserts on.
"""

import os
import re
import shutil
import threading
import time
from pathlib import Path

import yaml

FRIDAY_ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(FRIDAY_ROOT))

from core.model import ModelError  # noqa: E402
from core.service import FridayService  # noqa: E402

# Fixture projects: every status class, plus one with a known fact for
# retrieval tests. Throwaway names only — never Jack's real projects.
SEED_PROJECTS = {
    "alpha_rig": ("active", "Bench test rig for actuator characterization.",
                  "- **Load cell:** 20 kg rated"),
    "beta_probe": ("reference", "Retired depth probe; knowledge source.",
                   "- **Pressure rating:** 30 bar housing"),
    "gamma_arm": ("side-interest", "Occasional-tinkering robot arm.", ""),
    "delta_sled": ("", "Camera sled project (untagged status).", ""),  # = active
}


def n_runs() -> int:
    return int(os.environ.get("FRIDAY_TEST_RUNS", "5"))


class Recorder:
    """Everything FRIDAY did, captured at the action boundary."""

    def __init__(self):
        self.tools = []        # (name, args)
        self.confirms = []     # descriptions the gate asked about
        self.memory_writes = []
        self.pings = []
        self.errors = []
        self.replies = []      # final reply text per exchange (the STREAM)
        self.records = []      # reply.content per exchange (the RECORD, from
                               # on_done) — differs from the stream when the
                               # engine REPLACES content post-generation (the
                               # phantom-review barrier does exactly this).

    def tool_names(self):
        return [n for n, _ in self.tools]

    def reset(self):
        self.__init__()


class SandboxFriday:
    def __init__(self, tmp: Path, confirm_reply=True):
        self.root = Path(tmp)
        self.rec = Recorder()
        self.confirm_reply = confirm_reply  # bool or callable(desc)->bool
        self._build_tree()
        self.config = self._make_config()
        self.config_path = self.root / "friday_config.yaml"
        self.config_path.write_text(yaml.safe_dump(self.config), encoding="utf-8")
        # After the dump, so the file itself stays free of runtime keys:
        # change_own_config edits the file at _source_path (Tier B tools).
        self.config["_source_path"] = str(self.config_path)
        self._tokens = []
        self._boot_service()

    def _boot_service(self):
        self.service = FridayService(config=self.config)
        self._wrap_model_retry()
        self._done = threading.Event()
        self.service.attach(
            on_token=lambda t: self._tokens.append(t),
            on_tool=lambda n, a: self.rec.tools.append((n, a)),
            on_done=lambda i: (self.rec.records.append(
                (i or {}).get("content", "")), self._done.set()),
            on_error=lambda m: (self.rec.errors.append(m), self._done.set()),
            on_confirm=self._confirm,
            on_ping=lambda t: self.rec.pings.append(t),
            on_proactive=lambda: None,
            on_memory=lambda rel: self.rec.memory_writes.append(rel),
            on_activity=lambda t: None,
            on_labels=lambda: None,
        )

    def restart(self):
        """Simulate a fresh app launch over the same brain (recall tests)."""
        self._boot_service()

    def second_service(self):
        """A SECOND service over the same brain while the first is still alive
        and unflushed — anything the new instance can see was durable ON DISK
        the moment the write call returned (the write-through guarantee).
        Detached on purpose: no callbacks, not stored on the sandbox."""
        return FridayService(config=self.config)

    def fresh_conversation(self):
        """Wipe the in-memory conversation (history + taint) WITHOUT rebooting
        — brain/state on disk are untouched. Lets an N-run property test do N
        INDEPENDENT single-turn trials instead of one degrading dialogue (a
        reused conversation stops re-reading files, so later runs wouldn't
        exercise the same read-then-act path)."""
        self.service.engine.history = []
        self.service.engine._taint = ""
        self.service.engine.referents = []  # Task 6 working memory is
        self.rec.reset()                    # per-conversation too

    # ---------- construction ----------

    def _build_tree(self):
        brain = self.root / "brain"
        for sub in ("preferences", "projects", "people", "episodic", "inbox",
                    "character", "playbooks"):
            (brain / sub).mkdir(parents=True, exist_ok=True)
        # Real character brief + a small about-note so she has an owner context.
        shutil.copy(FRIDAY_ROOT / "brain" / "character" / "friday.md",
                    brain / "character" / "friday.md")
        (brain / "preferences" / "about_jack.md").write_text(
            "# About Jack\n\n- Mechanical engineering student.\n"
            "- Prefers metric fasteners.\n", encoding="utf-8")
        (brain / "index.md").write_text("# Brain Index\n", encoding="utf-8")
        for slug, (status, desc, extra) in SEED_PROJECTS.items():
            status_line = f"- **Status:** {status}\n" if status else ""
            (brain / "projects" / f"{slug}.md").write_text(
                f"# {slug.replace('_', ' ').title()}\n\n{status_line}\n"
                f"{desc}\n\n{extra}\n", encoding="utf-8")
        for d in ("friday_documents", "data", "logs", "Projects"):
            (self.root / d).mkdir(exist_ok=True)

    def _make_config(self) -> dict:
        # Real model settings; everything else points into the sandbox.
        real = yaml.safe_load((FRIDAY_ROOT / "config" / "friday_config.yaml")
                              .read_text(encoding="utf-8"))
        model = dict(real["model"])
        # FRIDAY_MODEL overrides the served tag for a single run WITHOUT editing
        # the repo config — this is how eval_compare.py points the whole suite at
        # the fine-tuned tag (friday-tuned-v1) vs the base for a clean A/B. Unset
        # in normal runs, so behaviour is identical to before.
        override = os.environ.get("FRIDAY_MODEL")
        if override:
            model["name"] = override
        return {
            "model": model,
            "paths": {"brain": str(self.root / "brain"),
                      "outbox": str(self.root / "friday_documents"),
                      "logs": str(self.root / "logs"),
                      "data": str(self.root / "data")},
            "persona_file": str(FRIDAY_ROOT / "config" / "persona.md"),
            "preferences_file": str(FRIDAY_ROOT / "config" / "preferences.json"),
            "character_note": "character/friday.md",
            "ui": {"hotkey": "ctrl+alt+f", "window_title": "FRIDAY-TEST"},
            "reasoning": real.get("reasoning", {"scaffold": "standard"}),
            "deep_mode": {"enabled": False, "model": "qwen2.5:32b"},
            "senses": {"gmail_accounts": [], "calendar_account": "personal",
                       "event_color_id": "6", "poll_minutes": 999,
                       "ping_event_minutes": 15, "web_max_bytes": 200000},
            "accountability": {"staleness_days": 14, "briefing_hour": 24,
                               "poll_seconds": 3600},
            "projects": {"default_root": str(self.root / "Projects")},
            "permissions": {"large_file_mb": 50, "writable_project_roots": []},
            # layered = notes + typed observations (Phase 3), matching prod. A
            # fresh sandbox has zero observations, so cold single-turn tests are
            # unchanged; multi-turn tests accrue and recall them (the point).
            "memory": {"retriever": "layered", "top_k": 4, "git_autocommit": True},
            "tools": {"read_file_max_bytes": 100000, "max_tool_rounds": 6},
        }

    def _wrap_model_retry(self):
        """One retry on ModelError only — a transient Ollama hiccup must not
        torch a whole overnight run. Correctness failures are never retried."""
        orig = self.service.engine.model.chat

        def chat(*a, **kw):
            try:
                return orig(*a, **kw)
            except ModelError:
                time.sleep(5)
                return orig(*a, **kw)
        self.service.engine.model.chat = chat

    def _confirm(self, cid, desc):
        self.rec.confirms.append(desc)
        reply = (self.confirm_reply(desc) if callable(self.confirm_reply)
                 else bool(self.confirm_reply))
        self.service.resolve_confirm(cid, reply)

    # ---------- talking to her ----------

    def ask(self, text: str, timeout: int = 420) -> str:
        """One exchange, waiting out the memory pass so all writes landed."""
        self._tokens = []
        self._done.clear()
        self.service.send_message(text)
        assert self._done.wait(timeout), f"model timeout on: {text[:80]}"
        deadline = time.time() + timeout
        while not self.service._busy.acquire(blocking=False):
            assert time.time() < deadline, "memory pass never finished"
            time.sleep(0.4)
        self.service._busy.release()
        reply = "".join(self._tokens).strip()
        self.rec.replies.append(reply)
        return reply

    def greeting(self, timeout: int = 300) -> str:
        self._tokens = []
        self._done.clear()
        self.service.open_session()
        assert self._done.wait(timeout), "greeting timeout"
        reply = "".join(self._tokens).strip()
        self.rec.replies.append(reply)
        return reply

    # ---------- convenience ----------

    @property
    def brain(self):
        return self.service.engine.brain

    def note(self, rel: str) -> str:
        return (self.brain.root / rel).read_text(encoding="utf-8")

    def git_log(self) -> str:
        import subprocess
        return subprocess.run(
            ["git", "-C", str(self.brain.root), "log", "--oneline", "-20"],
            capture_output=True, text=True).stdout


def repeat_behavior(fn, n=None, sandbox=None, detail=None):
    """Requirement C: run a phrasing-sensitive property n times. Returns
    (all_passed, results) where results = [(ok, detail), ...] for the report.
    Callers attach the x/n count so flaky cases are visible.

    Pass `sandbox` so each run starts a FRESH conversation. The N runs must be
    INDEPENDENT: without a reset they share one growing dialogue, and the
    degraded context suppresses tool-calling in later runs — which silently
    turned real behavior into flaky failures (commitment inference dropped from
    5/5 to 1/5 purely from shared history). Each run should test the behavior
    from a clean slate, which is also how the feature is actually used.

    Pass the test's `detail` dict so the exact pass fraction lands in the
    report evidence — the per-skill scorecard (armor plan §4.2) scores a case
    as passes/N, so "flaky" is a measured number, not just a flag."""
    n = n or n_runs()
    results = []
    for i in range(n):
        if sandbox is not None:
            sandbox.fresh_conversation()
        ok, run_detail = fn(i)
        results.append((bool(ok), str(run_detail)[:400]))
    passed = sum(1 for ok, _ in results if ok)
    if detail is not None:
        detail["run_passes"] = passed
        detail["run_total"] = n
    return all(ok for ok, _ in results), results


class FakeGmail:
    """Stand-in Gmail sense for injection/importance tests — plants exactly
    the messages a test needs. Deliberately has NO send method, matching the
    real GmailSense contract."""

    def __init__(self, account="personal", messages=None):
        self.account = account
        self.address = f"{account}@test.local"
        self.messages = messages or []   # dicts: id, from, subject, snippet, body
        self.drafts = []                 # records create_draft calls

    def connected(self):
        return True

    def unread(self, max_results=10):
        return [{"account": self.account, "id": m["id"], "from": m["from"],
                 "subject": m["subject"], "date": "", "snippet": m["snippet"]}
                for m in self.messages[:max_results]]

    def read_message(self, msg_id):
        for m in self.messages:
            if m["id"] == msg_id:
                return m.get("body", m["snippet"])
        return "(no such message)"

    def create_draft(self, to, subject, body):
        self.drafts.append({"to": to, "subject": subject, "body": body})
        return f"Draft created in {self.account} Gmail (id fake-{len(self.drafts)})."


def plant_email(sandbox, messages):
    """Swap the sandbox's gmail senses for a fake carrying planted messages."""
    fake = FakeGmail(messages=messages)
    sandbox.service.senses.gmail = [fake]
    sandbox.service.senses.poll()
    return fake


class _FakeCalendarAPI:
    """Stub of the Google Calendar API client — feeds raw API-shaped items
    (RFC3339 "dateTime" / date-only "date" starts) into the REAL
    CalendarSense.events() pipeline. Only the network layer is faked: parse,
    timezone conversion, and formatting are the production code under test.
    (The tz bug lived exactly there, and no test exercised it — the calendar
    tests only ever covered the outbound gate.)"""

    def __init__(self, items):
        self._items = items

    def events(self):
        return self

    def list(self, **kw):
        return self

    def execute(self):
        return {"items": self._items}

    def insert(self, **kw):
        raise AssertionError("event creation attempted through the fake API — "
                             "create tests use the real gate path (AUT-002)")


def plant_events(sandbox, items):
    """Swap the sandbox's calendar sense for one backed by planted raw API
    items (same pattern as plant_email). Items use the wire shape, e.g.
    {"id": "e1", "summary": "Meeting",
     "start": {"dateTime": "2026-07-08T14:00:00-07:00"}}   # or {"date": ...}
    """
    from core.senses.calendar_sense import CalendarSense
    senses = sandbox.service.senses
    cal = CalendarSense("personal", sandbox.root / "data" / "secrets", senses.log)
    cal._svc = _FakeCalendarAPI(items)   # bypass OAuth, keep the pipeline
    senses.calendar = cal
    senses.poll()
    return cal


NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?")


def numbers_in(text: str) -> set:
    """All numeric literals in a text — for fabrication checks."""
    return {m.group().replace(",", "") for m in NUMBER.finditer(text)}

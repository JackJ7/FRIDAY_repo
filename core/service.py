r"""
FridayService — the persistent service every frontend talks to.

The app window, the CLI, and (later) voice are all just faces; this object is
FRIDAY. It owns the engine, runs replies on worker threads, brokers the
permission gate's confirmations to whichever frontend is attached, and reports
live status. Stage 2's proactive background loop will live here too.

Frontend contract (a frontend registers plain callables):
    on_token(text)              streamed reply text
    on_tool(name, args)         a tool is about to run
    on_done(reply_info)         reply finished (dict: content, tok/s, ...)
    on_error(message)           something went wrong
    on_confirm(id, description) ask Jack; frontend later calls
                                resolve_confirm(id, approved)
"""

import os
import re
import threading
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

from core.accountability import Accountability
from core.bootstrap import ROOT, build_engine, data_dir, load_config
from core.model import ModelError
from core.project_meta import project_status
from core.version import __version__

# What each tool means for the live activity line in the status console.
_TOOL_ACTIVITY = {
    "read_file": "reading", "read_brain": "reading", "list_dir": "reading",
    "search_brain": "searching brain",
    "write_brain": "drafting", "write_to_friday_documents": "drafting",
    "create_project": "working on files", "add_files_to_project": "working on files",
    "track_commitment": "updating commitments",
    "close_commitment": "updating commitments",
    "list_commitments": "checking commitments",
    "read_playbook": "consulting playbook",
    "list_playbooks": "consulting playbook",
    "write_playbook": "saving to memory",
    "deep_think": "deep reasoning",
    "create_timeline": "planning timeline",
    "update_milestone": "updating timeline",
    "add_milestone": "updating timeline",
    "read_timeline": "checking timeline",
}


def _activity_for(tool: str, args: dict) -> str:
    label = _TOOL_ACTIVITY.get(tool, "working")
    if label == "reading":
        target = args.get("path", "")
        name = Path(target).name if target else ""
        return f"reading {name}" if name else "reading"
    return label


class FridayService:
    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self._frontend = {}            # name -> callback
        self._pending = {}             # confirm id -> {"event": Event, "approved": bool}
        self._busy = threading.Lock()  # one reply at a time
        # The gate's confirm callback routes to whatever frontend is attached.
        self.engine = build_engine(confirm=self._ask_jack, config=self.config)
        self._data_dir = data_dir(self.config)

        # Accountability (spec §4): panel data, DND, ping/briefing pacing.
        self.acc = Accountability(self.engine.brain, self.engine.tracker,
                                  self.config, self._data_dir,
                                  timelines=self.engine.timelines)
        # System-prompt state = accountability + whatever the senses cached.
        self.senses = self.engine.senses
        self.engine.acc_summary = lambda: "\n\n".join(
            s for s in (self.acc.text_summary(), self.senses.text_summary()) if s)
        # Every durable brain write pings the frontend's memory glyph.
        self.engine.brain.on_write = lambda rel: self._emit("on_memory", rel)
        # Autoresearch progress-to-UI (only when the capability is wired):
        # new-best / state-transition events surface as pings, mirroring the
        # on_write memory glyph above. No-op otherwise.
        if getattr(self.engine, "research", None) is not None:
            self.engine.research.on_event = lambda tag, text: self._emit(
                "on_ping", f"[research:{tag}] {text}")
        self._stop = threading.Event()
        self._activity = "idle"
        self._last_poll = 0.0
        threading.Thread(target=self._background_loop, daemon=True).start()

    # ---------- live activity (drives the status console) ----------

    def _set_activity(self, text: str):
        # Deep mode gets named whenever the deep-reasoning model is engaged, so
        # Jack knows why replies are slower (engine.deep_active is set by deep mode).
        if getattr(self.engine, "deep_active", False) and text != "idle":
            text = f"deep mode · {text}"
        if text != self._activity:
            self._activity = text
            self._emit("on_activity", text)

    # ---------- frontend attachment ----------

    def attach(self, **callbacks):
        """Register frontend callbacks (see contract above)."""
        self._frontend.update(callbacks)

    def _emit(self, name, *args):
        cb = self._frontend.get(name)
        if cb:
            cb(*args)

    # ---------- confirmations (the gate blocks here until Jack answers) ----------

    def _ask_jack(self, description: str) -> bool:
        if "on_confirm" not in self._frontend:
            return False  # no frontend attached — fail safe: decline
        cid = uuid.uuid4().hex[:8]
        pending = {"event": threading.Event(), "approved": False}
        self._pending[cid] = pending
        self._emit("on_confirm", cid, description)
        pending["event"].wait()  # engine worker parks here until Jack clicks
        self._pending.pop(cid, None)
        return pending["approved"]

    def resolve_confirm(self, cid: str, approved: bool):
        pending = self._pending.get(cid)
        if pending:
            pending["approved"] = bool(approved)
            pending["event"].set()

    # ---------- talking to FRIDAY ----------

    def send_message(self, text: str):
        """Handle one user message on a worker thread (non-blocking)."""
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def _run(self, text: str):
        if not self._busy.acquire(blocking=False):
            self._emit("on_error", "FRIDAY is mid-reply — give her a second.")
            return
        try:
            self._set_activity("thinking")

            def on_token(t):
                # First token after a tool ran means she's back to generating.
                if not self._activity.endswith("thinking"):
                    self._set_activity("thinking")
                self._emit("on_token", t)

            def on_tool(name, args):
                self._set_activity(_activity_for(name, args))
                self._emit("on_tool", name, args)

            reply = self.engine.respond(text, on_token=on_token, on_tool=on_tool)
            self._emit("on_done", {
                "content": reply.content,
                "tokens_per_second": round(reply.tokens_per_second, 1),
            })
            # Memory pass: commit anything durable from this exchange (item 2).
            # Runs after the reply is on screen; too-short messages skip it.
            if reply and len(text.strip()) >= 12:
                self._set_activity("saving to memory")
                try:
                    self.engine.memory_pass(text, reply.content,
                                            prior_tools=getattr(reply, "tool_log", []))
                except Exception:
                    pass  # memory must never break the conversation
        except ModelError as e:
            self._emit("on_error", str(e))
        except Exception as e:
            self._emit("on_error", f"Engine error ({type(e).__name__}): {e}")
        finally:
            self._set_activity("idle")
            self._busy.release()

    def open_session(self):
        """Generate the initiative-forward greeting on a worker thread."""
        def run():
            if not self._busy.acquire(blocking=False):
                return
            try:
                self._set_activity("thinking")
                reply = self.engine.session_greeting(
                    on_token=lambda t: self._emit("on_token", t))
                self._emit("on_done", {
                    "content": reply.content,
                    "tokens_per_second": round(reply.tokens_per_second, 1),
                })
            except ModelError as e:
                self._emit("on_error", str(e))
            except Exception as e:
                self._emit("on_error", f"Engine error ({type(e).__name__}): {e}")
            finally:
                self._set_activity("idle")
                self._busy.release()
        threading.Thread(target=run, daemon=True).start()

    def close_session(self):
        """Called when Jack ends the session (GUI Quit / CLI /quit): persists the
        running compaction digest as one session-summary observation for the next
        session's start-index (Notes-10 Phase 4 §4). Deterministic, best-effort,
        idempotent — see Engine.close_session. Never raises at shutdown."""
        try:
            return self.engine.close_session()
        except Exception:
            return None

    # ---------- accountability: panel, DND, background pacing ----------

    def get_needs_you(self) -> dict:
        data = self.acc.needs_you()
        cache = self.senses.cached()   # from the poll cache — never blocks on network
        data["events"] = cache["events"][:8]
        # Deliberately NO mail here: email is surfaced conversationally only
        # (briefing + on demand), never as an always-on display. The cache
        # still feeds her context so she can judge importance.
        return data

    def set_dnd(self, value: bool) -> bool:
        return self.acc.set_dnd(value)

    # Panel clicks — Jack's click IS the explicit confirmation (§6), so these
    # mutate directly (git-committed by the tracker either way).
    def confirm_commitment(self, cid):
        self.engine.tracker.confirm(cid)

    def decline_commitment(self, cid):
        self.engine.tracker.decline(cid)

    def close_commitment(self, cid):
        self.engine.tracker.close(cid)

    def _background_loop(self):
        """The quiet heartbeat: due-date pings and the once-a-day briefing.
        Everything else waits for the panel — that's the §4 pacing contract."""
        poll = self.config.get("accountability", {}).get("poll_seconds", 60)
        senses_cfg = self.config.get("senses", {})
        poll_minutes = senses_cfg.get("poll_minutes", 5)
        ping_window = senses_cfg.get("ping_event_minutes", 15)
        import time as _time
        while not self._stop.wait(poll):
            try:
                # Senses: refresh the mail/calendar cache every poll_minutes.
                # Network problems just leave the previous cache in place.
                if _time.time() - self._last_poll >= poll_minutes * 60:
                    self._last_poll = _time.time()
                    self.senses.poll()
                    # Time-sensitive ping: an event about to start (once each).
                    soon = (self.senses.calendar.starting_soon(ping_window)
                            if self.senses.calendar.connected() else [])
                    fresh = set(self.acc.unpinged("event", [e["id"] for e in soon]))
                    hits = [e for e in soon if e["id"] in fresh]
                    if hits and not self.acc.dnd:
                        self._emit("on_ping", "Starting soon: " + "; ".join(
                            f"{e['summary']} in {e['minutes']} min" for e in hits[:3]))

                # Real-time pings: genuinely time-sensitive only (due/overdue),
                # each at most once a day, silenced by DND (panel still shows them).
                due = self.acc.due_pings()
                if due and not self.acc.dnd:
                    lines = "; ".join(
                        c.text + (" (OVERDUE)" if c.overdue() else " — due today")
                        for c in due[:3])
                    self._emit("on_ping", f"Commitments need you: {lines}")

                # Daily briefing: once, after the configured hour, only when
                # idle — AND not while an autoresearch run holds the GPU (the
                # briefing calls the model, which would contend for VRAM). Skip
                # it this tick; briefing_due() stays true so it fires next tick
                # once the run ends. (Senses polling / due-date pings above touch
                # no model, so they're left untouched.)
                _research = getattr(self.engine, "research", None)
                research_busy = _research is not None and _research.active_tag
                if (self.acc.briefing_due() and not research_busy
                        and self._busy.acquire(blocking=False)):
                    try:
                        self.acc.mark_briefed()  # even if it fails, don't spam retries
                        self._set_activity("thinking")
                        self._emit("on_proactive")
                        reply = self.engine.briefing(
                            on_token=lambda t: self._emit("on_token", t))
                        self._emit("on_done", {
                            "content": reply.content,
                            "tokens_per_second": round(reply.tokens_per_second, 1),
                        })
                        if not self.acc.dnd:
                            self._emit("on_ping", "Daily briefing is ready.")
                    finally:
                        self._set_activity("idle")
                        self._busy.release()
            except Exception:
                pass  # the heartbeat must never die; next tick tries again

    # ---------- workspace views (read-only APIs for the tabs) ----------

    def _note_text(self, rel: str) -> str:
        try:
            return self.engine.brain.read_note(rel)
        except FileNotFoundError:
            return ""

    def list_projects(self) -> list:
        """Cards for the Projects tab, built from brain\\projects\\*.md."""
        out = []
        for rel in self.engine.brain.list_notes():
            if not rel.startswith("projects/"):
                continue
            text = self._note_text(rel)
            lines = [l.strip() for l in text.splitlines()]
            title = next((l[2:] for l in lines if l.startswith("# ")),
                         Path(rel).stem.replace("_", " ").title())
            desc = next((l for l in lines
                         if l and not l.startswith(("#", "-", "*"))), "")
            m = re.search(r"\*\*Folder:\*\*\s*(.+)", text)
            mtime = (self.engine.brain.root / rel).stat().st_mtime
            out.append({
                "note": rel, "title": title, "desc": desc[:140],
                "folder": m.group(1).strip() if m else "",
                "status": project_status(text),
                "edited": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
            })
        # Active projects first, then the rest alphabetically.
        return sorted(out, key=lambda p: (p["status"] != "active", p["title"].lower()))

    def get_project(self, rel: str) -> dict:
        """One project: its full note plus a live listing of its folder."""
        text = self._note_text(rel)
        m = re.search(r"\*\*Folder:\*\*\s*(.+)", text)
        folder, files = m.group(1).strip() if m else "", []
        if folder:
            p = self.engine.brain.gate.check_read(folder)
            if p.is_dir():
                for e in sorted(p.iterdir())[:200]:
                    files.append({"name": e.name + ("\\" if e.is_dir() else ""),
                                  "size": e.stat().st_size if e.is_file() else 0})
            else:
                folder = ""  # note points at a folder that's gone
        proj = Path(rel).stem
        milestones = [{"text": m.text, "target": m.target, "done": bool(m.done),
                       "late": m.days_late()}
                      for m in self.engine.timelines.milestones(proj)]
        return {"note": rel, "content": text, "folder": folder, "files": files,
                "timeline": milestones}

    def list_brain_notes(self) -> dict:
        """Notes grouped by top-level brain folder, for the Brain tab."""
        groups = {}
        for rel in self.engine.brain.list_notes():
            top = rel.split("/", 1)[0] if "/" in rel else "(root)"
            mtime = (self.engine.brain.root / rel).stat().st_mtime
            groups.setdefault(top, []).append({
                "path": rel,
                "edited": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
            })
        return groups

    def read_note(self, rel: str) -> str:
        return self._note_text(rel)

    def open_in_obsidian(self, rel: str):
        """Jack clicked 'Open in Obsidian' — hand the note to the vault app
        via the obsidian:// protocol (falls back to the default .md handler)."""
        p = (self.engine.brain.root / rel).resolve()
        self.engine.brain.gate.log.log("READ", f"open in Obsidian: {p}")
        try:
            os.startfile("obsidian://open?path=" + urllib.parse.quote(str(p)))
        except OSError:
            os.startfile(str(p))

    def open_folder(self, path: str):
        """Jack clicked 'Open folder' — Explorer, but only within her zones."""
        p = Path(path).resolve()
        gate = self.engine.brain.gate
        if p.is_dir() and gate._zone(p) is not None:
            gate.log.log("READ", f"open folder in Explorer: {p}")
            os.startfile(str(p))

    # ---------- chat history (History tab; read-only over interaction logs) ----------

    _INTERNAL_LABELS = ("(memory pass)",)
    _PROACTIVE_LABELS = ("(session start)", "(daily briefing)")

    def _log_files(self, max_files: int = 20):
        logs = self.config.get("paths", {}).get("logs", "logs")
        d = (Path(logs) if Path(logs).is_absolute() else ROOT / logs) / "interactions"
        if not d.is_dir():
            return []
        return sorted(d.glob("*.jsonl"), reverse=True)[:max_files]

    # FRIDAY-generated titles/summaries, cached so each session pays the
    # (local) model cost exactly once. data\session_titles.json.
    _labels_lock = threading.Lock()

    def _labels_path(self):
        return self._data_dir / "session_titles.json"

    def _labels(self) -> dict:
        import json as _json
        try:
            return _json.loads(self._labels_path().read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            return {}

    def generate_session_labels(self, max_new: int = 5):
        """Label recent unlabeled sessions (title + summary) on a worker
        thread. Skips entirely if FRIDAY is mid-reply — chat always wins."""
        def run():
            import json as _json
            if not self._labels_lock.acquire(blocking=False):
                return  # already labeling
            try:
                if not self._busy.acquire(blocking=False):
                    return  # she's talking — try again next History open
                try:
                    self._set_activity("organizing history")
                    labels = self._labels()
                    todo = [s for s in self.list_sessions()
                            if s["id"] not in labels][:max_new]
                    for s in todo:
                        convo = self.read_session(s["id"])[:6]
                        transcript = "\n".join(
                            f"JACK: {e['user'][:200]}\nFRIDAY: {e['reply'][:200]}"
                            for e in convo)
                        try:
                            reply = self.engine.model.chat([{
                                "role": "user", "content":
                                    "Label this conversation. Reply with exactly "
                                    "two lines:\nTITLE: <5-8 words, the nature of "
                                    "the conversation>\nSUMMARY: <1-2 sentences, "
                                    "what it covered>\n\n" + transcript}])
                        except ModelError:
                            break  # model unreachable — retry another time
                        title, summary = "", ""
                        for line in reply.content.splitlines():
                            if line.upper().startswith("TITLE:"):
                                title = line[6:].strip().strip('"')
                            elif line.upper().startswith("SUMMARY:"):
                                summary = line[8:].strip()
                        if not title:  # model misformatted — take what we can
                            title = reply.content.strip().splitlines()[0][:60]
                        labels[s["id"]] = {"title": title[:70],
                                           "summary": summary[:300]}
                    with open(self._labels_path(), "w", encoding="utf-8") as f:
                        f.write(_json.dumps(labels, ensure_ascii=False, indent=1))
                        f.flush()
                        import os as _os
                        _os.fsync(f.fileno())
                    if todo:
                        self._emit("on_labels")
                finally:
                    self._set_activity("idle")
                    self._busy.release()
            finally:
                self._labels_lock.release()
        threading.Thread(target=run, daemon=True).start()

    def list_sessions(self) -> list:
        """Past sessions, newest first: id, date, a title snippet, and size."""
        import json as _json
        sessions = {}
        for f in self._log_files():
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    r = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                sid = r.get("session", "?")
                if sid == self.engine.session_id:
                    continue  # the live session belongs in Chat, not History
                if r.get("user") in self._INTERNAL_LABELS:
                    continue
                s = sessions.setdefault(sid, {"id": sid, "when": r.get("timestamp", ""),
                                              "title": "", "count": 0})
                s["count"] += 1
                if not s["title"]:
                    if r.get("user") not in self._PROACTIVE_LABELS:
                        s["title"] = r.get("user", "")[:80]
                    else:
                        s["title"] = (r.get("reply", "") or "")[:80]
        out = sorted(sessions.values(), key=lambda s: s["when"], reverse=True)
        labels = self._labels()
        for s in out:
            s["when"] = s["when"][:16].replace("T", " ")
            lab = labels.get(s["id"])
            if lab:  # FRIDAY-generated; otherwise the snippet stays as fallback
                s["title"] = lab["title"]
                s["summary"] = lab.get("summary", "")
        return out[:100]

    def read_session(self, sid: str) -> list:
        """One past conversation: [{user, reply, when}], memory passes hidden."""
        import json as _json
        out = []
        for f in self._log_files():
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    r = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                if r.get("session") != sid or r.get("user") in self._INTERNAL_LABELS:
                    continue
                out.append({"user": r.get("user", ""), "reply": r.get("reply", ""),
                            "when": r.get("timestamp", "")[11:16],
                            "proactive": r.get("user") in self._PROACTIVE_LABELS})
        return sorted(out, key=lambda e: e["when"])

    # ---------- uploads history (Uploads tab) ----------

    def record_upload(self, path: str):
        entry = {"path": path, "name": Path(path).name,
                 "when": datetime.now().strftime("%Y-%m-%d %H:%M")}
        state = self.acc._state()
        uploads = [u for u in state.get("uploads", []) if u["path"] != path]
        state["uploads"] = ([entry] + uploads)[:30]
        self.acc._save_state(state)

    def get_uploads(self) -> list:
        out = []
        for u in self.acc._state().get("uploads", []):
            u = dict(u)
            u["exists"] = Path(u["path"]).exists()
            out.append(u)
        return out

    # ---------- connections (settings/about panel) ----------

    def get_connections(self) -> dict:
        return {
            "gmail": [{"name": g.account, "email": g.address,
                       "connected": g.connected()} for g in self.senses.gmail],
            "calendar": {"account": self.senses.calendar.account,
                         "connected": self.senses.calendar.connected()},
        }

    def reconnect_account(self, name: str):
        """Jack clicked Reconnect — run the OAuth consent flow for that account
        in his browser (a separate process; the app never blocks on it)."""
        import subprocess
        import sys as _sys
        self.engine.brain.gate.log.log("SENSE", f"reconnect flow launched: {name}")
        subprocess.Popen([_sys.executable, str(ROOT / "scripts" / "connect_senses.py"),
                          name], cwd=str(ROOT))

    def disconnect_account(self, name: str):
        """Jack clicked Disconnect — delete that account's token."""
        tp = self._data_dir / "secrets" / f"token_{name}.json"
        if tp.exists():
            tp.unlink()
        for g in self.senses.gmail:
            if g.account == name:
                g._svc = None
        if self.senses.calendar.account == name:
            self.senses.calendar._svc = None
        self.engine.brain.gate.log.log("SENSE", f"disconnected account: {name}")

    # ---------- live status (drives the UI's system console) ----------

    def get_status(self) -> dict:
        """The live console rows, plus the fuller facts for the About screen
        (model, note count) which no longer live in the main UI."""
        notes = self.engine.brain.list_notes()
        status = {
            "activity": self._activity,
            "dnd": self.acc.dnd,
            "version": __version__,
            # About-screen facts:
            "model": self.config["model"]["name"],
            "brain_notes": len(notes),
            "projects": sum(1 for n in notes if n.startswith("projects/")),
        }
        status.update(self.senses.status())  # gmail / calendar connection rows
        return status

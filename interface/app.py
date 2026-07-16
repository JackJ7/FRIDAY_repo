r"""
FRIDAY's app shell — the PyWebView window plus Windows presence.

This file owns: the window (built from the approved UI design in ui\),
the system-tray icon (closing the window hides it; FRIDAY keeps running),
the global summon hotkey, toast notifications, and a single-instance lock
(launching a second copy just summons the first).

All actual assistant behavior lives in core.service.FridayService — this is
just her face. Run with:  python friday_app.py
"""

import json
import os
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pystray
import webview
from PIL import Image, ImageDraw, ImageFont

from core.service import FridayService
from interface.hotkey import GlobalHotkey, force_foreground

UI_INDEX = ROOT / "interface" / "ui" / "index.html"
# Localhost lock: one FRIDAY at a time. Env-overridable so the test suite can
# exercise the lock without colliding with a real running instance.
LOCK_PORT = int(os.environ.get("FRIDAY_LOCK_PORT", "47533"))


# ---------- single instance ----------

def acquire_instance_lock():
    """Bind a localhost port as a lock. Returns the socket, or None if another
    FRIDAY is already running (in which case we ask it to show itself)."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
        lock.listen(1)
        return lock
    except OSError:
        try:  # tell the running instance to come to the front
            with socket.create_connection(("127.0.0.1", LOCK_PORT), timeout=2) as s:
                s.sendall(b"SUMMON\n")
        except OSError:
            pass
        return None


# ---------- tray icon ----------

def make_icon_image() -> Image.Image:
    """The brand mark from the UI (amber rounded square, dark F), drawn in code
    so there's no asset file to lose."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, 62, 62], radius=16, fill=(245, 184, 92, 255))
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 40)
        d.text((32, 30), "F", font=font, fill=(11, 14, 20, 255), anchor="mm")
    except OSError:  # font missing — plain square still reads as FRIDAY amber
        d.rectangle([26, 16, 34, 48], fill=(11, 14, 20, 255))
    return img


class FridayApp:
    def __init__(self):
        self.service = FridayService()
        self.config = self.service.config
        self.window = None
        self.tray = None
        self.visible = True

    # ---------- JS -> Python (exposed as window.pywebview.api) ----------

    class Api:
        def __init__(self, app):
            self._app = app

        def send(self, text):
            self._app.service.send_message(text)

        def resolve_confirm(self, cid, approved):
            self._app.service.resolve_confirm(cid, bool(approved))

        def get_status(self):
            return self._app.service.get_status()

        def open_session(self):
            self._app.service.open_session()

        def pick_file(self):
            try:
                mode = webview.FileDialog.OPEN          # pywebview >= 5
            except AttributeError:
                mode = webview.OPEN_DIALOG              # older API
            paths = self._app.window.create_file_dialog(mode, allow_multiple=True)
            return list(paths or [])

        # ----- Stage 2: "Needs You" panel + DND -----

        def get_needs_you(self):
            return self._app.service.get_needs_you()

        def set_dnd(self, value):
            return self._app.service.set_dnd(bool(value))

        # ----- Controls panel (jarvis plan J0) -----

        def get_toggles(self):
            return self._app.service.get_toggles()

        def set_toggle(self, key, value):
            return self._app.service.set_toggle(key, value)

        def confirm_commitment(self, cid):
            self._app.service.confirm_commitment(cid)

        def decline_commitment(self, cid):
            self._app.service.decline_commitment(cid)

        def close_commitment(self, cid):
            self._app.service.close_commitment(cid)

        # ----- workspace tabs (read-only) -----

        def list_projects(self):
            return self._app.service.list_projects()

        def get_project(self, rel):
            return self._app.service.get_project(rel)

        def list_brain_notes(self):
            return self._app.service.list_brain_notes()

        def read_note(self, rel):
            return self._app.service.read_note(rel)

        def open_in_obsidian(self, rel):
            self._app.service.open_in_obsidian(rel)

        def open_folder(self, path):
            self._app.service.open_folder(path)

        def record_upload(self, path):
            self._app.service.record_upload(path)

        def get_uploads(self):
            return self._app.service.get_uploads()

        # ----- history tab + settings panel -----

        def list_sessions(self):
            self._app.service.generate_session_labels()  # label gaps, async
            return self._app.service.list_sessions()

        def read_session(self, sid):
            return self._app.service.read_session(sid)

        def get_connections(self):
            return self._app.service.get_connections()

        def reconnect_account(self, name):
            self._app.service.reconnect_account(name)

        def disconnect_account(self, name):
            self._app.service.disconnect_account(name)

    # ---------- Python -> JS ----------

    def _js(self, code):
        try:
            self.window.evaluate_js(code)
        except Exception:
            pass  # window mid-teardown — drop the update, never crash the engine

    def _attach_service(self):
        self.service.attach(
            on_token=lambda t: self._js(f"FRIDAY.onToken({json.dumps(t)})"),
            on_tool=lambda n, a: self._js(
                f"FRIDAY.onTool({json.dumps(n)}, {json.dumps(a, default=str)})"),
            on_done=self._on_done,
            on_error=lambda m: self._js(f"FRIDAY.onError({json.dumps(m)})"),
            on_confirm=lambda cid, d: self._js(
                f"FRIDAY.onConfirm({json.dumps(cid)}, {json.dumps(d)})"),
            # Stage 2: time-sensitive pings become toasts; proactive messages
            # (the daily briefing) open a FRIDAY bubble in the thread.
            on_ping=lambda text: self.notify("FRIDAY", text),
            on_proactive=lambda: self._js("FRIDAY.onProactive()"),
            on_activity=lambda text: self._js(f"FRIDAY.onActivity({json.dumps(text)})"),
            on_memory=lambda rel: self._js(f"FRIDAY.onMemory({json.dumps(rel)})"),
            on_labels=lambda: self._js("FRIDAY.onLabels()"),
        )

    def _on_done(self, info):
        self._js(f"FRIDAY.onDone({json.dumps(info)})")
        if not self.visible:  # she finished while hidden — quiet heads-up
            snippet = (info.get("content") or "").strip().replace("\n", " ")
            self.notify("FRIDAY", snippet[:120] or "Done.")

    # ---------- presence ----------

    def notify(self, title, message):
        """Native Windows toast; failures are never fatal."""
        try:
            from windows_toasts import Toast, WindowsToaster
            toast = Toast()
            toast.text_fields = [title, message]
            WindowsToaster("FRIDAY").show_toast(toast)
        except Exception:
            pass

    def summon(self):
        """Bring FRIDAY to the front (hotkey / tray / second launch)."""
        try:
            self.window.show()
            self.window.restore()
            # pywebview's show() maps the window but doesn't reliably take
            # focus from the foreground app — the native nudge does.
            force_foreground(self.config.get("ui", {}).get("window_title", "FRIDAY"))
            self.visible = True
        except Exception:
            pass

    def _hide_instead_of_close(self):
        """Window X hides to tray; FRIDAY stays running (quit via tray)."""
        self.window.hide()
        self.visible = False
        return False  # cancel the close

    def quit(self):
        # Close the memory loop: persist this session's compaction digest as a
        # session-summary observation before we tear down (Notes-10 Phase 4 §4).
        try:
            self.service.close_session()
        except Exception:
            pass
        if self.tray:
            self.tray.stop()
        try:
            self.window.destroy()
        except Exception:
            pass

    def _start_tray(self):
        def about():
            s = self.service.get_status()
            self.notify(f"FRIDAY v{s['version']}",
                        f"model {s['model']} · {s['brain_notes']} brain notes · all local")

        menu = pystray.Menu(
            pystray.MenuItem("Show FRIDAY", lambda: self.summon(), default=True),
            pystray.MenuItem("About FRIDAY", lambda: about()),
            pystray.MenuItem("Quit", lambda: self.quit()),
        )
        self.tray = pystray.Icon("FRIDAY", make_icon_image(), "FRIDAY — local assistant", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _start_summon_listener(self, lock):
        """Accept SUMMON pings from second launches (single-instance lock)."""
        def listen():
            while True:
                try:
                    conn, _ = lock.accept()
                    conn.close()
                    self.summon()
                except OSError:
                    return  # lock closed — shutting down
        threading.Thread(target=listen, daemon=True).start()

    # ---------- boot ----------

    def run(self, lock):
        ui_cfg = self.config.get("ui", {})
        self.window = webview.create_window(
            ui_cfg.get("window_title", "FRIDAY"),
            UI_INDEX.as_uri(),
            js_api=self.Api(self),
            width=ui_cfg.get("width", 1180),
            height=ui_cfg.get("height", 800),
            min_size=(900, 620),
            background_color="#0B0E14",
            text_select=True,
        )
        self.window.events.closing += self._hide_instead_of_close
        self._attach_service()

        def on_start():
            self._start_tray()
            self._start_summon_listener(lock)
            combo = ui_cfg.get("hotkey", "ctrl+alt+f")
            hk = GlobalHotkey(combo, self.summon)
            if hk.start():
                print(f"(global hotkey live: {combo})")
            else:
                # Tell Jack loudly — a silent hotkey was the Stage 1 bug.
                print(f"(hotkey problem: {hk.error})")
                self.notify("FRIDAY", f"Hotkey problem: {hk.error}")

        webview.start(on_start)  # blocks until the window is destroyed (Quit)


def main():
    lock = acquire_instance_lock()
    if lock is None:
        # Windowless launches have no console — a toast is the feedback.
        print("FRIDAY is already running — summoned her instead.")
        try:
            from windows_toasts import Toast, WindowsToaster
            toast = Toast()
            toast.text_fields = ["FRIDAY", "Already running — brought her to the front."]
            WindowsToaster("FRIDAY").show_toast(toast)
        except Exception:
            pass
        return
    app = FridayApp()
    app.run(lock)


if __name__ == "__main__":
    main()

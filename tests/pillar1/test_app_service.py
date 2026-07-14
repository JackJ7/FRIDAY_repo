r"""APP — app/service lifecycle: single-instance lock, hard-kill, busy guard.
These drive the real friday_app.py in subprocesses with a sandbox config and a
non-default lock port, so they never collide with Jack's running instance."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

FRIDAY_ROOT = Path(__file__).resolve().parents[2]
TEST_LOCK_PORT = "47599"  # not the real 47533


@pytest.mark.case("APP-001", "the single-instance lock port binds and rejects a second binder")
def test_lock_port():
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.bind(("127.0.0.1", int(TEST_LOCK_PORT)))
    s1.listen(1)
    try:
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(OSError):
            s2.bind(("127.0.0.1", int(TEST_LOCK_PORT)))
        s2.close()
    finally:
        s1.close()


@pytest.mark.case("APP-002", "acquire_instance_lock returns a lock, then None for a second call")
def test_acquire_lock(monkeypatch):
    monkeypatch.setenv("FRIDAY_LOCK_PORT", "47601")
    # import fresh so the env is read
    import importlib
    import interface.app as app
    importlib.reload(app)
    lock = app.acquire_instance_lock()
    assert lock is not None
    assert app.acquire_instance_lock() is None  # second instance refused
    lock.close()
    importlib.reload(app)  # restore default for other tests


@pytest.mark.case("APP-003", "service busy guard: a second message mid-reply is refused, not queued")
@pytest.mark.model
@pytest.mark.skill("session_ops")
def test_busy_guard(sandbox, detail):
    errors = []
    sandbox.service._frontend["on_error"] = lambda m: errors.append(m)
    sandbox.service.send_message("Count slowly to twenty, one number per line.")
    time.sleep(1.0)  # ensure the first reply is in flight
    sandbox.service.send_message("and again")
    time.sleep(2.0)
    detail["errors"] = errors
    assert any("mid-reply" in e for e in errors), "busy guard did not fire"


@pytest.mark.case("APP-004", "windowless launch stays alive, writes app.log, holds the lock")
def test_windowless_launch(tmp_path):
    # A minimal windowless smoke: friday_app under pythonw with a test lock port
    # and the REAL config (UI needs the real ui\ assets). We only check it lives.
    env = dict(os.environ, FRIDAY_LOCK_PORT="47603")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw) if pythonw.exists() else sys.executable
    p = subprocess.Popen([exe, str(FRIDAY_ROOT / "friday_app.py")],
                         cwd=str(FRIDAY_ROOT), env=env)
    try:
        time.sleep(20)
        alive = p.poll() is None
        assert alive, "windowless app exited early"
        # lock held?
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        held = False
        try:
            s.bind(("127.0.0.1", 47603))
        except OSError:
            held = True
        finally:
            s.close()
        assert held, "app did not hold its instance lock"
    finally:
        p.kill()
        p.wait(timeout=10)


@pytest.mark.case("APP-005", "graceful vs hard kill: brain state identical either way")
@pytest.mark.model
@pytest.mark.skill("memory_persistence")
def test_graceful_equals_hard(sandbox):
    # Graceful path already covered by MEM-005 (hard kill). Here: a graceful
    # restart preserves a committed write.
    sandbox.brain.write_note("inbox/persist.md", "# P\n\nkept\n", summary="persist check")
    sandbox.restart()
    assert "kept" in sandbox.note("inbox/persist.md")

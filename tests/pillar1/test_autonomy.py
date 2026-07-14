r"""AUT — the autonomy boundary (invariant #3), enforced in code."""

import re
from pathlib import Path

import pytest

from core.permissions import ConfirmationDeclined

FRIDAY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.case("AUT-001", "approve_outbound always asks; declined raises and logs")
def test_outbound_always_confirms(sandbox):
    sandbox.confirm_reply = False
    with pytest.raises(ConfirmationDeclined):
        sandbox.brain.gate.approve_outbound("send email to test")
    assert len(sandbox.rec.confirms) == 1
    log = (sandbox.root / "logs" / "actions.log").read_text(encoding="utf-8")
    assert "CONFIRM-NO" in log


@pytest.mark.case("AUT-002", "declined calendar create makes zero API calls")
def test_declined_event_no_api(sandbox):
    from core.senses.calendar_sense import CalendarSense

    class Tripwire:  # any attribute access = API touched
        def __getattr__(self, name):
            raise AssertionError("calendar API touched before/despite decline!")

    sandbox.confirm_reply = False
    cal = CalendarSense("personal", sandbox.root / "data" / "secrets",
                        sandbox.brain.gate.log)
    cal._svc = Tripwire()
    with pytest.raises(ConfirmationDeclined):
        cal.create_event(sandbox.brain.gate, "T", "2026-08-01T10:00:00-07:00",
                         "2026-08-01T11:00:00-07:00")


@pytest.mark.case("AUT-003", "no script-execution tool exists in the registry")
def test_no_script_tool(sandbox):
    names = [t["function"]["name"] for t in sandbox.service.engine.registry.to_ollama()]
    forbidden = [n for n in names if re.search(r"(run|exec|shell|script|command|spawn)", n)]
    assert not forbidden, f"execution-shaped tools present: {forbidden}"


@pytest.mark.case("AUT-004", "no gmail send exists: method scan + source scan of core\\")
def test_no_send_path():
    from core.senses.gmail_sense import GmailSense
    sendish = [a for a in dir(GmailSense) if "send" in a.lower()]
    assert not sendish, f"GmailSense has send-like members: {sendish}"
    for py in (FRIDAY_ROOT / "core").rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        assert ".send(" not in src and "messages().send" not in src, \
            f"send-shaped call in {py.name}"


@pytest.mark.case("AUT-005", "web lookup cannot run ambiently: no timers/threads in the module")
def test_web_not_ambient():
    src = (FRIDAY_ROOT / "core" / "senses" / "web_lookup.py").read_text(encoding="utf-8")
    assert "threading" not in src and "Timer" not in src and "sleep" not in src
    hub = (FRIDAY_ROOT / "core" / "senses" / "__init__.py").read_text(encoding="utf-8")
    assert "fetch_url" not in hub, "senses hub (polled!) references web fetch"


@pytest.mark.case("AUT-006", "web_fetch refuses non-http schemes")
def test_web_scheme_refused(sandbox):
    r = sandbox.service.engine.registry.call("web_fetch", {"url": "file:///C:/Windows/win.ini"})
    assert r.startswith("ERROR")
    r = sandbox.service.engine.registry.call("web_fetch", {"url": "ftp://x"})
    assert r.startswith("ERROR")


@pytest.mark.case("AUT-007", "approved outbound is logged as OUTBOUND in the audit trail")
def test_outbound_logged(sandbox):
    sandbox.confirm_reply = True
    sandbox.brain.gate.approve_outbound("create calendar event: test")
    log = (sandbox.root / "logs" / "actions.log").read_text(encoding="utf-8")
    assert "OUTBOUND" in log


@pytest.mark.case("AUT-008", "deep_think is always available so FRIDAY can self-engage deep mode")
def test_deep_think_available(sandbox, monkeypatch):
    # Contract change (Jack, 2026-07-08): deep mode is no longer gated behind a
    # config flag - FRIDAY engages it on her own judgment for hard problems, so
    # the tool is always registered. Availability of the heavier MODEL is a
    # runtime concern (deep_think returns an honest fallback if it isn't pulled),
    # not a registration-time gate. The sandbox config has enabled=false, and
    # the tool is present anyway - that's the point.
    assert sandbox.config["deep_mode"]["enabled"] is False
    names = [t["function"]["name"] for t in sandbox.service.engine.registry.to_ollama()]
    assert "deep_think" in names
    assert sandbox.service.engine.deep_active is False
    # Engaging it flips the status flag the console reads and, when the heavier
    # model isn't reachable, takes the honest-fallback path (never a bluff). We
    # FORCE the unreachable case so this is deterministic and fast regardless of
    # whether the deep model happens to be pulled on this machine - otherwise
    # the test would run a real (slow) deep inference and its assertion would flip.
    from core.model import ModelError, OllamaClient

    def unavailable(*a, **k):
        raise ModelError("deep model not pulled (forced for the test)")
    monkeypatch.setattr(OllamaClient, "chat", unavailable)
    result = sandbox.service.engine.registry.call("deep_think", {"question": "2+2?"})
    assert "NOT AVAILABLE" in result and "ollama pull" in result
    assert sandbox.service.engine.deep_active is False  # cleared in finally

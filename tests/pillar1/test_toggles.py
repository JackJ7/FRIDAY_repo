r"""TGL — the J0 toggle registry (FRIDAY_jarvis_plan.md §2).

Every user-facing switch the jarvis plan ships flows through ToggleRegistry:
declared in code, persisted in data\toggles.json, applied at runtime through
an owner callback. These are pure-code tests (no model, no brain) — the
registry must hold its contract before anything rides on it.
"""

import json

import pytest

from core.toggles import ToggleRegistry


def _registry(tmp_path, **kw):
    return ToggleRegistry(tmp_path / "toggles.json", **kw)


def _register_voice(reg, **kw):
    return reg.register(
        "voice.mode", "enum", "Voice",
        "How FRIDAY listens: off, push-to-talk, or wake word.",
        default="off", choices=("off", "ptt", "wake"), **kw)


@pytest.mark.case("TGL-001", "describe() returns registered toggles, in order, with values")
def test_describe_order_and_shape(tmp_path):
    reg = _registry(tmp_path)
    reg.register("dnd", "bool", "Do Not Disturb", "Silence pings.",
                 default=False, persist=False)
    _register_voice(reg)
    desc = reg.describe()
    assert [d["key"] for d in desc] == ["dnd", "voice.mode"]
    assert desc[0] == {"key": "dnd", "kind": "bool", "label": "Do Not Disturb",
                       "description": "Silence pings.", "value": False,
                       "choices": None}
    assert desc[1]["choices"] == ["off", "ptt", "wake"]
    assert desc[1]["value"] == "off"


@pytest.mark.case("TGL-002", "bool set coerces the usual string forms and refuses garbage")
def test_bool_coercion(tmp_path):
    reg = _registry(tmp_path)
    reg.register("x", "bool", "X", "", default=False)
    assert reg.set("x", "on") is True
    assert reg.set("x", "0") is False
    assert reg.set("x", True) is True
    with pytest.raises(ValueError):
        reg.set("x", "maybe")
    assert reg.get("x") is True  # the refused value changed nothing


@pytest.mark.case("TGL-003", "enum set enforces choices; unknown keys are refused loudly")
def test_enum_and_unknown_key(tmp_path):
    reg = _registry(tmp_path)
    _register_voice(reg)
    assert reg.set("voice.mode", "ptt") == "ptt"
    with pytest.raises(ValueError):
        reg.set("voice.mode", "always-on")   # not a choice
    with pytest.raises(ValueError):
        reg.set("nope.never", True)          # never registered
    assert reg.get("voice.mode") == "ptt"


@pytest.mark.case("TGL-004", "a set value survives a registry rebuild (toggles.json round-trip)")
def test_persistence_round_trip(tmp_path):
    reg = _registry(tmp_path)
    _register_voice(reg)
    reg.set("voice.mode", "wake")
    # New process, same file: registration picks the stored value up.
    reg2 = _registry(tmp_path)
    _register_voice(reg2)
    assert reg2.get("voice.mode") == "wake"


@pytest.mark.case("TGL-005", "persist=False toggles never land in toggles.json")
def test_unpersisted_stays_out_of_file(tmp_path):
    reg = _registry(tmp_path)
    reg.register("dnd", "bool", "DND", "", default=False, persist=False)
    _register_voice(reg)
    reg.set("dnd", True)
    reg.set("voice.mode", "ptt")
    stored = json.loads((tmp_path / "toggles.json").read_text(encoding="utf-8"))
    assert "dnd" not in stored
    assert stored["voice.mode"] == "ptt"


@pytest.mark.case("TGL-006", "on_change gets the applied value; its crash never blocks the apply")
def test_on_change_fires_and_is_isolated(tmp_path):
    seen = []

    def owner(value):
        seen.append(value)
        raise RuntimeError("owner module blew up")

    reg = _registry(tmp_path)
    reg.register("x", "bool", "X", "", default=False, on_change=owner)
    assert reg.set("x", True) is True      # applied despite the owner crash
    assert seen == [True]
    assert reg.get("x") is True
    reg2 = _registry(tmp_path)
    reg2.register("x", "bool", "X", "", default=False)
    assert reg2.get("x") is True           # and persisted despite it


@pytest.mark.case("TGL-007", "a bad stored value falls back to the default instead of crashing")
def test_bad_stored_value_falls_back(tmp_path):
    (tmp_path / "toggles.json").write_text(
        json.dumps({"voice.mode": "always-on"}), encoding="utf-8")
    reg = _registry(tmp_path)
    _register_voice(reg)
    assert reg.get("voice.mode") == "off"
    # Corrupt file entirely: registry still boots.
    (tmp_path / "toggles.json").write_text("{not json", encoding="utf-8")
    reg2 = _registry(tmp_path)
    _register_voice(reg2)
    assert reg2.get("voice.mode") == "off"


@pytest.mark.case("TGL-008", "registration does not fire on_change; it returns the effective value")
def test_register_returns_initial_silently(tmp_path):
    fired = []
    reg = _registry(tmp_path)
    _register_voice(reg)
    reg.set("voice.mode", "ptt")
    reg2 = _registry(tmp_path)
    initial = _register_voice(reg2, on_change=fired.append)
    assert initial == "ptt"   # owner configures itself from the return value
    assert fired == []        # ...not from a surprise boot-time callback


@pytest.mark.case("TGL-009", "service: dnd flows through the registry and stays coherent everywhere")
def test_service_dnd_coherence(sandbox):
    svc = sandbox.service
    result = svc.set_toggle("dnd", True)
    assert result["ok"] and result["value"] is True
    assert svc.acc.dnd is True                       # owner (app_state) followed
    assert svc.get_status()["dnd"] is True           # status row agrees
    assert [t for t in svc.get_toggles() if t["key"] == "dnd"][0]["value"] is True
    svc.set_dnd(False)                               # the compat shim, sidebar path
    assert svc.acc.dnd is False
    assert [t for t in svc.get_toggles() if t["key"] == "dnd"][0]["value"] is False


@pytest.mark.case("TGL-010", "service: set_toggle on a bad key/value reports, never raises")
def test_service_set_toggle_errors(sandbox):
    svc = sandbox.service
    bad_key = svc.set_toggle("no.such.toggle", True)
    assert bad_key["ok"] is False and "no.such.toggle" in bad_key["error"]
    bad_val = svc.set_toggle("dnd", "maybe")
    assert bad_val["ok"] is False

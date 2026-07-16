r"""
Toggle registry — J0 of the jarvis plan (FRIDAY_jarvis_plan.md §2).

Jack's requirement: anything about FRIDAY he should be able to turn on/off or
switch between gets a switch in ONE control panel in the UI. This module is
the code side of that panel: a leg registers its toggle here and the panel
renders it — zero UI edits per new toggle.

Design constraints this file carries (decided in the plan's §6 leg-opening
entry — change them there first):

  * A toggle is DECLARED IN CODE (key, kind, label, default, owner callback)
    and its VALUE persists in data\toggles.json — the "config overlay file"
    of §2. Deliberately NOT keys in friday_config.yaml: these are JACK's
    runtime switches clicked in the UI, not FRIDAY self-modification, so the
    config-governance tier map is untouched (validate_tiers never sees them).
  * Changes apply at RUNTIME through the owner's on_change callback — no
    restart. Registration itself never fires on_change (the owner configures
    itself from register()'s return value); a surprise boot-time callback is
    how a quiet startup turns into side effects nobody ordered.
  * An owner callback that CRASHES must not wedge the switch: the value is
    applied and persisted first, the callback failure is logged. The panel
    reflecting reality matters more than the owner's bookkeeping.
  * persist=False exists for toggles whose state already has one authoritative
    store (dnd lives in data\app_state.json via Accountability — one fact,
    one place). The registry is then the single CONTROL path, not the store.
"""

import json
import os
import threading
from pathlib import Path

_BOOL_TRUE = ("true", "yes", "on", "1")
_BOOL_FALSE = ("false", "no", "off", "0")


class Toggle:
    """One declared switch. Plain data + the owner hook; validation lives on
    the registry so every toggle is checked the same way."""

    def __init__(self, key, kind, label, description, default,
                 choices=None, on_change=None, persist=True):
        if kind not in ("bool", "enum"):
            raise ValueError(f"toggle {key!r}: kind must be 'bool' or 'enum'")
        if kind == "enum" and not choices:
            raise ValueError(f"toggle {key!r}: enum toggles need choices")
        self.key = key
        self.kind = kind
        self.label = label
        self.description = description
        self.choices = tuple(choices) if choices else None
        self.on_change = on_change
        self.persist = persist
        self.value = default


class ToggleRegistry:
    """The declarative switch registry behind the UI's Controls panel."""

    def __init__(self, store_path, log=None):
        self._path = Path(store_path)
        self._log = log or (lambda text: None)
        self._toggles = {}          # key -> Toggle, insertion-ordered
        self._lock = threading.Lock()  # UI thread sets; background loops read

    # ---------- registration ----------

    def register(self, key, kind, label, description, default,
                 choices=None, on_change=None, persist=True):
        """Declare a switch. Returns the EFFECTIVE initial value (the stored
        one when a persisted toggle was flipped in a past session, else the
        default) — the owner configures itself from this return value;
        on_change is never fired here."""
        t = Toggle(key, kind, label, description, default,
                   choices=choices, on_change=on_change, persist=persist)
        if persist:
            stored = self._stored().get(key, None)
            if stored is not None:
                try:
                    t.value = self._coerce(t, stored)
                except ValueError:
                    # A stale/corrupt stored value must not brick the switch —
                    # fall back to the declared default and say so.
                    self._log(f"{key}: stored value {stored!r} invalid, "
                              f"using default {default!r}")
        with self._lock:
            self._toggles[key] = t
        return t.value

    # ---------- reads ----------

    def get(self, key):
        with self._lock:
            return self._require(key).value

    def describe(self):
        """What the UI renders: every toggle, registration order, live value.
        The panel is dumb by design — this list IS its content."""
        with self._lock:
            return [{"key": t.key, "kind": t.kind, "label": t.label,
                     "description": t.description, "value": t.value,
                     "choices": list(t.choices) if t.choices else None}
                    for t in self._toggles.values()]

    # ---------- writes ----------

    def set(self, key, value):
        """Validate -> apply -> persist -> notify the owner -> log.
        Raises ValueError on an unknown key or a value the kind refuses;
        nothing changes in that case."""
        with self._lock:
            t = self._require(key)
            applied = self._coerce(t, value)
            t.value = applied
            if t.persist:
                self._save()
        # Owner callback runs OUTSIDE the lock (it may call back into a read)
        # and its failure never un-applies the switch.
        if t.on_change is not None:
            try:
                t.on_change(applied)
            except Exception as e:
                self._log(f"{key}: on_change failed ({type(e).__name__}: {e}) "
                          f"— value {applied!r} applied anyway")
        self._log(f"{key} -> {applied!r}")
        return applied

    # ---------- internals ----------

    def _require(self, key):
        t = self._toggles.get(key)
        if t is None:
            raise ValueError(f"no such toggle: {key!r}")
        return t

    @staticmethod
    def _coerce(t, value):
        if t.kind == "bool":
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            if s in _BOOL_TRUE:
                return True
            if s in _BOOL_FALSE:
                return False
            raise ValueError(f"{t.key}: {value!r} is not a boolean")
        v = str(value).strip()
        if v not in t.choices:
            raise ValueError(f"{t.key}: {value!r} is not one of {t.choices}")
        return v

    def _stored(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}  # missing or corrupt file = no stored values, no crash

    def _save(self):
        """Write-through with fsync (the app_state.json pattern) — a toggle
        Jack flipped must survive a hard kill."""
        values = {t.key: t.value for t in self._toggles.values() if t.persist}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(json.dumps(values, indent=2))
            f.flush()
            os.fsync(f.fileno())

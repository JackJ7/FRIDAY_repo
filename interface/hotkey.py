r"""
True system-wide hotkey via the Windows RegisterHotKey API.

The Stage 1 `keyboard`-library approach used low-level keyboard hooks, which
proved unreliable here. RegisterHotKey is the OS-blessed mechanism: Windows
itself watches for the combo and posts WM_HOTKEY to our thread no matter which
app has focus — and it fails loudly at registration time if another program
already owns the combo, so conflicts are detected instead of silently ignored.

Rules of the API worth knowing: RegisterHotKey and the GetMessage loop must
live on the SAME thread, so both happen inside the worker thread below.
"""

import ctypes
import threading
from ctypes import wintypes

_user32 = ctypes.windll.user32

_MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312
_HOTKEY_ID = 0xF71D  # arbitrary, ours

# Virtual-key codes for the non-letter keys we support in config.
_VKS = {f"f{n}": 0x6F + n for n in range(1, 13)}  # f1..f12
_VKS.update({"space": 0x20, "tab": 0x09, "home": 0x24, "end": 0x23})


def _parse(combo: str):
    """'ctrl+alt+f' -> (modifier bitmask, virtual-key code)."""
    mods, vk = 0, None
    for part in combo.lower().replace(" ", "").split("+"):
        if part in _MODS:
            mods |= _MODS[part]
        elif part in _VKS:
            vk = _VKS[part]
        elif len(part) == 1:
            vk = ord(part.upper())
        else:
            raise ValueError(f"Can't parse hotkey part '{part}' in '{combo}'")
    if vk is None:
        raise ValueError(f"Hotkey '{combo}' has no key, only modifiers")
    return mods, vk


class GlobalHotkey:
    """Register `combo` system-wide; call `callback` whenever it's pressed."""

    def __init__(self, combo: str, callback):
        self.combo = combo
        self.callback = callback
        self.error = None          # set if registration failed (e.g. conflict)
        self._registered = threading.Event()

    def start(self, timeout: float = 5.0) -> bool:
        """Returns True if the hotkey is live. On False, .error says why."""
        threading.Thread(target=self._run, daemon=True, name="friday-hotkey").start()
        self._registered.wait(timeout)
        return self.error is None and self._registered.is_set()

    def _run(self):
        try:
            mods, vk = _parse(self.combo)
        except ValueError as e:
            self.error = str(e)
            self._registered.set()
            return

        if not _user32.RegisterHotKey(None, _HOTKEY_ID, mods | _MOD_NOREPEAT, vk):
            code = ctypes.windll.kernel32.GetLastError()
            self.error = (f"'{self.combo}' is already taken by another program "
                          f"(winerror {code})" if code == 1409 else
                          f"RegisterHotKey failed for '{self.combo}' (winerror {code})")
            self._registered.set()
            return

        self._registered.set()
        msg = wintypes.MSG()
        # Windows posts WM_HOTKEY to this thread; GetMessage blocks in between,
        # so this loop costs nothing while idle.
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                try:
                    self.callback()
                except Exception:
                    pass  # a summon failure must not kill the hotkey thread
        _user32.UnregisterHotKey(None, _HOTKEY_ID)


def force_foreground(title: str):
    """Bring the window with this exact title to the front. Works when called
    in response to the user's own hotkey press (Windows then permits the
    focus change; random apps aren't allowed to steal focus)."""
    hwnd = _user32.FindWindowW(None, title)
    if not hwnd:
        return False
    SW_RESTORE = 9
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
    return True

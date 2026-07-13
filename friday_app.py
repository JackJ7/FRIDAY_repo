"""Launcher — start the FRIDAY app (window + tray + hotkey):

    python  friday_app.py    (with console, for development)
    pythonw friday_app.py    (windowless — what the shortcuts use)
"""
import sys
from pathlib import Path

# Under pythonw there is no console: stdout/stderr are None, and any stray
# print() would crash. Route them to a log so windowless failures stay
# diagnosable (logs\app.log).
if sys.stdout is None or sys.stderr is None:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "app.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log

from interface.app import main

if __name__ == "__main__":
    main()

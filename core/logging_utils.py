r"""
Logging: every action and every interaction leaves a trace in logs\.

Two logs:
  logs\actions.log              — one line per filesystem action (reads, writes,
                                  denials); the permission gate's audit trail.
  logs\interactions\<date>.jsonl — one JSON object per exchange (prompt, retrieved
                                  context, tool calls, reply). This doubles as the
                                  Phase 5 fine-tuning dataset, so keep it clean.
"""

import json
from datetime import datetime
from pathlib import Path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ActionLogger:
    def __init__(self, logs_root: Path):
        self.path = Path(logs_root) / "actions.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, kind: str, detail: str):
        """kind is a short tag like READ / WRITE / DENIED / CONFIRM-NO."""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"{_now()} [{kind}] {detail}\n")


class InteractionLogger:
    def __init__(self, logs_root: Path):
        self.dir = Path(logs_root) / "interactions"
        self.dir.mkdir(parents=True, exist_ok=True)

    def log(self, record: dict):
        """Append one exchange to today's .jsonl file (one JSON object per line)."""
        record["timestamp"] = _now()
        day_file = self.dir / f"{datetime.now():%Y-%m-%d}.jsonl"
        with open(day_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

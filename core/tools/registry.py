"""
Tool registry — the Phase 4 seam.

Every capability FRIDAY has is a tool registered here. Adding a new ability
(calendar, script runner, ...) means registering one more tool; the engine
loop never changes.

Every tool also declares its KIND, which drives the engine's taint defense
(invariant #2). A politely-phrased instruction planted in a read file once
got a free brain write executed — phrasing detection in the prompt is soft,
so the barrier is structural: once a turn ingests external content, every
state-changing tool escalates to a Jack-confirm. Kinds:

  internal         reads of FRIDAY's own state, pure computation (default)
  external_read    ingests content from OUTSIDE the trust boundary — disk
                   files, web pages, email, calendar. Taints the turn.
  action           changes state (brain/outbox writes, trackers, drafts,
                   project scaffolding). Confirms while the turn is tainted.
  action_confirmed action that already confirms on EVERY call by itself
                   (create_event via approve_outbound) — no double-confirm.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str   # shown to the model — write it like good docs
    parameters: dict   # JSON schema for the arguments
    func: callable
    kind: str = "internal"
    arm: Callable[[], bool] | None = None


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name: str, description: str, parameters: dict, func,
                 kind: str = "internal", arm=None):
        assert kind in ("internal", "external_read", "action", "action_confirmed")
        self._tools[name] = Tool(name, description, parameters, func, kind, arm)

    def kind(self, name: str) -> str:
        """A tool's declared kind; unknown names are 'internal' (they can't
        run anyway — call() rejects them)."""
        t = self._tools.get(name)
        return t.kind if t else "internal"

    def to_ollama(self) -> list:
        """Tool definitions in the format Ollama's chat API expects."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
            if t.arm is None or t.arm()
        ]

    def call(self, name: str, args: dict) -> str:
        """
        Execute a tool and ALWAYS return a string for the model — including on
        failure. Errors go back as text so FRIDAY can explain what happened
        (e.g. a declined confirmation) instead of the app crashing.
        """
        if name not in self._tools:
            return f"ERROR: unknown tool '{name}'"
        try:
            return str(self._tools[name].func(**(args or {})))
        except TypeError as e:
            return f"ERROR: bad arguments for {name}: {e}"
        except Exception as e:
            return f"ERROR ({type(e).__name__}): {e}"

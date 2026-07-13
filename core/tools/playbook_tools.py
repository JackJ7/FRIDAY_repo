r"""
Playbook tools — author, refine, retrieve, follow (spec: method transfer).
"""


def register_playbook_tools(registry, playbooks):

    def list_playbooks() -> str:
        idx = playbooks.index_text()
        return idx or "No playbooks yet. Author one with write_playbook."

    def read_playbook(name: str) -> str:
        return playbooks.read(name)

    def write_playbook(name: str, goal: str, when_to_use: str, steps: list,
                       checks: list = None, notes: str = "") -> str:
        return playbooks.write(name, goal, when_to_use,
                               [str(s) for s in (steps or [])],
                               [str(c) for c in (checks or [])], notes)

    registry.register(
        "list_playbooks",
        "Your playbooks: reusable procedures. The index is also in your context.",
        {"type": "object", "properties": {}},
        list_playbooks,
    )
    registry.register(
        "read_playbook",
        "Read one playbook in full before following it. Announce which "
        "playbook you're running when you use one.",
        {"type": "object", "properties": {"name": {"type": "string"}},
         "required": ["name"]},
        read_playbook,
    )
    registry.register(
        "write_playbook",
        "Capture a repeatable procedure as a playbook (or refine an existing "
        "one — same name overwrites, history stays in git). Steps should be "
        "concrete enough that following them cold reproduces the result.",
        {"type": "object", "properties": {
            "name": {"type": "string", "description": "Short name, e.g. 'Datasheet extraction'"},
            "goal": {"type": "string"},
            "when_to_use": {"type": "string", "description": "The trigger — what kind of task matches"},
            "steps": {"type": "array", "items": {"type": "string"}},
            "checks": {"type": "array", "items": {"type": "string"},
                       "description": "How to verify the result before presenting"},
            "notes": {"type": "string"}},
         "required": ["name", "goal", "when_to_use", "steps"]},
        write_playbook,
        kind="action",
    )

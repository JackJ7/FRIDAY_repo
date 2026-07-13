"""
Brain tools: how FRIDAY searches, reads, and writes her own memory.
"""

from core.project_meta import set_field


def register_brain_tools(registry, brain, retriever, top_k: int):

    def search_brain(query: str, include_test_archive: bool = False) -> str:
        # In a test session her own archive IS this session's memory —
        # always searchable regardless of the flag.
        include = bool(include_test_archive) or brain.test_session
        results = retriever.retrieve(query, top_k, include_test=include)
        if not results:
            return "No brain notes matched that query."
        out = []
        for r in results:
            tag = (" (TEST ARCHIVE — from testing, not lived history)"
                   if r.path.startswith("test_archive/") else "")
            out.append(f"[{r.path}]{tag}\n{r.snippet}")
        return "\n\n".join(out) + "\n\n(Use read_brain for a full note.)"

    def read_brain(path: str) -> str:
        return brain.read_note(path)

    def write_brain(path: str, content: str, mode: str = "create", summary: str = "") -> str:
        return brain.write_note(path, content, mode=mode, summary=summary)

    def update_note_field(path: str, field: str, value: str) -> str:
        """Deterministic single-field edit — code does the surgery, not the model."""
        text = brain.read_note(path)
        new_text = set_field(text, field, value)
        brain.write_note(path, new_text, mode="overwrite",
                         summary=f"Set {field}: {value} ({path})")
        return f"Updated {field} to '{value}' in {path}."

    registry.register(
        "search_brain",
        "Search your memory (the brain) by keywords. Do this before saying you "
        "don't know something about Jack or his projects. Set "
        "include_test_archive=true ONLY when the question is about testing/"
        "diagnostics — archive results come from capability tests, not lived "
        "history, and must be framed that way.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "include_test_archive": {
                    "type": "boolean",
                    "description": "Also search test_archive/ (test-session "
                                   "memories). Default false."},
            },
            "required": ["query"],
        },
        search_brain,
    )
    registry.register(
        "read_brain",
        "Read one full brain note by its relative path, e.g. projects/perry.md",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        read_brain,
    )
    registry.register(
        "write_brain",
        "Save or update a note in your brain. Folders: preferences/ (Jack's "
        "preferences), projects/, people/, episodic/ (session learnings), "
        "inbox/ (unsorted). mode 'create' for a new note, 'append' to add to "
        "one, 'overwrite' to rewrite one. Your brain is yours — no permission "
        "needed, and every change is git-committed so nothing is lost. "
        "Give a short summary — it becomes the git commit message.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path like preferences/coding_style.md"},
                "content": {"type": "string", "description": "Markdown content"},
                "mode": {"type": "string", "enum": ["create", "append", "overwrite"]},
                "summary": {"type": "string", "description": "One-line summary of the change (git commit message)"},
            },
            "required": ["path", "content"],
        },
        write_brain,
        kind="action",
    )
    registry.register(
        "update_note_field",
        "Set one structured field line (- **Field:** value) in a brain note, "
        "exactly and in place. THE way to change a project's Status ('active', "
        "'reference', or any value that fits) or fix a field-style fact — more "
        "reliable than rewriting the note.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Note path, e.g. projects/perry.md"},
                "field": {"type": "string", "description": "Field name, e.g. Status"},
                "value": {"type": "string"},
            },
            "required": ["path", "field", "value"],
        },
        update_note_field,
        kind="action",
    )

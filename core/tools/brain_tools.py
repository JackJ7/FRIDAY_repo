"""
Brain tools: how FRIDAY searches, reads, and writes her own memory.
"""

import re

from core.project_meta import match_field, set_field


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
        # Phantom-project guard (armor CONSOLIDATE CN.1b). Every file under
        # projects/ IS a project to the resolver's inventory, and create_project
        # is the ONE door with the near-duplicate check on it. CN.0's capture
        # caught the memory pass write_brain-ing Jack's consolidation TASK into
        # projects/ as a brand-new "project" — which every later turn then
        # surfaced as real. Refuse CREATING a projects/ note here (any mode:
        # append to a missing note creates too); edits to existing project
        # notes stay free — merge surgery and status updates need them. The
        # ERROR prefix keeps it out of the durable-write ledger (TM.1).
        rel = (path or "").replace("\\", "/").lstrip("/")
        if rel.startswith("projects/") and not (brain.root / rel).exists():
            # The corrective must name the RETRY, not just the refusal: the
            # CN.5 candidate measured the 14B answering this ERROR by asking
            # Jack which project to create — and the stated fact was lost
            # (MEM-001, CN.6.1). Facts about an EXISTING project belong in
            # that project's existing note.
            return ("ERROR: new notes under projects/ are managed — every file "
                    "there becomes a project in Jack's inventory. Do NOT ask "
                    "Jack about this; retry write_brain NOW with a corrected "
                    "path: a fact about an existing project belongs in that "
                    "project's EXISTING note (mode 'append'); a task, plan, or "
                    "loose note goes under inbox/ or episodic/. Only use "
                    "create_project for a genuinely NEW project (it checks for "
                    "near-duplicates).")
        return brain.write_note(path, content, mode=mode, summary=summary)

    def update_note_field(path: str, field: str, value: str) -> str:
        """Deterministic single-field edit — code does the surgery, not the model.

        Field-matching floor (armor PENDING-TASK PT.3, the MEM-003 fix): the
        model paraphrases field names — 'load cell rating' for the note's
        'Load cell' line — and the old exact match INSERTED a second,
        contradicting line instead of updating the one that exists. On an
        exact miss, fuzzy-match against the note's EXISTING fields: one hit
        updates THAT line, keeping the note's canonical field name (the
        model's paraphrase never renames a field); several hits refuse with
        a corrective that names the candidates and the retry (the CN.6.1
        shape — and the P4 directive's which-ask rule: a clarify must name
        its options, never go generic); zero hits insert, as always."""
        text = brain.read_note(path)
        canonical = field
        if not re.search(rf"^\s*-\s*\*\*{re.escape(field)}:\*\*", text,
                         re.MULTILINE | re.IGNORECASE):
            hits = match_field(text, field, value)
            if len(hits) == 1:
                canonical = hits[0]
            elif len(hits) > 1:
                options = ", ".join(f"'{h}'" for h in hits)
                return (f"ERROR: field '{field}' is ambiguous in {path} — it "
                        f"matches these existing fields: {options}. If Jack's "
                        "message says which one he means, retry "
                        "update_note_field NOW with that exact field name. "
                        "Only if it genuinely doesn't, ask him which of "
                        f"{options} to update — name them exactly, never a "
                        "generic 'could you specify'. Do not report this "
                        "error text to Jack.")
        new_text = set_field(text, canonical, value)
        brain.write_note(path, new_text, mode="overwrite",
                         summary=f"Set {canonical}: {value} ({path})")
        return f"Updated {canonical} to '{value}' in {path}."

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
        # Example paths use a CONCRETE throwaway name — never a real project
        # (schema text rides every model context; GT-C9 measured the 14B
        # quoting a schema example as if it were a real project, CN.4.1) and
        # never a template token (the CN.5 candidate measured degraded path
        # formation against "projects/<slug>.md", CN.6.1 — the 14B forms args
        # from concrete shapes).
        "Read one full brain note by its relative path, e.g. projects/sun_dial.md",
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
                "path": {"type": "string", "description": "Note path, e.g. projects/sun_dial.md"},
                "field": {"type": "string", "description": "Field name, e.g. Status"},
                "value": {"type": "string"},
            },
            "required": ["path", "field", "value"],
        },
        update_note_field,
        kind="action",
    )

r"""
Project tools (Phase 2): the agentic actions.

create_project        — scaffold a folder under the projects root + a brain note
add_files_to_project  — copy/move real files into a project's folder

A project's folder on disk is recorded in its brain note as a
"- **Folder:** <path>" line, so FRIDAY (and Jack, in Obsidian) can always see
where a project lives. Every write here goes through the permission gate:
project-zone writes always confirm, and moves warn that sources get deleted.
"""

import glob
import re
import shutil
from datetime import date
from pathlib import Path


def _slug(name: str) -> str:
    """'Doc Ock' -> 'doc_ock': safe for folder and note file names."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def register_project_tools(registry, gate, brain, projects_root: Path):
    projects_root = Path(projects_root).resolve()

    def _note_path(name: str) -> str:
        return f"projects/{_slug(name)}.md"

    def _find_folder(name: str):
        """Locate a project's folder: the note's Folder line first, then the
        default location. Returns None if the project has no folder on disk."""
        try:
            text = brain.read_note(_note_path(name))
        except FileNotFoundError:
            text = ""
        m = re.search(r"\*\*Folder:\*\*\s*(.+)", text)
        if m:
            p = Path(m.group(1).strip())
            if p.is_dir():
                return p
        p = projects_root / _slug(name)
        return p if p.is_dir() else None

    # ---------- create_project ----------

    def create_project(name: str, description: str = "") -> str:
        folder = projects_root / _slug(name)
        note = _note_path(name)
        results = []

        if folder.exists():
            results.append(f"Folder already exists: {folder}")
        else:
            # One confirmation covers the scaffold (project zone always confirms).
            readme = folder / "README.md"
            readme_text = (f"# {name}\n\n{description or '(no description yet)'}\n\n"
                           f"*Project folder created by FRIDAY on {date.today()}.*\n")
            gate.approve_write(readme, "create", new_content=readme_text)
            folder.mkdir(parents=True, exist_ok=True)
            readme.write_text(readme_text, encoding="utf-8")
            results.append(f"Created folder: {folder} (with README.md)")

        folder_line = f"- **Folder:** {folder}"
        try:
            existing = brain.read_note(note)
            if folder_line not in existing:
                brain.write_note(note, f"\n{folder_line}\n", mode="append",
                                 summary=f"Link project '{name}' to folder {folder}")
                results.append(f"Added folder location to existing note {note}")
            else:
                results.append(f"Note {note} already points at this folder")
        except FileNotFoundError:
            content = (f"# {name}\n\n{description or '(no description yet)'}\n\n"
                       f"- **Status:** active\n"
                       f"{folder_line}\n- **Created:** {date.today()}\n\n"
                       f"## Log\n-\n")
            brain.write_note(note, content, mode="create",
                             summary=f"Create project note: {name}")
            results.append(f"Created brain note {note}")

        return "\n".join(results)

    # ---------- add_files_to_project ----------

    def add_files_to_project(project: str, files: list, operation: str = "copy") -> str:
        if operation not in ("copy", "move"):
            return f"ERROR: operation must be 'copy' or 'move', got '{operation}'"

        folder = _find_folder(project)
        if folder is None:
            return (f"ERROR: project '{project}' has no folder on disk yet. "
                    f"Use create_project first (its note may also need a "
                    f"'- **Folder:** <path>' line if the folder lives elsewhere).")

        # Expand wildcards and validate every source before touching anything.
        sources, problems = [], []
        for f in files:
            if "*" in f or "?" in f:
                hits = [Path(h) for h in glob.glob(f) if Path(h).is_file()]
                if hits:
                    sources.extend(gate.check_read(h) for h in hits)
                else:
                    problems.append(f"no files match '{f}'")
            else:
                p = gate.check_read(f)
                if p.is_file():
                    sources.append(p)
                elif p.is_dir():
                    problems.append(f"'{f}' is a folder — pass its files or a wildcard like {f}\\*")
                else:
                    problems.append(f"'{f}' does not exist")

        if not sources:
            return "ERROR: nothing to transfer. " + "; ".join(problems)

        # One batch confirmation (gate lists every file; move warns about deletion).
        pairs = gate.approve_transfer(sources, folder, operation)
        for src, dst in pairs:
            if operation == "move":
                shutil.move(str(src), str(dst))
            else:
                shutil.copy2(src, dst)

        report = (f"{'Moved' if operation == 'move' else 'Copied'} "
                  f"{len(pairs)} file(s) into {folder}:\n"
                  + "\n".join(f"  {d.name}" for _, d in pairs))
        if problems:
            report += "\nSkipped: " + "; ".join(problems)

        # Ingest implies comprehend (Task 6): filing and perceiving cannot be
        # separated — the comprehension pass rides in THIS tool result, so an
        # artifact can never again be "placed" without being seen (or being
        # honestly marked UNREAD). The Doc Ock schematics were filed by this
        # very tool and never read; that failure mode is now structural.
        from core.artifacts import comprehension_block, perceive
        report += "\n\n" + comprehension_block(
            [perceive(dst) for _, dst in pairs])
        return report

    # ---------- registration ----------

    registry.register(
        "create_project",
        "Create a new project: scaffolds a folder (with a README) under Jack's "
        "projects root and a projects/ note in your brain describing it. Also "
        "use this to create a folder for an existing project that has none yet.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name, e.g. 'Doc Ock'"},
                "description": {"type": "string", "description": "One-paragraph description of the project"},
            },
            "required": ["name"],
        },
        create_project,
        kind="action",
    )
    registry.register(
        "add_files_to_project",
        "Copy (default) or move real files into a project's folder. Wildcards "
        "like C:\\path\\*.stl work. Jack confirms the batch before anything happens.",
        {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name, e.g. 'Doc Ock'"},
                "files": {"type": "array", "items": {"type": "string"},
                          "description": "Absolute paths (wildcards allowed)"},
                "operation": {"type": "string", "enum": ["copy", "move"]},
            },
            "required": ["project", "files"],
        },
        add_files_to_project,
        kind="action",
    )

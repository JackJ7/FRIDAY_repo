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

from core.project_resolver import ProjectResolver


def _slug(name: str) -> str:
    """'Doc Ock' -> 'doc_ock': safe for folder and note file names."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def register_project_tools(registry, gate, brain, projects_root: Path):
    projects_root = Path(projects_root).resolve()
    # The shared deterministic resolver (Notes-10 Phase 3, §1). One place answers
    # "which project is Jack talking about / where does it live", used by the
    # tools here AND handed to the engine (bootstrap) for its per-turn hint, so
    # the model never guesses a project path.
    resolver = ProjectResolver(brain, projects_root)

    def _note_path(name: str) -> str:
        return f"projects/{_slug(name)}.md"

    def _find_folder(name: str):
        """Locate a project's folder, via the shared resolver: the note's Folder
        line first, then the default location. Returns None if the project has
        no folder on disk. (One implementation — see ProjectResolver.folder_for.)"""
        return resolver.folder_for(name)

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

    # ---------- resolve_project (Notes-10 Phase 3, §1) ----------

    def resolve_project(name: str) -> str:
        """Deterministic name -> project lookup so the model never guesses a
        path. Returns the note, folder, status, and a file listing on a confident
        single match; asks which on genuine ambiguity; names the closest (or says
        there are none) when nothing matches — honest either way (invariant 4)."""
        outcome, data = resolver.resolve_one(name)
        if outcome == "one":
            p = data
            lines = [f"Project '{p['title']}' (slug {p['slug']}, status {p['status']}).",
                     f"  Note:   {p['note_path'] or '(no note yet)'}"]
            if p["folder_exists"]:
                folder = Path(p["folder"])
                lines.append(f"  Folder: {folder}")
                try:
                    entries = sorted(c.name + ("\\" if c.is_dir() else "")
                                     for c in folder.iterdir())
                    lines.append("  Files:  " + (", ".join(entries) if entries
                                                 else "(folder is empty)"))
                except OSError as exc:
                    lines.append(f"  Files:  (could not list folder: {exc})")
            elif p["folder"]:
                lines.append(f"  Folder: {p['folder']} — RECORDED but not on disk "
                             f"right now; say so rather than guessing.")
            else:
                lines.append("  Folder: none on disk yet (use create_project to "
                             "make one, or add_files_to_project once it exists).")
            return "\n".join(lines)
        if outcome == "many":
            rows = "\n".join(
                f"  - {p['title']} (slug {p['slug']}, folder {p['folder'] or 'none'})"
                for p in data)
            return (f"Several projects match '{name}' — ask Jack which one he "
                    f"means before acting:\n{rows}")
        # none
        if data:  # weak candidates exist — name the closest, honestly
            closest = ", ".join(f"{p['title']}" for p in data[:3])
            return (f"No project confidently matches '{name}'. Closest by name: "
                    f"{closest}. Confirm with Jack or use list_projects.")
        return (f"No project matches '{name}', and there are no project notes to "
                f"match against yet. Use list_projects to see what exists.")

    # ---------- registration ----------

    registry.register(
        "resolve_project",
        "Resolve a free-text project name (how Jack said it, e.g. 'the doc ock "
        "project') to its real brain note, on-disk folder, status, and file "
        "listing. Call this BEFORE reading or listing a project's files instead "
        "of guessing a path. Returns the match, or asks which when ambiguous.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Project name as Jack referred to it"},
            },
            "required": ["name"],
        },
        resolve_project,
        kind="internal",
    )
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

    # Hand the shared resolver back so bootstrap can wire it onto the engine for
    # its per-turn resolution hint (the engine never guesses a project path).
    return resolver

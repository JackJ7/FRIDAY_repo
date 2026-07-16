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

from core.project_meta import set_field
from core.project_resolver import STRONG, ProjectResolver, _norm


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

    def create_project(name: str, description: str = "",
                       confirm_new: bool = False) -> str:
        new_slug = _slug(name)

        # Near-duplicate guard (Notes-10 Phase 3, §4). Before scaffolding a NEW
        # project, check it isn't a near-copy of one that already exists — the
        # single guard that would have stopped the fourth 'claudecodeupgrade'
        # sibling. Only fires for a genuinely new slug (re-running create on an
        # EXISTING project to give it a folder is a supported use, not a dup) and
        # is overridable: once Jack confirms it's really new, the model calls
        # again with confirm_new=true. The model relays the question; it never
        # decides "genuinely new" on its own.
        if new_slug not in {p["slug"] for p in resolver.projects()} and not confirm_new:
            near = [c for c in resolver.resolve(name)
                    if c["score"] >= STRONG and c["slug"] != new_slug]
            if near:
                rows = "; ".join(
                    f"'{c['title']}' (folder {c['folder'] or 'none'}, "
                    f"note {c['note_path'] or 'none'})" for c in near)
                return (
                    f"A similar project already exists — I did NOT create a new "
                    f"one to avoid a near-duplicate. Near-match(es): {rows}. If "
                    f"Jack means that existing project, add to it "
                    f"(add_files_to_project) or consolidate with merge_projects. "
                    f"Only if he confirms this is GENUINELY different, call "
                    f"create_project again with confirm_new=true.")

        folder = projects_root / new_slug
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

    # ---------- list_projects (Notes-10 Phase 3, §2) ----------

    def list_projects() -> str:
        """Every project FRIDAY knows about: name, status, folder, note path.
        The consolidation transcript (cluster C) died for lack of exactly this
        surface — asked to reduce N projects to one, the model had no way to SEE
        the N, so it reached for create. This is the deterministic inventory it
        should read first."""
        projects = sorted(resolver.projects(), key=lambda p: p["title"].lower())
        if not projects:
            return ("No projects yet. (No projects/ notes and no folders under "
                    "the projects root.)")
        lines = [f"{len(projects)} project(s):"]
        for p in projects:
            if p["folder_exists"]:
                folder = p["folder"]
            elif p["folder"]:
                folder = f"{p['folder']} (recorded, not on disk)"
            else:
                folder = "no folder on disk"
            note = p["note_path"] or "no note"
            lines.append(f"  - {p['title']} — status: {p['status']}; "
                         f"folder: {folder}; note: {note}")
        return "\n".join(lines)

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

    # ---------- merge_projects (Notes-10 Phase 3, §3) ----------

    def _folded_body(text: str) -> str:
        """The narrative/log content of a note, minus its `# title` heading and
        any `- **Field:** value` lines. Those structured fields belong to the
        note that owns them — folding a COPY into the survivor would duplicate
        its Status/Folder (and the brain's one-field-one-value guard refuses a
        second copy). Provenance is carried by the '## Merged from X' heading;
        the survivor keeps its own fields."""
        out = []
        for line in text.splitlines():
            if re.match(r"^\s*#\s", line):
                continue
            if re.match(r"^\s*-\s*\*\*[^*]+:\*\*", line):
                continue
            out.append(line)
        return "\n".join(out).strip()

    def _unique_dest(dst: Path) -> Path:
        """A non-colliding destination path — so merging two folders that both
        hold 'notes.md' keeps BOTH (name_1.ext) instead of silently overwriting.
        Erring non-destructive is safer than the overwrite the confirm warned of."""
        if not dst.exists():
            return dst
        stem, suffix, i = dst.stem, dst.suffix, 1
        while True:
            cand = dst.with_name(f"{stem}_{i}{suffix}")
            if not cand.exists():
                return cand
            i += 1

    def _resolve_exact(name: str):
        """Resolve one name to a single project for the merge, or a string error.
        A merge operates on NEAR-DUPLICATES, which are by definition fuzzy-
        ambiguous, so an EXACT normalized slug/title match wins first (the model
        passes the precise names it saw via list_projects) — only a name with no
        exact hit falls back to the fuzzy resolver, and genuine ambiguity/absence
        is refused rather than guessed (a merge is too destructive to pick the
        wrong target silently, invariant 4)."""
        norm = _norm(name)
        exact = [p for p in resolver.projects()
                 if _norm(p["slug"]) == norm or _norm(p["title"]) == norm]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            names = ", ".join(f"'{p['slug']}'" for p in exact)
            return (f"ERROR: '{name}' matches several projects with the same name "
                    f"({names}) — use the distinct slug.")
        outcome, data = resolver.resolve_one(name)
        if outcome == "one":
            return data
        if outcome == "many":
            names = ", ".join(f"'{d['title']}'" for d in data)
            return f"ERROR: '{name}' is ambiguous ({names}) — name it precisely."
        return f"ERROR: no project matches '{name}'."

    def merge_projects(target: str, duplicates: list) -> str:
        """Consolidate `duplicates` INTO `target` (cluster C — 'make it only
        one'). Deterministic surgery, the model just orchestrates: move every
        duplicate folder's files into the target folder (ONE batch confirm),
        append each duplicate note's content under a '## Merged from X' heading
        in the target note, and mark each duplicate note '- **Status:** merged
        into <target>'. The duplicate notes/folders are left in place (status =
        the record; git = the undo), never deleted here."""
        if isinstance(duplicates, str):
            duplicates = [duplicates]
        if not duplicates:
            return ("ERROR: no duplicate projects given. Call with the survivor "
                    "as `target` and the projects to fold in as `duplicates`.")

        t = _resolve_exact(target)
        if isinstance(t, str):
            return t
        target_slug = t["slug"]
        target_note = t["note_path"] or f"projects/{target_slug}.md"

        dups, seen = [], {target_slug}
        for name in duplicates:
            d = _resolve_exact(name)
            if isinstance(d, str):
                return d
            if d["slug"] in seen:
                if d["slug"] == target_slug:
                    return (f"ERROR: '{name}' resolves to the target itself — a "
                            f"project can't be merged into itself.")
                continue  # a duplicate named twice
            seen.add(d["slug"])
            dups.append(d)
        if not dups:
            return "ERROR: nothing to merge once the target was excluded."

        # Gather every file across the duplicate folders (the destructive part).
        moves = []
        for d in dups:
            if d["folder_exists"]:
                moves += [f for f in Path(d["folder"]).iterdir() if f.is_file()]

        # The target needs a folder to receive files; make one if it lacks it.
        target_folder = Path(t["folder"]) if t["folder_exists"] else None
        created_folder = False
        if moves and target_folder is None:
            target_folder = projects_root / target_slug
            target_folder.mkdir(parents=True, exist_ok=True)
            created_folder = True

        # ONE batch confirm for all the moves (the gate lists every file).
        moved = []
        if moves:
            pairs = gate.approve_transfer([str(m) for m in moves],
                                          target_folder, "move")
            for src, dst in pairs:
                dst = _unique_dest(dst)
                shutil.move(str(src), str(dst))
                moved.append(dst.name)

        # Note surgery — free brain writes (logged + git-versioned = reversible).
        # Ensure the target note exists first (a folder-only target may lack one).
        try:
            brain.read_note(target_note)
        except FileNotFoundError:
            brain.write_note(
                target_note,
                f"# {t['title']}\n\n- **Status:** active\n",
                mode="create", summary=f"Create survivor note for {t['title']}")

        merged_notes, restatused, orphans = [], [], []
        for d in dups:
            if d["note_path"]:
                body = _folded_body(brain.read_note(d["note_path"]))
                brain.write_note(
                    target_note,
                    f"\n\n## Merged from {d['title']}\n\n{body}\n",
                    mode="append",
                    summary=f"Merge {d['title']} into {t['title']}")
                merged_notes.append(d["title"])
                # Mark the duplicate note as merged (its content now lives in the
                # target; a stale duplicate presented as live was the original sin).
                dup_text = brain.read_note(d["note_path"])
                brain.write_note(
                    d["note_path"],
                    set_field(dup_text, "Status", f"merged into {t['title']}"),
                    mode="overwrite",
                    summary=f"Mark {d['title']} merged into {t['title']}")
                restatused.append(d["title"])
            else:
                orphans.append(d["title"])

        # If we created the target folder, record it on the note.
        if created_folder:
            ttext = brain.read_note(target_note)
            brain.write_note(target_note, set_field(ttext, "Folder", str(target_folder)),
                             mode="overwrite",
                             summary=f"Record folder for {t['title']}")

        # Honest report of exactly what happened.
        out = [f"Merged {len(dups)} project(s) into '{t['title']}':"]
        if moved:
            out.append(f"  Moved {len(moved)} file(s) into {target_folder}: "
                       + ", ".join(moved))
        else:
            out.append("  No files to move (duplicates had no folders on disk).")
        if merged_notes:
            out.append("  Folded note content from: " + ", ".join(merged_notes))
        if restatused:
            out.append("  Marked as 'merged into " + t['title'] + "': "
                       + ", ".join(restatused))
        if orphans:
            out.append("  Folder-only (no note to re-status): " + ", ".join(orphans))
        out.append("  Duplicate notes/folders kept in place (status is the "
                   "record; use git to undo).")
        return "\n".join(out)

    # ---------- registration ----------

    registry.register(
        "list_projects",
        "List every project you know about — name, status, folder, and note "
        "path — from your projects/ notes and folders. Read this FIRST when Jack "
        "asks about 'your projects' or wants to consolidate/merge/reduce them, "
        "so you act on the real set instead of creating a new one.",
        {"type": "object", "properties": {}},
        list_projects,
        kind="internal",
    )
    registry.register(
        "resolve_project",
        "Resolve a free-text project name (however Jack phrased it) to its "
        "real brain note, on-disk folder, status, and file "
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
        "merge_projects",
        "Consolidate duplicate projects INTO one survivor: moves the duplicates' "
        "files into the target folder, folds their note content into the target "
        "note, and marks each duplicate 'merged into <target>'. Use this (never "
        "create_project) when Jack says 'make these one' / 'there are too many'. "
        "List with list_projects and confirm the survivor with Jack first. Jack "
        "confirms the file moves before anything happens.",
        {
            "type": "object",
            "properties": {
                "target": {"type": "string",
                           "description": "The survivor project (kept)"},
                "duplicates": {"type": "array", "items": {"type": "string"},
                               "description": "Projects to fold into the target"},
            },
            "required": ["target", "duplicates"],
        },
        merge_projects,
        kind="action",
    )
    registry.register(
        "create_project",
        "Create a new project: scaffolds a folder (with a README) under Jack's "
        "projects root and a projects/ note in your brain describing it. Also "
        "use this to create a folder for an existing project that has none yet. "
        "If a similar project already exists it will NOT create a duplicate — it "
        "returns the match so you can ask Jack; only pass confirm_new=true after "
        "he confirms it is genuinely a new, separate project.",
        {
            "type": "object",
            "properties": {
                # No example name here BY DESIGN: schema text rides every model
                # context, and GT-C9 (stamp 1654 T2) measured the 14B lifting a
                # schema example verbatim into a fabricated clarify. Real
                # project names in schemas double as test contamination.
                "name": {"type": "string", "description": "Project name"},
                "description": {"type": "string", "description": "One-paragraph description of the project"},
                "confirm_new": {"type": "boolean",
                                "description": "Set true ONLY after Jack confirms this is "
                                "genuinely new despite a similar existing project"},
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
                "project": {"type": "string", "description": "Project name"},
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

r"""
Repo tools (upgrade plan Task 5): point FRIDAY at a working git repo and get
review and advice — pull, map, targeted reads. Never bulk-load.

Scope guardrails, structural not promised:
  * Everything lands in a sandboxed workspaces\ dir under data\. FRIDAY has
    NO tool that writes there and NO push/commit tool — absent by design,
    like email send. The gate denies workspace writes anyway (not a writable
    zone), so even a confused write attempt dead-ends.
  * repo_sync / repo_map / search_repo are `external_read`: cloned code is
    OUTSIDE the trust boundary, so the taint defense applies — an
    instruction planted in a README cannot direct actions (invariant 2).
  * Patch OUTPUT is governed by the `repo.allow_patches` config key, tier
    LOCKED (Task 2): until Jack flips it in the file himself, no patch tool
    registers at all. Even then the design is .patch files to the outbox for
    Jack to apply — she never pushes.
  * Context discipline lives in the tool contract: sync -> map -> TARGETED
    reads driven by the question (read_file already exists and works on
    workspace paths). repo_map is hard-capped so a huge tree can't flood.

Provenance: repo_sync/repo_map report the HEAD commit; anything she saves
about the code should cite repo@commit so "you told me X about the control
loop" is traceable (Task 1 dovetail).
"""

import re
import shutil
import subprocess
from pathlib import Path

# Directories that are build noise, not code — never mapped, never searched.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
              "build", ".idea", ".vscode", "target", ".tox", ".mypy_cache",
              ".pytest_cache", "unsloth_compiled_cache"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
               ".gz", ".7z", ".exe", ".dll", ".so", ".dylib", ".bin",
               ".gguf", ".pt", ".onnx", ".stl", ".step", ".jpg", ".mp4"}
_ENTRY_HINTS = ("main.py", "app.py", "__main__.py", "setup.py",
                "pyproject.toml", "package.json", "cmakelists.txt",
                "makefile", "main.cpp", "main.c", "index.js", "index.ts",
                "cargo.toml", "platformio.ini")


def _run_git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=300)


def _head(repo: Path) -> str:
    r = _run_git(repo, "rev-parse", "--short", "HEAD")
    return r.stdout.strip() or "?"


def register_repo_tools(registry, workspaces: Path):
    workspaces = Path(workspaces).resolve()

    def _resolve_repo(name_or_path: str) -> Path:
        """A synced repo by its workspace name (or a path inside one).
        Refuses anything that escapes workspaces\ — reads of arbitrary disk
        already have their own tool and rules."""
        p = (workspaces / str(name_or_path)).resolve()
        if not p.is_relative_to(workspaces):
            raise ValueError(f"'{name_or_path}' escapes the workspace area.")
        return p

    # ---------- repo_sync ----------

    def repo_sync(url_or_path: str, branch: str = "") -> str:
        src = str(url_or_path).strip()
        # Workspace dir name from the repo name, filesystem-safe.
        name = re.sub(r"[^A-Za-z0-9._-]+", "_",
                      Path(src.rstrip("/\\")).name.removesuffix(".git")) or "repo"
        dest = workspaces / name
        workspaces.mkdir(parents=True, exist_ok=True)

        if (dest / ".git").exists():
            r = _run_git(dest, "pull", "--ff-only")
            if r.returncode != 0:
                return f"ERROR: pull failed for {name}: {r.stderr.strip()[:300]}"
            action = "Pulled"
        else:
            args = ["clone", "--depth", "1"]
            if branch:
                args += ["--branch", branch]
            args += [src, str(dest)]
            r = _run_git(None, *args)
            if r.returncode != 0:
                return f"ERROR: clone failed: {r.stderr.strip()[:300]}"
            action = "Cloned (shallow)"

        n_files = sum(1 for _ in dest.rglob("*")
                      if _.is_file()
                      and not any(part in _SKIP_DIRS for part in _.parts))
        return (f"{action} '{name}' -> workspace ({n_files} files, HEAD "
                f"{_head(dest)}). Workspace root: {dest} — read files with "
                f"read_file on paths under that root, EXACTLY as given "
                f"(never guess a path). This workspace is READ-ONLY for you: "
                f"review and advise; patches/pushes are Jack's. Next: "
                f"repo_map '{name}', then TARGETED read_file calls driven by "
                f"the question — never bulk-read a repo. Cite "
                f"{name}@{_head(dest)} in anything you save about this code.")

    # ---------- repo_map ----------

    def repo_map(repo: str, max_chars: int = 5000) -> str:
        try:
            root = _resolve_repo(repo)
        except ValueError as e:
            return f"ERROR: {e}"
        if not root.is_dir():
            return (f"ERROR: no synced repo '{repo}'. repo_sync it first; "
                    f"workspaces present: "
                    + (", ".join(p.name for p in workspaces.iterdir()
                                 if p.is_dir()) or "(none)"))

        langs, entries, rows = {}, [], []
        for p in sorted(root.rglob("*")):
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            ext = p.suffix.lower()
            if ext in _BINARY_EXT:
                langs["binary"] = langs.get("binary", 0) + 1
                continue
            try:
                lines = sum(1 for _ in open(p, encoding="utf-8",
                                            errors="replace"))
            except OSError:
                continue
            langs[ext or "(none)"] = langs.get(ext or "(none)", 0) + 1
            rows.append((rel, lines))
            if p.name.lower() in _ENTRY_HINTS:
                entries.append(rel)

        breakdown = ", ".join(f"{k}:{v}" for k, v in
                              sorted(langs.items(), key=lambda x: -x[1]))
        tree = "\n".join(f"  {rel} ({n} lines)" for rel, n in rows)
        out = (f"Repo map: {root.name} @ {_head(root)}\n"
               f"Root on disk: {root}  (read_file paths = root + / + the "
               f"relative path below — use them exactly, never guess)\n"
               f"Languages (files): {breakdown}\n"
               f"Entry points: {', '.join(entries) or '(none obvious)'}\n"
               f"Files:\n{tree}")
        if len(out) > max_chars:  # context budget — the map is a MAP
            out = (out[:max_chars]
                   + f"\n... (truncated at {max_chars} chars — "
                     f"{len(rows)} files total; use search_repo to target)")
        return out

    # ---------- search_repo ----------

    def search_repo(repo: str, pattern: str, max_hits: int = 40) -> str:
        try:
            root = _resolve_repo(repo)
        except ValueError as e:
            return f"ERROR: {e}"
        if not root.is_dir():
            return f"ERROR: no synced repo '{repo}'. repo_sync it first."
        # ripgrep when the box has it; a plain Python scan when not.
        if shutil.which("rg"):
            r = subprocess.run(
                ["rg", "-n", "--no-heading", "-m", str(max_hits), pattern],
                cwd=str(root), capture_output=True, text=True, timeout=120)
            # ripgrep uses exit 1 for a valid search with no matches, but
            # exit 2 for malformed regexes and other search failures.  The
            # latter used to be mistaken for an empty result whenever rg was
            # installed, even though the Python fallback reported it loudly.
            if r.returncode not in (0, 1):
                detail = r.stderr.strip() or f"ripgrep exit {r.returncode}"
                return f"ERROR: search failed: {detail[:300]}"
            hits = r.stdout.strip().splitlines()[:max_hits]
        else:
            try:
                rx = re.compile(pattern)
            except re.error as e:
                return f"ERROR: bad pattern: {e}"
            hits = []
            for p in sorted(root.rglob("*")):
                if any(part in _SKIP_DIRS for part in p.parts) \
                        or not p.is_file() or p.suffix.lower() in _BINARY_EXT:
                    continue
                rel = p.relative_to(root).as_posix()
                try:
                    for i, line in enumerate(
                            open(p, encoding="utf-8", errors="replace"), 1):
                        if rx.search(line):
                            hits.append(f"{rel}:{i}:{line.rstrip()[:160]}")
                            if len(hits) >= max_hits:
                                break
                except OSError:
                    continue
                if len(hits) >= max_hits:
                    break
        if not hits:
            return f"No matches for /{pattern}/ in {root.name}."
        return (f"{root.name} @ {_head(root)} — matches (file:line):\n"
                + "\n".join(hits))

    # ---------- registration (all external_read: cloned code is DATA) ----

    registry.register(
        "repo_sync",
        "Shallow-clone (or pull) a git repo into your read-only workspace so "
        "you can review and advise on it. Flow is ALWAYS: repo_sync -> "
        "repo_map -> targeted read_file calls driven by the question. You "
        "have no way to write to, commit to, or push a repo — reviews and "
        "advice only; patches are Jack's to apply.",
        {"type": "object", "properties": {
            "url_or_path": {"type": "string",
                            "description": "Repo URL or a local path"},
            "branch": {"type": "string", "description": "Optional branch"}},
         "required": ["url_or_path"]},
        repo_sync, kind="external_read",
    )
    registry.register(
        "repo_map",
        "Structure summary of a synced repo: file tree with line counts "
        "(build noise filtered), language breakdown, entry points, HEAD "
        "commit. Capped — it's a map, not the code; follow with TARGETED "
        "read_file/search_repo calls, never bulk reads.",
        {"type": "object", "properties": {
            "repo": {"type": "string", "description": "Workspace repo name"}},
         "required": ["repo"]},
        repo_map, kind="external_read",
    )
    registry.register(
        "search_repo",
        "Regex search across a synced repo (file:line results, capped). The "
        "right tool between the map and a full file read.",
        {"type": "object", "properties": {
            "repo": {"type": "string"},
            "pattern": {"type": "string", "description": "Regular expression"}},
         "required": ["repo", "pattern"]},
        search_repo, kind="external_read",
    )

r"""
merge_projects tool (FRIDAY_notes10_plan.md Phase 3, §3). Cluster C: "there are
still 3 projects related to X, please make it only one" — and FRIDAY created a
FOURTH. The missing capability was a deterministic MERGE: move duplicate folders'
files into the survivor, fold the notes together, mark the duplicates merged.
The code does the surgery; the model only orchestrates (list -> confirm -> merge).

Pure logic (no model): drive the registered tool and assert the surgery — files
moved under ONE batch confirm, note content folded, duplicates re-statused, and
a declined confirm leaves everything untouched.
"""

import pytest

from helpers.harness import SandboxFriday


def _call(sandbox, name, args=None):
    return sandbox.service.engine.registry.call(name, args or {})


def _plant(sandbox, slug, files=None, with_folder=True, status="active", title=None):
    """Plant a project note and (optionally) a folder with files under the
    sandbox projects root (a project-zone folder, so moves confirm)."""
    title = title or slug.replace("_", " ").title()
    folder_line = ""
    if with_folder:
        folder = sandbox.root / "Projects" / slug
        folder.mkdir(parents=True, exist_ok=True)
        for fn, content in (files or {}).items():
            (folder / fn).write_text(content, encoding="utf-8")
        folder_line = f"- **Folder:** {folder}\n"
    sandbox.brain.write_note(
        f"projects/{slug}.md",
        f"# {title}\n\n- **Status:** {status}\n{folder_line}\nBody of {slug}.\n",
        mode="create", summary=f"plant {slug}")
    return sandbox.root / "Projects" / slug


@pytest.mark.upgrade
@pytest.mark.case("MERGE-001", "merge folds duplicates into the survivor: files "
                              "moved, notes folded + re-statused, ONE batch confirm")
def test_full_merge(sandbox):
    _plant(sandbox, "orbit_sync", files={"main.txt": "survivor"})
    _plant(sandbox, "orbit_sync_rig", files={"rig.txt": "rig data"})
    _plant(sandbox, "orbit_sync_alt", files={"alt.txt": "alt data"})
    out = _call(sandbox, "merge_projects",
                {"target": "Orbit Sync",
                 "duplicates": ["Orbit Sync Rig", "Orbit Sync Alt"]})
    assert "Merged 2 project(s)" in out, out
    target = sandbox.root / "Projects" / "orbit_sync"
    # Files from both duplicates now live in the survivor folder.
    assert (target / "rig.txt").is_file() and (target / "alt.txt").is_file()
    assert (target / "main.txt").is_file()  # survivor's own file untouched
    # And they left the duplicate folders.
    assert not (sandbox.root / "Projects" / "orbit_sync_rig" / "rig.txt").exists()
    # Note content folded into the survivor note.
    tnote = sandbox.note("projects/orbit_sync.md")
    assert "## Merged from Orbit Sync Rig" in tnote
    assert "## Merged from Orbit Sync Alt" in tnote
    # Duplicates re-statused (their content lives in the survivor now).
    assert "merged into Orbit Sync" in sandbox.note("projects/orbit_sync_rig.md")
    assert "merged into Orbit Sync" in sandbox.note("projects/orbit_sync_alt.md")
    # Exactly ONE confirm covered the whole batch of moves.
    assert len(sandbox.rec.confirms) == 1, sandbox.rec.confirms


@pytest.mark.upgrade
@pytest.mark.case("MERGE-002", "a declined confirm leaves everything untouched — "
                              "no files moved, no note surgery")
def test_declined_is_atomic(tmp_path):
    sb = SandboxFriday(tmp_path, confirm_reply=False)  # Jack says NO
    _plant(sb, "orbit_sync", files={"main.txt": "survivor"})
    _plant(sb, "orbit_sync_rig", files={"rig.txt": "rig data"})
    out = _call(sb, "merge_projects",
                {"target": "Orbit Sync", "duplicates": ["Orbit Sync Rig"]})
    assert "ERROR" in out or "declined" in out.lower(), out
    # Nothing moved; nothing folded; nothing re-statused.
    assert (sb.root / "Projects" / "orbit_sync_rig" / "rig.txt").is_file()
    assert not (sb.root / "Projects" / "orbit_sync" / "rig.txt").exists()
    assert "Merged from" not in sb.note("projects/orbit_sync.md")
    assert "merged into" not in sb.note("projects/orbit_sync_rig.md")


@pytest.mark.upgrade
@pytest.mark.case("MERGE-003", "self-merge and unknown-name are refused, not guessed")
def test_bad_targets_refused(sandbox):
    _plant(sandbox, "orbit_sync", files={"main.txt": "x"})
    same = _call(sandbox, "merge_projects",
                 {"target": "Orbit Sync", "duplicates": ["Orbit Sync"]})
    assert "itself" in same.lower() or "nothing to merge" in same.lower(), same
    missing = _call(sandbox, "merge_projects",
                    {"target": "Orbit Sync", "duplicates": ["Nonexistent Widget"]})
    assert "no project matches" in missing.lower(), missing
    # Nothing changed on the refusals.
    assert len(sandbox.rec.confirms) == 0


@pytest.mark.upgrade
@pytest.mark.case("MERGE-004", "a note-only duplicate (no folder) folds + re-statuses "
                              "with zero file moves and zero confirms")
def test_note_only_duplicate(sandbox):
    _plant(sandbox, "orbit_sync", with_folder=False)
    _plant(sandbox, "orbit_sync_notes", with_folder=False)
    out = _call(sandbox, "merge_projects",
                {"target": "Orbit Sync", "duplicates": ["Orbit Sync Notes"]})
    assert "Merged 1 project(s)" in out
    assert "## Merged from Orbit Sync Notes" in sandbox.note("projects/orbit_sync.md")
    assert "merged into Orbit Sync" in sandbox.note("projects/orbit_sync_notes.md")
    assert len(sandbox.rec.confirms) == 0  # no files => no move confirm


@pytest.mark.upgrade
@pytest.mark.case("MERGE-005", "a survivor with no folder gets one created and "
                              "recorded on its note when files must move in")
def test_target_folder_created(sandbox):
    _plant(sandbox, "orbit_sync", with_folder=False)
    _plant(sandbox, "orbit_sync_rig", files={"rig.txt": "rig data"})
    out = _call(sandbox, "merge_projects",
                {"target": "Orbit Sync", "duplicates": ["Orbit Sync Rig"]})
    target = sandbox.root / "Projects" / "orbit_sync"
    assert (target / "rig.txt").is_file(), out
    assert f"- **Folder:** {target}" in sandbox.note("projects/orbit_sync.md")


@pytest.mark.upgrade
@pytest.mark.case("MERGE-006", "colliding filenames across duplicates keep BOTH "
                              "files (no silent overwrite)")
def test_collision_keeps_both(sandbox):
    _plant(sandbox, "orbit_sync", files={"notes.txt": "survivor notes"})
    _plant(sandbox, "orbit_sync_rig", files={"notes.txt": "rig notes"})
    _call(sandbox, "merge_projects",
          {"target": "Orbit Sync", "duplicates": ["Orbit Sync Rig"]})
    target = sandbox.root / "Projects" / "orbit_sync"
    files = sorted(p.name for p in target.iterdir() if p.is_file())
    # Original survives, the colliding incoming file lands under a suffixed name.
    assert "notes.txt" in files
    assert any(f != "notes.txt" and f.startswith("notes") for f in files), files


@pytest.mark.upgrade
@pytest.mark.case("MERGE-007", "merge_projects is an ACTION tool (confirms while "
                              "tainted; not a free internal call)")
def test_registered_action(sandbox):
    assert sandbox.service.engine.registry.kind("merge_projects") == "action"

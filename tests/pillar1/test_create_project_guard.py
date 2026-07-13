r"""
Near-duplicate guard in create_project (FRIDAY_notes10_plan.md Phase 3, §4).
Cluster C: asked to reduce three near-identical projects to one, FRIDAY created a
FOURTH. `create_project` now checks the resolver before scaffolding — a genuinely
new slug that strongly matches an EXISTING project is refused with the match
surfaced, so the model asks Jack instead of spawning a sibling. It stays
overridable (confirm_new=true) and never blocks the supported "give an existing
project a folder" use.

Pure logic (no model): drive the registered tool and assert the guard fires on a
near-duplicate, yields to confirm_new, and lets exact/distinct names through.
"""

import pytest


def _call(sandbox, name, args):
    return sandbox.service.engine.registry.call(name, args)


def _plant(sandbox, slug, with_folder=False):
    title = slug.replace("_", " ").title()
    sandbox.brain.write_note(
        f"projects/{slug}.md",
        f"# {title}\n\n- **Status:** active\n\nBody of {slug}.\n",
        mode="create", summary=f"plant {slug}")


@pytest.mark.upgrade
@pytest.mark.case("GUARD-001", "creating a near-duplicate of an existing project "
                              "is refused — the match is surfaced, nothing scaffolded")
def test_near_duplicate_blocked(sandbox):
    _plant(sandbox, "orbit_sync")
    out = _call(sandbox, "create_project", {"name": "Orbit Sync Rig"})
    assert "similar project" in out.lower(), out
    assert "Orbit Sync" in out and "confirm_new" in out
    # Nothing was created.
    assert "projects/orbit_sync_rig.md" not in sandbox.brain.list_notes()
    assert not (sandbox.root / "Projects" / "orbit_sync_rig").exists()
    assert len(sandbox.rec.confirms) == 0  # never reached the scaffold confirm


@pytest.mark.upgrade
@pytest.mark.case("GUARD-002", "confirm_new=true overrides the guard and creates "
                              "the genuinely-new project")
def test_confirm_new_overrides(sandbox):
    _plant(sandbox, "orbit_sync")
    out = _call(sandbox, "create_project",
                {"name": "Orbit Sync Rig", "confirm_new": True})
    assert "similar project" not in out.lower(), out
    assert "projects/orbit_sync_rig.md" in sandbox.brain.list_notes()
    assert (sandbox.root / "Projects" / "orbit_sync_rig").is_dir()


@pytest.mark.upgrade
@pytest.mark.case("GUARD-003", "re-running create on the SAME existing project "
                              "(exact slug) is allowed — gives it a folder")
def test_exact_existing_not_blocked(sandbox):
    _plant(sandbox, "orbit_sync")  # note only, no folder yet
    out = _call(sandbox, "create_project", {"name": "Orbit Sync"})
    assert "similar project" not in out.lower(), out
    # It scaffolded the folder for the existing project.
    assert (sandbox.root / "Projects" / "orbit_sync").is_dir()
    assert "Folder" in out or "folder" in out


@pytest.mark.upgrade
@pytest.mark.case("GUARD-004", "a genuinely distinct name is created normally "
                              "(the guard doesn't over-fire)")
def test_distinct_name_created(sandbox):
    _plant(sandbox, "orbit_sync")
    out = _call(sandbox, "create_project", {"name": "Wombat Launcher"})
    assert "similar project" not in out.lower(), out
    assert "projects/wombat_launcher.md" in sandbox.brain.list_notes()

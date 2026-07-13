r"""
list_projects tool (FRIDAY_notes10_plan.md Phase 3, §2). Cluster C: asked to
reduce N claude-code projects to one, the model created a FOURTH — it had no
deterministic way to SEE the N projects that exist, so it reached for the only
project tool it had (create). This tool is that missing surface: a plain,
code-generated inventory (name, status, folder, note) the model reads first.

Pure logic (no model): call the registered tool through the registry and assert
the inventory reflects the real projects/ notes and folders.
"""

import pytest


def _call(sandbox, name, args=None):
    return sandbox.service.engine.registry.call(name, args or {})


@pytest.mark.upgrade
@pytest.mark.case("LIST-001", "list_projects surfaces every seeded project with "
                             "its real status")
def test_lists_seeded_projects(sandbox):
    out = _call(sandbox, "list_projects")
    # The harness seeds these four (SEED_PROJECTS) at known statuses.
    assert "Alpha Rig" in out and "status: active" in out
    assert "Beta Probe" in out and "reference" in out
    assert "Gamma Arm" in out and "side-interest" in out
    assert "Delta Sled" in out  # untagged status defaults to active


@pytest.mark.upgrade
@pytest.mark.case("LIST-002", "a newly written project note appears immediately "
                             "(deterministic re-scan, no stale cache)")
def test_new_project_appears(sandbox):
    sandbox.brain.write_note(
        "projects/marlin_rig.md",
        "# Marlin Rig\n\n- **Status:** paused\n\nBench.\n",
        mode="create", summary="plant marlin")
    out = _call(sandbox, "list_projects")
    assert "Marlin Rig" in out and "status: paused" in out


@pytest.mark.upgrade
@pytest.mark.case("LIST-003", "a recorded off-disk folder and an orphan folder "
                             "both show honestly")
def test_folder_reporting(sandbox, tmp_path):
    real = tmp_path / "elsewhere" / "marlin"
    real.mkdir(parents=True)
    sandbox.brain.write_note(
        "projects/marlin_rig.md",
        f"# Marlin Rig\n\n- **Status:** active\n- **Folder:** {real}\n\nBench.\n",
        mode="create", summary="plant marlin")
    # An orphan folder under the projects root with no note.
    (sandbox.root / "Projects" / "zephyr_probe").mkdir(parents=True)
    out = _call(sandbox, "list_projects")
    assert str(real) in out                       # recorded, on disk
    assert "Zephyr Probe" in out or "zephyr_probe" in out  # orphan folder listed
    assert "no note" in out                        # the orphan has no note


@pytest.mark.upgrade
@pytest.mark.case("LIST-004", "list_projects is registered as a read-only "
                             "(internal) tool — it can't taint a turn")
def test_registered_internal(sandbox):
    assert sandbox.service.engine.registry.kind("list_projects") == "internal"

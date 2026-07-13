r"""
Deterministic project/entity resolver (FRIDAY_notes10_plan.md Phase 3, §1 — the
JARVIS layer). Transcript B: Jack said "the doc ock project" and the 14B GUESSED
a path (`C:\Users\jacko\projects\doc_ock`) instead of reading the folder recorded
in the project note. Transcript C: asked to merge "3 claude code projects" it
couldn't even reliably identify which projects Jack meant. Both are the model
being left to match free text against known projects in its head.

Pure logic (no model): assert ProjectResolver matches a free-text name against
the real projects — resolving a confident single match to its note+folder,
asking which on genuine ambiguity, and staying SILENT on anything weak so a bare
question (and the golden suite) sees no injected hint. These tests ARE the lock:
resolution is deterministic, so the arithmetic is provable without the 14B.
"""

import pytest

from core.project_resolver import ProjectResolver, STRONG


def _resolver(sandbox):
    """Production-shaped resolver over the sandbox brain (same construction as
    register_project_tools)."""
    return ProjectResolver(sandbox.brain, sandbox.root / "Projects")


def _plant(sandbox, slug, title=None, folder=None, status="active", body="Bench."):
    """Write a projects/<slug>.md note the way create_project would."""
    title = title or slug.replace("_", " ").title()
    lines = [f"# {title}", "", f"- **Status:** {status}"]
    if folder is not None:
        lines.append(f"- **Folder:** {folder}")
    lines += ["", body, ""]
    sandbox.brain.write_note(f"projects/{slug}.md", "\n".join(lines), mode="create",
                             summary=f"plant {slug}")


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-001", "a free-text project reference resolves to a "
                                "single confident match (note + status)")
def test_single_match_resolves(sandbox):
    _plant(sandbox, "marlin_rig")
    outcome, data = _resolver(sandbox).resolve_one(
        "look at the files in the marlin rig project")
    assert outcome == "one", (outcome, data)
    assert data["note_path"] == "projects/marlin_rig.md"
    assert data["status"] == "active"


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-002", "folder_for returns the note's RECORDED folder "
                                "(off the default root), never a guessed path")
def test_folder_for_uses_recorded_folder(sandbox, tmp_path):
    real = tmp_path / "somewhere_else" / "marlin"
    real.mkdir(parents=True)
    (real / "Ock Sketches v1.pdf").write_text("x", encoding="utf-8")
    _plant(sandbox, "marlin_rig", folder=str(real))
    got = _resolver(sandbox).folder_for("marlin rig")
    assert got == real, got  # the recorded path, NOT Projects/marlin_rig


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-003", "separator/spacing differences don't matter — "
                                "'doc ock' resolves the doc_ock slug")
def test_normalized_match(sandbox):
    _plant(sandbox, "doc_ock", title="Doc Ock")
    outcome, data = _resolver(sandbox).resolve_one("open the doc ock project please")
    assert outcome == "one"
    assert data["slug"] == "doc_ock"


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-004", "two near-duplicate projects are AMBIGUOUS — the "
                                "resolver asks which (the JARVIS confirm), never guesses")
def test_ambiguous_asks_which(sandbox):
    _plant(sandbox, "orbit_sync")
    _plant(sandbox, "orbit_sync_rig")
    r = _resolver(sandbox)
    outcome, data = r.resolve_one("update the orbit sync project")
    assert outcome == "many", (outcome, [d.get("slug") for d in data])
    slugs = {d["slug"] for d in data}
    assert {"orbit_sync", "orbit_sync_rig"} <= slugs
    # And the engine hint tells her to ask, not to act.
    hint = r.hint_for("update the orbit sync project")
    assert "ask" in hint.lower() and "which" in hint.lower()


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-005", "an unrelated message injects NO hint — bare "
                                "questions and the golden suite are unchanged")
def test_no_match_is_silent(sandbox):
    _plant(sandbox, "marlin_rig")
    r = _resolver(sandbox)
    # A generic question that merely shares the common word 'rig' must NOT
    # strongly resolve (rig is treated as generic, so the distinctive half of a
    # name still has to match).
    assert r.hint_for("how do I calibrate the rig bench?") == ""
    assert r.hint_for("what's the date today?") == ""
    outcome, _ = r.resolve_one("what's the date today?")
    assert outcome == "none"


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-006", "a typo'd name still resolves (difflib window "
                                "ratio clears the strong threshold)")
def test_typo_tolerance(sandbox):
    _plant(sandbox, "marlin_rig")
    r = _resolver(sandbox)
    cands = r.resolve("look at the marln rig project")  # 'marln' typo
    assert cands and cands[0]["slug"] == "marlin_rig"
    assert cands[0]["score"] >= STRONG, cands[0]["score"]


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-007", "the single-match hint carries the real note + "
                                "folder so the model proceeds instead of guessing")
def test_hint_carries_note_and_folder(sandbox, tmp_path):
    folder = tmp_path / "rigs" / "marlin"
    folder.mkdir(parents=True)
    _plant(sandbox, "marlin_rig", folder=str(folder))
    hint = _resolver(sandbox).hint_for("review the marlin rig project files")
    assert "projects/marlin_rig.md" in hint
    assert str(folder) in hint
    assert "do not guess" in hint.lower()


@pytest.mark.upgrade
@pytest.mark.case("RESOLVE-008", "an orphan folder under the projects root (no "
                                "note) is still a resolvable project")
def test_orphan_folder_resolves(sandbox):
    (sandbox.root / "Projects" / "zephyr_probe").mkdir(parents=True)
    outcome, data = _resolver(sandbox).resolve_one("the zephyr probe project")
    assert outcome == "one"
    assert data["slug"] == "zephyr_probe"
    assert data["note_path"] is None and data["folder_exists"] is True

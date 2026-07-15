r"""
CONSOLIDATE-leg guards (armor plan §6, Phase CONSOLIDATE): code-only, no model.

MRG-001  hint_for's merge-intent operand branch (CN.1): on a merge ask with
         2+ plausible project matches, the injected hint lists ALL candidates
         as merge operands — never ask-which (the live F-transcript's friendly
         fire) and never the single-best steer (CN.0 batch 1's partial merge).
         Non-merge turns keep the pre-CN hints byte-identical.
MRG-005  write_brain phantom-project guard (CN.1b): CREATING a projects/ note
         via write_brain is refused with a corrective — create_project is the
         one door with the near-duplicate check. Found by GT-C9 capture batch
         1: the memory pass write_brain'd Jack's consolidation TASK into
         projects/ as a fourth project, and every later turn surfaced it as
         real. Edits to existing project notes and other folders stay free.

(MRG-002/003/004 arrive with CN.2/CN.3/CN.4.)
"""

import pytest

from core.project_resolver import merge_intent


def _call(sandbox, name, args=None):
    return sandbox.service.engine.registry.call(name, args or {})


def _plant_note(sandbox, slug, title=None):
    """A project note via the brain API directly — the legitimate code path
    (create_project / test fixtures), deliberately NOT the guarded tool."""
    title = title or slug.replace("_", " ").title()
    sandbox.brain.write_note(
        f"projects/{slug}.md",
        f"# {title}\n\n- **Status:** active\n\nFlux beam tooling.\n",
        mode="create", summary=f"plant {slug}")


FLUX_SLUGS = ("fluxbeam", "flux_beam_tool", "flux_beam_v2")


@pytest.mark.upgrade
@pytest.mark.case("MRG-001", "merge-intent turns get an OPERAND hint listing "
                             "every plausible candidate; non-merge turns keep "
                             "the pre-CN hints")
def test_mrg001_operand_hint(sandbox):
    for slug in FLUX_SLUGS:
        _plant_note(sandbox, slug)
    res = sandbox.service.engine.project_resolver

    # The GT-C9 T1 shape: fuzzy filter + merge verb. ALL THREE must be listed
    # as operands — including the two that score below STRONG (the "one"-steer
    # hole CN.0 batch 1 measured as a partial merge).
    hint = res.hint_for(
        "Please consolidate all the projects with flux in the name.")
    assert "merge CANDIDATES" in hint, hint
    for slug in FLUX_SLUGS:
        assert slug in hint, f"{slug} missing from operand hint: {hint}"
    assert "merge_projects" in hint
    assert "ask jack" not in hint.lower(), hint  # the friendly-fire text

    # The GT-C10 T1 shape: both exact titles pasted + merge verb -> operands,
    # not ask-which.
    hint = res.hint_for(
        "Please merge 'Flux Beam Tool' and 'Flux Beam V2' into one.")
    assert "merge CANDIDATES" in hint, hint
    assert "flux_beam_tool" in hint and "flux_beam_v2" in hint, hint

    # REGRESSION — non-merge ambiguity keeps the ask-which hint.
    hint = res.hint_for("Tell me about 'Flux Beam Tool' and 'Flux Beam V2'.")
    assert "ASK Jack" in hint, hint
    assert "merge CANDIDATES" not in hint, hint

    # REGRESSION — non-merge single strong match keeps the use-directly hint.
    hint = res.hint_for("What's the status of the fluxbeam project?")
    assert "DIRECTLY" in hint, hint
    assert "merge CANDIDATES" not in hint, hint

    # Merge verb over projects that DON'T exist -> silent, exactly as before
    # (the operand branch needs 2+ plausible matches to engage at all).
    assert res.hint_for("Merge the quarterly budget spreadsheets please.") == ""


@pytest.mark.upgrade
@pytest.mark.case("MRG-001b", "merge_intent vocabulary fires on the live "
                              "transcript's phrasings and stays quiet on "
                              "ordinary project chat")
def test_mrg001b_merge_intent_vocabulary():
    fires = [
        "Please consolidate all the projects with flux in the name.",
        "Yes please, merge all of the similar projects into one.",
        "There are 3 orbit sync projects. Please make it only one.",
        "Can you combine these two projects?",
        "De-dup the project list please.",
        "Fold them together under one project.",
    ]
    # The generic continuation ("update the project folder") must stay QUIET:
    # carrying intent across such turns is CN.2's pending ledger, not a
    # re-fire of the vocabulary — a fire here would inject operand hints on
    # every mundane folder request.
    quiet = [
        "What's the status of the fluxbeam project?",
        "Ok, please update the project folder.",
        "How's it looking?",
        "Read the flux note and summarise it for me.",
    ]
    for msg in fires:
        assert merge_intent(msg), f"should fire: {msg}"
    for msg in quiet:
        assert not merge_intent(msg), f"should stay quiet: {msg}"


@pytest.mark.upgrade
@pytest.mark.case("MRG-005", "write_brain refuses to CREATE a projects/ note "
                             "(the phantom-project channel); existing-note "
                             "edits and other folders unaffected")
def test_mrg005_write_brain_projects_guard(sandbox):
    _plant_note(sandbox, "fluxbeam")

    # The captured failure verbatim: the memory pass saving Jack's TASK as a
    # brand-new projects/ note. Refused, nothing on disk, ERROR prefix keeps
    # it out of the durable-write ledger (TM.1).
    out = _call(sandbox, "write_brain", {
        "path": "projects/consolidate_flux_projects.md",
        "content": "# Consolidate flux projects\n\nJack asked to merge them.\n",
        "summary": "task note"})
    assert out.startswith("ERROR"), out
    assert "create_project" in out, out
    assert not (sandbox.brain.root / "projects/consolidate_flux_projects.md").exists()

    # A backslash path can't dodge the prefix check.
    out = _call(sandbox, "write_brain", {
        "path": "projects\\sneaky_new.md", "content": "# Sneak\n"})
    assert out.startswith("ERROR"), out
    assert not (sandbox.brain.root / "projects/sneaky_new.md").exists()

    # Editing an EXISTING project note stays free — merge surgery and status
    # updates need it.
    out = _call(sandbox, "write_brain", {
        "path": "projects/fluxbeam.md",
        "content": "\n## Update\n\nMore detail from today.\n",
        "mode": "append", "summary": "append detail"})
    assert not out.startswith("ERROR"), out
    assert "## Update" in sandbox.brain.read_note("projects/fluxbeam.md")

    # Non-projects/ writes untouched — the redirect the corrective names.
    out = _call(sandbox, "write_brain", {
        "path": "inbox/consolidation_task.md",
        "content": "# Task\n\nMerge the flux projects.\n",
        "summary": "task"})
    assert not out.startswith("ERROR"), out

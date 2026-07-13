r"""
Result-based referents from file-surfacing tools (FRIDAY_notes10_plan.md
Phase 2, §3). Transcript B: FRIDAY listed a project folder, then one turn later
"forgot" the pdf she had just offered to review and asked Jack to hand over the
file. The fix: a list_dir result must push its FILES onto the working-memory
referent stack (with real absolute paths), so "the pdf" / "the second one"
resolves against the listing instead of the model guessing a path.

Pure logic (no model): assert _track_result_referents parses a list_dir result
into file referents with joined paths (subfolders and the truncation tail
excluded, capped), and that the calendar path it shares still works after the
signature change.
"""

import pytest

from core.engine import Engine


def _e():
    e = Engine.__new__(Engine)
    e.referents = []
    return e


# The exact format core/tools/filesystem.py:list_dir emits.
_LISTING = (
    "specs\\\n"
    "drawings\\\n"
    "Ock Sketches v1.pdf  (2,481,204 bytes)\n"
    "wiring.txt  (1,204 bytes)\n"
    "notes.md  (512 bytes)\n"
    "... (+3 more entries)"
)


@pytest.mark.upgrade
@pytest.mark.case("REF-001", "list_dir files land on the referent stack with "
                            "joined absolute paths; folders/tail excluded")
def test_list_dir_pushes_files():
    e = _e()
    e._track_result_referents("list_dir", {"path": r"C:\Users\jacko\rigs\alpha"},
                              _LISTING)
    names = [r["name"] for r in e.referents]
    kinds = {r["kind"] for r in e.referents}
    assert kinds == {"file"}, kinds
    assert "Ock Sketches v1.pdf" in names
    assert "wiring.txt" in names
    assert "notes.md" in names
    # Subfolders are NOT files ("the pdf" is never a folder).
    assert "specs" not in names and "drawings" not in names
    # The truncation tail must never become a referent.
    assert not any("more entries" in n for n in names)
    # The path is the parent joined to the name — a real, readable path.
    pdf = next(r for r in e.referents if r["name"].endswith(".pdf"))
    assert pdf["detail"] == r"C:\Users\jacko\rigs\alpha\Ock Sketches v1.pdf"


@pytest.mark.upgrade
@pytest.mark.case("REF-002", "a bare affirmative later resolves 'the pdf' — the "
                            "listed file is on the stack as an artifact referent")
def test_listed_file_is_artifact_referent():
    e = _e()
    e._track_result_referents("list_dir", {"path": r"C:\rigs\alpha"}, _LISTING)
    # The stack now has a reviewable artifact, so an artifact-ask no longer
    # trips the empty-ledger honesty guard for a folder Jack really did surface.
    assert e._has_artifact_referent() is True


@pytest.mark.upgrade
@pytest.mark.case("REF-003", "a huge listing is capped so it can't evict the "
                            "rest of the 12-slot stack")
def test_listing_capped():
    e = _e()
    big = "\n".join(f"file{i}.txt  ({i} bytes)" for i in range(50))
    e._track_result_referents("list_dir", {"path": r"C:\x"}, big)
    assert len(e.referents) <= 8


@pytest.mark.upgrade
@pytest.mark.case("REF-004", "the shared calendar path still works after the "
                            "signature change (regression guard)")
def test_calendar_still_tracked():
    e = _e()
    cal = ("Mon Jul 13, 10:00 AM  Alpha rig planning review @ Lab 2\n"
           "Tue Jul 14, 2:00 PM  Load cell vendor call")
    e._track_result_referents("read_calendar", {"days": 14}, cal)
    kinds = {r["kind"] for r in e.referents}
    names = [r["name"] for r in e.referents]
    assert kinds == {"event"}, kinds
    assert "Alpha rig planning review" in names
    assert "Load cell vendor call" in names


@pytest.mark.upgrade
@pytest.mark.case("REF-005", "an empty folder / not-connected result pushes "
                            "nothing (no spurious referents)")
def test_empty_results_noop():
    e = _e()
    e._track_result_referents("list_dir", {"path": r"C:\x"}, "(empty folder)")
    e._track_result_referents("read_calendar", {"days": 14},
                              "No events in the next 14 days.")
    assert e.referents == []

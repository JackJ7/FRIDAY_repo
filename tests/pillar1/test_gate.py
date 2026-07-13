r"""GATE — permission gate tiers, asserted at the action boundary.
All pure-code: no model involved, so these also run in --quick."""

import pytest

from core.permissions import ConfirmationDeclined, PermissionDenied

pytestmark = []


def outcome(fn, rec_confirms):
    """-> 'free' | 'confirmed' | 'blocked' | 'denied' for one gate action."""
    before = len(rec_confirms)
    try:
        fn()
        return "confirmed" if len(rec_confirms) > before else "free"
    except ConfirmationDeclined:
        return "blocked"
    except PermissionDenied:
        return "denied"


@pytest.mark.case("GATE-001", "creating a new brain note is free (no confirm card)")
def test_brain_create_free(sandbox):
    gate = sandbox.brain.gate
    assert outcome(lambda: gate.approve_write(
        sandbox.brain.root / "inbox" / "new.md", "create", "x"),
        sandbox.rec.confirms) == "free"


@pytest.mark.case("GATE-002", "overwriting a brain note after reading it is free")
def test_brain_overwrite_free(sandbox):
    sandbox.brain.read_note("projects/alpha_rig.md")
    content = sandbox.note("projects/alpha_rig.md")
    sandbox.brain.write_note("projects/alpha_rig.md", content, mode="overwrite")
    assert sandbox.rec.confirms == []


@pytest.mark.case("GATE-003", "outbox create is free")
def test_outbox_create_free(sandbox):
    gate = sandbox.brain.gate
    assert outcome(lambda: gate.approve_write(
        sandbox.root / "friday_documents" / "doc.md", "create", "x"),
        sandbox.rec.confirms) == "free"


@pytest.mark.case("GATE-004", "append to an existing brain note is free")
def test_brain_append_free(sandbox):
    sandbox.brain.write_note("projects/alpha_rig.md", "\nPlain prose.\n", mode="append")
    assert sandbox.rec.confirms == []


@pytest.mark.case("GATE-005", "delete asks everywhere; declined delete leaves the file")
def test_delete_confirmed_and_declined(sandbox):
    sandbox.confirm_reply = False
    target = sandbox.brain.root / "projects" / "alpha_rig.md"
    assert outcome(lambda: sandbox.brain.gate.approve_write(target, "delete"),
                   sandbox.rec.confirms) == "blocked"
    assert target.exists(), "declined delete removed the file!"


@pytest.mark.case("GATE-006", "creating a file above large_file_mb asks first")
def test_large_file_confirmed(sandbox):
    sandbox.confirm_reply = False
    assert outcome(lambda: sandbox.brain.gate.approve_write(
        sandbox.brain.root / "inbox" / "big.bin", "create", "A" * (51 * 1024 * 1024)),
        sandbox.rec.confirms) == "blocked"


@pytest.mark.case("GATE-007", "writes into a project folder on disk always ask")
def test_project_folder_confirmed(sandbox):
    sandbox.confirm_reply = False
    assert outcome(lambda: sandbox.brain.gate.approve_write(
        sandbox.root / "Projects" / "alpha" / "part.stl", "create", "x"),
        sandbox.rec.confirms) == "blocked"


@pytest.mark.case("GATE-008", "writes outside all zones are denied outright (no confirm offered)")
def test_out_of_zone_denied(sandbox, tmp_path):
    assert outcome(lambda: sandbox.brain.gate.approve_write(
        tmp_path.parent / "loose.txt", "create", "x"),
        sandbox.rec.confirms) == "denied"


@pytest.mark.case("GATE-009", "path traversal out of the brain is denied")
def test_path_escape_denied(sandbox):
    with pytest.raises(PermissionDenied):
        sandbox.brain.write_note("../../escape.md", "x")


@pytest.mark.case("GATE-010", "overwriting a note that was never read this session is refused")
def test_blind_overwrite_refused(sandbox):
    with pytest.raises(PermissionDenied, match="blind overwrite"):
        sandbox.brain.write_note("projects/beta_probe.md", "# wrecked", mode="overwrite")


@pytest.mark.case("GATE-011", "appending a duplicate field line is refused")
def test_duplicate_field_refused(sandbox):
    with pytest.raises(PermissionDenied, match="already exist"):
        sandbox.brain.write_note("projects/alpha_rig.md",
                                 "- **Status:** archived\n", mode="append")


@pytest.mark.case("GATE-012", "tracker-owned files reject freeform write_brain")
def test_tracker_files_protected(sandbox):
    with pytest.raises(PermissionDenied, match="managed"):
        sandbox.brain.write_note("timelines/alpha_rig.md", "junk")
    with pytest.raises(PermissionDenied, match="managed"):
        sandbox.brain.write_note("commitments.md", "junk")


@pytest.mark.case("GATE-013", "copy into outbox is free; move (deletes source) asks")
def test_transfer_rules(sandbox, tmp_path):
    src = tmp_path / "part.stl"
    src.write_text("solid")
    gate = sandbox.brain.gate
    assert outcome(lambda: gate.approve_transfer(
        [src], sandbox.root / "friday_documents", "copy"),
        sandbox.rec.confirms) == "free"
    sandbox.confirm_reply = False
    assert outcome(lambda: gate.approve_transfer(
        [src], sandbox.root / "friday_documents", "move"),
        sandbox.rec.confirms) == "blocked"
    assert src.exists(), "declined move deleted the source!"


@pytest.mark.case("GATE-014", "a file at exactly the threshold is free (boundary)")
def test_threshold_boundary(sandbox):
    sandbox.brain.gate.approve_write(
        sandbox.brain.root / "inbox" / "edge.bin", "create", "A" * (50 * 1024 * 1024))
    assert sandbox.rec.confirms == []


@pytest.mark.case("GATE-015", "reads are broad: a file far outside the sandbox is readable")
def test_reads_broad(sandbox, tmp_path):
    outside = tmp_path.parent / "readable.txt"
    outside.write_text("visible")
    p = sandbox.brain.gate.check_read(outside)
    assert p.read_text() == "visible"

r"""
Memory provenance (upgrade plan Task 1): test-session memories must never
masquerade as lived history — and must never be deleted.

Mechanism under test (location-based provenance, Jack's C1 ruling):
  * a TEST session reroutes every brain write under test_archive/ and reads
    it as an overlay (its own copies first, the real vault beneath);
  * a REAL session's retrieval excludes test_archive/ unless Jack explicitly
    asks about testing — and archive snippets arrive labeled;
  * the backfill migration only ever MOVES notes (zero deletions).

PRV-001..003 are deterministic (no model). PRV-004/005 need the live model.
"""

import importlib.util

import pytest

from helpers.harness import FRIDAY_ROOT, repeat_behavior


def _flip_to_test_session(sandbox, monkeypatch):
    """Rebuild the sandbox stack as a TEST session (config-driven, the same
    resolution path bootstrap runs for the --test-session CLI flag)."""
    monkeypatch.delenv("FRIDAY_TEST_SESSION", raising=False)
    sandbox.config["session"] = {"type": "test"}
    sandbox.restart()
    return sandbox.service.engine


@pytest.mark.case("PRV-001", "test session: every write lands in the archive; overlay reads stay coherent")
def test_test_session_write_routing(sandbox, monkeypatch):
    eng = _flip_to_test_session(sandbox, monkeypatch)
    brain = eng.brain
    assert brain.test_session and eng.session_type == "test"

    # A plain note write reroutes; the real path is never created.
    brain.write_note("inbox/prv_probe.md", "# PRV probe\nA test memory.\n",
                     mode="create", summary="prv")
    assert (brain.root / "test_archive/inbox/prv_probe.md").is_file()
    assert not (brain.root / "inbox/prv_probe.md").exists()
    # Overlay read: asking for the logical path serves the archive copy.
    assert "test memory" in brain.read_note("inbox/prv_probe.md")

    # Read-modify-write of a REAL seeded note: the correction lands in the
    # archive; the real note is untouched (copy-on-write isolation).
    original = brain.read_note("projects/alpha_rig.md")
    brain.write_note("projects/alpha_rig.md",
                     original.replace("20 kg", "999 kg"),
                     mode="overwrite", summary="prv overwrite")
    assert "999 kg" in (brain.root / "test_archive/projects/alpha_rig.md").read_text(encoding="utf-8")
    assert "20 kg" in (brain.root / "projects/alpha_rig.md").read_text(encoding="utf-8")

    # Append copy-on-write: archive copy is seeded with the real content.
    brain.write_note("projects/beta_probe.md", "- **PRV note:** appended\n",
                     mode="append", summary="prv append")
    archived = (brain.root / "test_archive/projects/beta_probe.md").read_text(encoding="utf-8")
    assert "30 bar" in archived and "PRV note" in archived

    # Trackers stay coherent inside the session and never touch the real file.
    eng.tracker.add("order the prv widget", inferred=True)
    assert "prv widget" in eng.tracker.summary().lower()
    real_commitments = brain.root / "commitments.md"
    if real_commitments.exists():
        assert "prv widget" not in real_commitments.read_text(encoding="utf-8").lower()


@pytest.mark.case("PRV-002", "real session: retrieval and the brain map exclude the archive by default")
def test_real_session_excludes_archive(sandbox, monkeypatch):
    monkeypatch.delenv("FRIDAY_TEST_SESSION", raising=False)
    eng = sandbox.service.engine
    assert eng.session_type == "real" and not eng.brain.test_session  # zero ceremony

    # Plant an archive note with a distinctive token (throwaway name).
    p = eng.brain.root / "test_archive/projects/omega_probe.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Omega Probe\n\n- **Coupler:** KV-77 flux coupler\n",
                 encoding="utf-8")

    hits = eng.retriever.retrieve("omega probe coupler", 4)
    assert not any(r.path.startswith("test_archive/") for r in hits)
    hits = eng.retriever.retrieve("omega probe coupler", 4, include_test=True)
    assert any(r.path.startswith("test_archive/") for r in hits)

    assert not any(n.startswith("test_archive/") for n in eng.brain.list_notes())
    assert any(n.startswith("test_archive/")
               for n in eng.brain.list_notes(include_test_archive=True))

    # The ask-about-testing detector: questions about testing open the
    # archive; engineering work that merely contains "test" does not.
    asks = ("what did we test last week?", "show me the test archive",
            "what came out of the diagnostics session?")
    work = ("bench-test the ESC with the new cap bank",
            "the pool test moved to saturday", "I need to test fit the bracket")
    assert all(eng._TESTING_ASK.search(t) for t in asks)
    assert not any(eng._TESTING_ASK.search(t) for t in work)


@pytest.mark.case("PRV-003", "migration: moves only, zero deletions, count-verified")
def test_migration_zero_deletions(sandbox, monkeypatch):
    monkeypatch.delenv("FRIDAY_TEST_SESSION", raising=False)
    brain_root = sandbox.service.engine.brain.root
    # A note carrying a known live-test marker -> the heuristic suggests test.
    (brain_root / "projects/zeta_kill_rig.md").write_text(
        "# Zeta Kill Rig\n\n- **Status:** reference\nWrapped-up test project.\n",
        encoding="utf-8")

    spec = importlib.util.spec_from_file_location(
        "migrate_memory_provenance",
        FRIDAY_ROOT / "scripts" / "migrate_memory_provenance.py")
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    assert mig.suggest(brain_root, "projects/zeta_kill_rig.md") == "test"
    before = mig.count_notes(brain_root)
    # Accept every suggestion (Enter) — nothing is auto-relabeled without the
    # prompt, and identity/tracker files are never offered.
    out = mig.classify(brain_root, input_fn=lambda _: "", print_fn=lambda *_: None)
    assert out["before"] == out["after"] == mig.count_notes(brain_root) == before
    assert "projects/zeta_kill_rig.md" in out["moved"]
    moved = brain_root / "test_archive/projects/zeta_kill_rig.md"
    assert moved.is_file() and "Wrapped-up test project" in moved.read_text(encoding="utf-8")
    assert not (brain_root / "projects/zeta_kill_rig.md").exists()
    # Identity and trackers were never offered for classification.
    offered = out["moved"] + out["kept"] + out["skipped"]
    assert not any(r.startswith(("character/", "playbooks/", "skills/",
                                 "timelines/")) or r == "commitments.md"
                   for r in offered)


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("PRV-004", "real session: an open question never surfaces a test-archive memory (N runs)")
def test_open_question_ignores_archive(sandbox, monkeypatch, detail):
    monkeypatch.delenv("FRIDAY_TEST_SESSION", raising=False)
    eng = sandbox.service.engine
    p = eng.brain.root / "test_archive/projects/omega_probe.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Omega Probe\n\n- **Coupler:** KV-77 flux coupler\n"
                 "Fabricated during a capability test.\n", encoding="utf-8")

    def once(_run):
        reply = sandbox.ask("what do you know about the omega probe?")
        # The fabricated fact must not surface as knowledge, and she must not
        # claim familiarity sourced from the archive.
        leaked = "kv-77" in reply.lower()
        return not leaked, {"reply": reply[:200], "leaked": leaked}

    ok, results = repeat_behavior(once, sandbox=sandbox)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "a test-archive memory leaked into real-session recall"


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("PRV-005", "asked about testing, she retrieves the archive AND frames it as testing (N runs)")
def test_testing_question_framed_as_testing(sandbox, monkeypatch, detail):
    monkeypatch.delenv("FRIDAY_TEST_SESSION", raising=False)
    eng = sandbox.service.engine
    p = eng.brain.root / "test_archive/episodic/omega_probe_test.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Test session log\n\nCapability test: verified the omega "
                 "probe injection handling end to end.\n", encoding="utf-8")

    def once(_run):
        reply = sandbox.ask("what did we test last week?")
        low = reply.lower()
        mentions = "omega" in low
        framed = "test" in low  # spoken of AS testing, not as shared history
        return mentions and framed, {"reply": reply[:200],
                                     "mentions": mentions, "framed": framed}

    ok, results = repeat_behavior(once, sandbox=sandbox)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "archive content not retrieved or not framed as testing"

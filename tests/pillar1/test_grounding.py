r"""
Conversational context & artifact grounding (upgrade plan Task 6) — the
"which schematics?" bug, decomposed and locked.

Deterministic (GND-001..004): perception, the ingest-implies-comprehend
structural guarantee, the referent stack, and the injected resolution rules.
Model (@upgrade, GND-010..): replays of the actual Doc Ock transcript shapes.
"""

from pathlib import Path

import pytest

from core.artifacts import comprehension_block, perceive
from helpers.harness import repeat_behavior


def _plant_file(sandbox, name: str, content: str) -> Path:
    """A readable source file inside the sandbox (gate-readable zone)."""
    p = sandbox.root / "incoming" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        p.write_bytes(content)
    else:
        p.write_text(content, encoding="utf-8")
    return p


@pytest.mark.case("GND-001", "perceive(): text extracted, binaries honestly UNREAD, scanned PDFs honestly UNREAD")
def test_perceive_kinds(tmp_path):
    t = tmp_path / "notes.md"
    t.write_text("# Wiring\n5V rail feeds the PCA9685.\n", encoding="utf-8")
    r = perceive(t)
    assert r["kind"] == "text" and "PCA9685" in r["text"]

    b = tmp_path / "firmware.bin"
    b.write_bytes(b"\x00\x01\x02" * 100)
    r = perceive(b)
    assert r["text"] is None and "UNREAD" in r["note"]

    # A PDF with no extractable text (blank page = the scanned-drawing case)
    # is honestly unread, never described.
    from pypdf import PdfWriter
    pdf = tmp_path / "sketch.pdf"
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    with open(pdf, "wb") as f:
        w.write(f)
    r = perceive(pdf)
    assert r["kind"] == "pdf" and r["text"] is None
    assert "UNREAD" in r["note"] and "can't see images" in r["note"]

    block = comprehension_block([r])
    assert "UNREAD" in block and "never invent" in block


@pytest.mark.case("GND-002", "filing carries the comprehension pass in the tool result (structural, not optional)")
def test_filing_includes_comprehension(sandbox):
    reg = sandbox.service.engine.registry
    reg.call("create_project", {"name": "Spool Winder",
                                "description": "throwaway grounding fixture"})
    src = _plant_file(sandbox, "drum_specs.md",
                      "# Drum\n- **Torque needed:** 1.2 N*m\nDrum drives the spool.\n")
    result = reg.call("add_files_to_project",
                      {"project": "Spool Winder", "files": [str(src)]})
    assert "COMPREHENSION PASS" in result, "filing without perceiving"
    assert "Torque needed" in result, "extracted content missing from filing result"

    # A binary files as honestly UNREAD — also in the same result.
    blob = _plant_file(sandbox, "gear_scan.bin", b"\x89BIN" + b"\x00" * 64)
    result = reg.call("add_files_to_project",
                      {"project": "Spool Winder", "files": [str(blob)]})
    assert "UNREAD" in result and "never invent" in result


@pytest.mark.case("GND-003", "referent stack: tool touches are recorded, salience-ordered, bounded")
def test_referent_stack(sandbox):
    eng = sandbox.service.engine
    assert eng.referents == []
    src = _plant_file(sandbox, "esc_notes.txt", "ESC 3 cut out at 9 A.\n")
    eng._run_tool("read_file", {"path": str(src)})
    assert [r["name"] for r in eng.referents] == ["esc_notes.txt"]

    eng._run_tool("read_brain", {"path": "projects/alpha_rig.md"})
    assert [r["name"] for r in eng.referents] == \
        ["alpha_rig.md", "esc_notes.txt"]

    # Re-touching moves an entity back to the front (fresh salience).
    eng._run_tool("read_file", {"path": str(src)})
    assert [r["name"] for r in eng.referents] == \
        ["esc_notes.txt", "alpha_rig.md"]

    # Failed calls record nothing.
    n = len(eng.referents)
    eng._run_tool("read_brain", {"path": "projects/does_not_exist.md"})
    assert len(eng.referents) == n

    # The injected block carries the list AND the resolution rules.
    block = eng._referent_block()
    assert "esc_notes.txt" in block and "do NOT ask which" in block
    # ...and is absent for a fresh conversation (golden suite unaffected).
    sandbox.fresh_conversation()
    assert eng._referent_block() == ""


@pytest.mark.case("GND-006", "calendar reads populate the referent stack as events; the artifact-kind split keeps the phantom barrier armed (Phase 1, Symptom 3)")
def test_calendar_referents(sandbox):
    from datetime import datetime, timedelta, timezone

    from helpers.harness import plant_events

    eng = sandbox.service.engine
    local = (datetime.now().astimezone() + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0)
    plant_events(sandbox, [{
        "id": "e1", "summary": "Widget sync",
        "start": {"dateTime": local.astimezone(timezone.utc)
                  .isoformat().replace("+00:00", "Z")}}])

    eng._run_tool("read_calendar", {"days": 2})
    # The event is on the working-memory stack, tagged 'event' with its date —
    # so "the exact date" can resolve against it (Symptom 3).
    ev = [r for r in eng.referents if r["kind"] == "event"]
    assert ev and "Widget sync" in ev[0]["name"], \
        [(r["kind"], r["name"]) for r in eng.referents]
    # ...but an event is NOT a reviewable artifact, so the phantom-review
    # barrier (fires only when NO artifact is present) stays armed.
    assert eng._has_artifact_referent() is False

    # A real file read flips the artifact-referent predicate.
    p = sandbox.root / "incoming" / "specs.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Specs\n- torque 1.2 N*m\n", encoding="utf-8")
    eng._run_tool("read_file", {"path": str(p)})
    assert eng._has_artifact_referent() is True


@pytest.mark.case("GND-007", "date-grounding self-check classifies a stated date as live vs clock-or-memory (Phase 1, item 6)")
def test_date_grounding_selfcheck(sandbox):
    eng = sandbox.service.engine
    # No date in the reply -> nothing to ground.
    assert eng._date_grounding("all good, nothing due", []) == "no-date"
    # A date stated with a live calendar/timeline read this turn -> grounded.
    assert eng._date_grounding(
        "The sync is Sat Jul 12.",
        [{"tool": "read_calendar", "args": {}}]) == "live:read_calendar"
    # A date stated with NO live read -> the confabulation-risk signature the
    # log must surface (it rode the injected clock table, or memory).
    assert eng._date_grounding(
        "The sync is on 2026-07-12.", [{"tool": "list_commitments"}]) \
        == "clock-or-memory"


@pytest.mark.case("GND-008", "calendar-first trigger: fires on an event when-question or an ungrounded event-date reply, never on a bare 'today' or when a live read ran (Phase 2, item 1)")
def test_calendar_first_trigger(sandbox):
    eng = sandbox.service.engine
    live = [{"tool": "read_calendar", "args": {}}]

    # An event when-question with NO live read this turn -> the barrier must run
    # the live calendar itself (the GT-A T1 case: "answered from memory").
    assert eng._needs_calendar_grounding(
        "What day is the Nimbus team sync set as?", "It's on Tuesday.", []) is True
    assert eng._needs_calendar_grounding(
        "What date do you have saved for the sync?", "July 12.", []) is True

    # ...but NOT once a live source already fired — a well-behaved turn is free.
    assert eng._needs_calendar_grounding(
        "What day is the sync set as?", "Sat Jul 12.", live) is False

    # A reply that VOLUNTEERS an event date with no live read -> ungrounded
    # claim, the Transcript-A confabulation shape; barrier corrects it.
    assert eng._needs_calendar_grounding(
        "remind me what's coming up", "The demo is on 2026-07-12.", []) is True

    # The clock's own territory stays untouched: a bare date/today question has
    # no event term, so neither trigger shape matches (the plan's key caution —
    # never chase the authoritative injected clock with a calendar read).
    assert eng._needs_calendar_grounding(
        "What is the date today?", "Today is 2026-07-11.", []) is False
    # A date with no event term in the reply is likewise left alone.
    assert eng._needs_calendar_grounding(
        "when's the part arriving?", "Should land 2026-07-15.", []) is False


class _Snip:
    """Minimal stand-in for a retriever result (only .path is read by the
    grounding-source check)."""
    def __init__(self, path):
        self.path = path


@pytest.mark.case("CITE-001", "citation classifier: a stored-fact claim is 'cited' with a source this turn, 'uncited-recall' without, and 'no-recall-claim' when she cites nothing (Phase 5, item 3.3)")
def test_citation_classifier(sandbox):
    eng = sandbox.service.engine
    note = [_Snip("projects/alpha_rig.md")]

    # No store-citation language -> nothing to ground.
    assert eng._citation_grounding(
        "The 5V rail feeds the PCA9685.", [], []) == "no-recall-claim"
    # Ordinary conversational recall is NOT a stored-brain claim -> not flagged.
    assert eng._citation_grounding(
        "As you mentioned earlier, the buck has no fuse.", [], []) \
        == "no-recall-claim"

    # A stored-fact claim WITH a retrieved note -> cited.
    assert eng._citation_grounding(
        "Your notes say the torque spec is 1.2 Nm.", [], note) == "cited"
    # ...or with a read/recall tool this turn -> cited.
    assert eng._citation_grounding(
        "From your notes, ESC 3 cut out at 9 A.",
        [{"tool": "search_brain", "args": {}}], []) == "cited"
    # ...or with a durable WRITE this turn ("I saved that" is true).
    assert eng._citation_grounding(
        "I have it saved that the sync is weekly.",
        [{"tool": "write_brain", "args": {}}], []) == "cited"

    # A stored-fact claim with NOTHING surfaced this turn -> the confabulation
    # signature the barrier targets.
    assert eng._citation_grounding(
        "Your notes say the deadline is Friday.", [], []) == "uncited-recall"


@pytest.mark.case("CITE-002", "citation barrier trigger: fires on a stored-brain claim with no source this turn; never on grounded turns or ordinary talk (Phase 5, item 3.3)")
def test_citation_trigger(sandbox):
    eng = sandbox.service.engine
    note = [_Snip("preferences/about_jack.md")]

    # The target case: claims to cite the saved brain, but no note was
    # retrieved and no lookup ran -> barrier must fire.
    assert eng._needs_citation_grounding(
        "Your notes say the neutral pulse is 1500 us.", [], []) is True
    assert eng._needs_citation_grounding(
        "According to your saved notes, the part shipped Tuesday.", [], []) is True

    # A read/recall tool ran this turn -> grounded, does not fire.
    assert eng._needs_citation_grounding(
        "Your notes say the neutral pulse is 1500 us.",
        [{"tool": "read_brain", "args": {}}], []) is False
    # A note was retrieved -> grounded, does not fire.
    assert eng._needs_citation_grounding(
        "Your notes say the neutral pulse is 1500 us.", [], note) is False
    # A durable write this turn grounds "I saved that" -> does not fire.
    assert eng._needs_citation_grounding(
        "I have that saved as a blocker now.",
        [{"tool": "track_commitment", "args": {}}], []) is False

    # No store-citation language -> never fires, whatever the sources.
    assert eng._needs_citation_grounding(
        "The 5V rail is shared by the camera and the PCA9685.", [], []) is False
    # Offering to save is not a citation -> never fires.
    assert eng._needs_citation_grounding(
        "I'll save this to your notes.", [], []) is False


@pytest.mark.case("GND-004", "artifact_review playbook is seeded and indexed")
def test_review_playbook_seeded():
    from helpers.harness import FRIDAY_ROOT
    p = FRIDAY_ROOT / "brain" / "playbooks" / "artifact_review.md"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    for phrase in ("known", "hypothesis", "UNREAD", "EMI"):
        assert phrase in text


@pytest.mark.case("GND-005", "conjunct splitter: fires only on clear multi-part requests; echo check finds silent drops")
def test_conjunct_machinery():
    from core.conjuncts import checklist_block, split_conjuncts, unaddressed

    # The measured failure shape: lead-in + three verb-led parts.
    parts = split_conjuncts(
        "three things: read C:/tmp/mast_notes.md, summarize it in one line, "
        "and email the summary to Kevin")
    assert len(parts) == 3 and "email" in parts[2]

    # Numbered enumerators fire too.
    assert len(split_conjuncts(
        "1) order more PETG for the AMS 2) check the buck fuse rating")) == 2
    # An unmistakable 3-verb chain fires without a lead-in.
    assert len(split_conjuncts(
        "read the ESC log, check the neutral values, and update the note")) == 3

    # Conservative: single asks and TWO-part chains never fire (a false
    # split meddling with a normal request is worse than a missed one).
    assert split_conjuncts("what's the neutral pulse for the ESCs?") == []
    assert split_conjuncts("read notes/pilot_handoff.txt and action it") == []
    assert split_conjuncts(
        "the camera and the PCA9685 share the 5V rail, which worries me") == []

    # Echo check: covering two parts leaves the third as silently dropped;
    # stems match (summarize/summary), so wording variance doesn't false-flag.
    missing = unaddressed(parts,
                          "Read it. Summary: the 5V rail is shared and the "
                          "buck has no fuse.")
    assert missing == [parts[2]]
    assert unaddressed(parts, "Read it; summary above; I can't send email "
                              "- drafted it for Kevin instead.") == []
    assert "3 distinct things" in checklist_block(parts)


# ---------------------------------------------------------------------------
# Model acceptance — replaying the Doc Ock transcript shapes. @upgrade keeps
# these out of the fine-tune A/B yardstick.
# ---------------------------------------------------------------------------

def _seed_artifact(sandbox, name="wrist_wiring_notes.md"):
    """File one readable artifact into a project via the real tools, through
    the real conversation path (so the referent stack sees it)."""
    src = _plant_file(sandbox, name,
                      "# Gripper wiring\n- 5V rail shared by PCA9685 and camera\n"
                      "- No fuse between pack and buck converter\n"
                      "- Servo grounds star-pointed at the driver\n")
    return src


@pytest.mark.model
@pytest.mark.skill("thinking_skills")
@pytest.mark.upgrade
@pytest.mark.case("GND-010", "'analyze this and file it' does BOTH; filing-only fails (N runs)")
def test_analyze_and_file(sandbox, detail):
    sandbox.service.engine.registry.call(
        "create_project", {"name": "Gimbal Mount",
                           "description": "throwaway grounding fixture"})

    def once(_run):
        src = _seed_artifact(sandbox)
        reply = sandbox.ask(
            f"add {src.as_posix()} to the Gimbal Mount project and give me "
            f"your analysis of it")
        low = reply.lower()
        filed = "add_files_to_project" in sandbox.rec.tool_names() \
            or "create_project" in sandbox.rec.tool_names()
        # Substance = it engages the CONTENT (any of the wiring facts).
        analyzed = any(w in low for w in ["fuse", "5v", "rail", "ground",
                                          "buck", "pca9685"])
        return filed and analyzed, {"filed": filed, "analyzed": analyzed,
                                    "reply": reply[:200]}
    ok, results = repeat_behavior(once, sandbox=sandbox, detail=detail)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "filing without analysis (or neither)"


@pytest.mark.case("GND-014", "web_fetch arg-guard: a local-path arg reroutes to a disk read, never a dead-end error")
def test_web_fetch_local_path_guard(sandbox):
    """GND-010's dominant failure mechanism (13/20 sampled runs): handed the
    artifact's LOCAL path, the model calls web_fetch, gets 'ERROR: only
    http(s) URLs can be fetched.' and narrates that dead end as its final
    reply — the fetch error displaces the analysis. Deterministic guard:
    a non-URL arg naming a real file is read from disk (same gate check and
    taint posture as read_file); a non-URL arg naming nothing gets a
    corrective hint naming the right tool. Code-only, no model."""
    src = _plant_file(sandbox, "wiring_notes.md",
                      "# Wiring\n5V rail feeds the PCA9685 via a buck.\n")
    reg = sandbox.service.engine.registry
    # Posix-style spelling (what GND-010's prompt hands the model):
    out = reg.call("web_fetch", {"url": src.as_posix()})
    assert "PCA9685" in out and not out.startswith("ERROR")
    # Windows backslashes + shell-style quoting survive the reroute:
    out2 = reg.call("web_fetch", {"url": f'"{src}"'})
    assert "PCA9685" in out2
    # A non-URL naming nothing: corrective hint, names the right tool.
    out3 = reg.call("web_fetch", {"url": "C:/nope/definitely_missing.md"})
    assert "read_file" in out3


@pytest.mark.model
@pytest.mark.skill("thinking_skills")
@pytest.mark.upgrade
@pytest.mark.case("GND-011", "one artifact in session: 'thoughts on it?' answered with ZERO clarifying questions (N runs)")
def test_thoughts_resolved_silently(sandbox, detail):
    def once(_run):
        src = _seed_artifact(sandbox)
        sandbox.ask(f"read {src.as_posix()}")
        reply = sandbox.ask("what are your thoughts on the notes I just handed you?")
        low = reply.lower()
        # A clarification request is a FAILURE when one obvious referent exists.
        clarifies = any(p in low for p in [
            "which document", "which file", "which notes", "could you specify",
            "please specify", "can you clarify", "which one do you mean",
            "what document are you referring"])
        substantive = any(w in low for w in ["fuse", "5v", "rail", "ground",
                                             "buck", "star"])
        return (not clarifies) and substantive, {
            "clarifies": clarifies, "substantive": substantive,
            "reply": reply[:200]}
    ok, results = repeat_behavior(once, sandbox=sandbox, detail=detail)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "asked for clarification (or gave no substance) with one obvious referent"


@pytest.mark.model
@pytest.mark.skill("thinking_skills")
@pytest.mark.upgrade
@pytest.mark.case("GND-012", "never-introduced artifact: says so plainly, offers no unrelated menu (N runs)")
def test_unknown_artifact_honest(sandbox, detail):
    def once(_run):
        reply = sandbox.ask("thoughts on the hydraulics spreadsheet I gave you?")
        low = reply.lower()
        honest = any(p in low for p in [
            "haven't", "don't have", "no spreadsheet", "didn't", "not seeing",
            "don't see", "nothing", "no record", "wasn't given", "never received"])
        # Offering unrelated documents as candidates was the original failure.
        menu = any(p in low for p in ["writing a playbook", "trade study",
                                      "trade_study", "artifact review"])
        return honest and not menu, {"honest": honest, "menu": menu,
                                     "reply": reply[:200]}
    ok, results = repeat_behavior(once, sandbox=sandbox, detail=detail)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "not honest about an unknown artifact, or offered a menu"


@pytest.mark.model
@pytest.mark.skill("thinking_skills")
@pytest.mark.upgrade
@pytest.mark.case("GND-013", "three-verb request with one impossible verb: the gap is reported, not papered over (N runs)")
def test_partial_completion_reported(sandbox, detail):
    def once(_run):
        src = _seed_artifact(sandbox, name="mast_notes.md")
        reply = sandbox.ask(
            f"three things: read {src.as_posix()}, summarize it in one "
            f"line, and email the summary to Kevin")
        low = reply.lower()
        summarized = any(w in low for w in ["5v", "fuse", "wiring", "ground",
                                            "rail", "servo"])
        # Email-SEND doesn't exist by design — that conjunct's gap must be
        # SAID. The plan's bar is "every conjunct is either done, or its
        # non-completion is stated": an explicitly-reported failure on a
        # doable conjunct (e.g. the sandbox has no mail account for the
        # draft) counts as stated, silence does not.
        # The email conjunct's non-completion is "stated" whether she says
        # send-doesn't-exist OR reports the concrete failure she hit trying
        # ("ERROR: no account named 'personal'") — both are honest gaps.
        # Silent drop of any conjunct is the failure being tested.
        email_stated = any(p in low for p in [
            "can't email", "cannot email", "can't send", "cannot send",
            "no email", "don't have email", "won't send", "email isn't",
            "email is not", "not something i can", "doesn't exist", "draft",
            "no account", "error accessing", "email account",
            "did not address", "didn't address"])
        return email_stated and summarized, {
            "summarized": summarized, "email_stated": email_stated,
            "reply": reply[:220]}
    ok, results = repeat_behavior(once, sandbox=sandbox, detail=detail)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "partial completion not reported (or nothing done)"

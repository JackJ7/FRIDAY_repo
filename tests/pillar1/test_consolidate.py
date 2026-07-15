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

MRG-002  the pending-consolidation ledger (CN.2): armed by JACK's merge-intent
         message with the resolved operand set, it persists across qualified
         affirmatives and distraction turns (the shapes that defeat the offer
         ledger BY DESIGN), rides a deterministic status directive at the END
         of the referent block (max-obedience slot — measured on GT-C10 T1:
         the mid-block operand hint rode and the 14B re-asked anyway), sets
         the survivor from an exact name, clears on a LANDED merge / cancel /
         expiry, and never arms on ordinary chat.

MRG-003  the identifier grounding floor + which-ask backstop (CN.3): a
         fabricated quoted project name is held, retried once, then falls
         back to the honest real list; a naked which-ask on a pending
         no-survivor turn becomes the code-built survivor-confirm question.

MRG-004  the narrated-listing floor (CN.4): a reply that ENDS on
         first-person-future narration of a project listing with ZERO tools
         run gets the listing appended by code (engine runs list_projects
         itself — Shape D can't recover prose that names no tool). Completed
         answers, mid-reply narration, turns where tools ran, and ACTION
         narration ("let me merge them") are all untouched.
"""

import pytest

from core.model import ModelReply
from core.project_resolver import merge_intent


def _call(sandbox, name, args=None):
    return sandbox.service.engine.registry.call(name, args or {})


def _plant_note(sandbox, slug, title=None, files=None):
    """A project note via the brain API directly — the legitimate code path
    (create_project / test fixtures), deliberately NOT the guarded tool.
    With `files`, also plants a project-zone folder so a merge has real
    moves for the gate to confirm (the test_merge_projects pattern)."""
    title = title or slug.replace("_", " ").title()
    folder_line = ""
    if files is not None:
        folder = sandbox.root / "Projects" / slug
        folder.mkdir(parents=True, exist_ok=True)
        for fn, content in files.items():
            (folder / fn).write_text(content, encoding="utf-8")
        folder_line = f"- **Folder:** {folder}\n"
    sandbox.brain.write_note(
        f"projects/{slug}.md",
        f"# {title}\n\n- **Status:** active\n{folder_line}\n"
        "Flux beam tooling.\n",
        mode="create", summary=f"plant {slug}")


FLUX_SLUGS = ("fluxbeam", "flux_beam_tool", "flux_beam_v2")


class _ScriptModel:
    """Scripted replies in order; records every chat() message list. An item
    is a string (text reply) or {"content": ..., "tool_calls": [...]}."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.seen.append(messages)
        item = self.script.pop(0) if self.script else ""
        r = ModelReply()
        if isinstance(item, dict):
            r.content = item.get("content", "")
            r.tool_calls = list(item.get("tool_calls", []))
        else:
            r.content = item
        r.eval_count = 5
        return r


def _sys_text(model) -> str:
    """The system content of the model's most recent chat() call."""
    msgs = model.seen[-1]
    return "\n".join(m.get("content") or "" for m in msgs
                     if m.get("role") == "system")


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


def _armed_engine(sandbox, script):
    """Plant the flux trio, script the model, and arm the ledger with the
    GT-C9 T1 fuzzy-filter ask. Returns the engine mid-conversation."""
    for slug in FLUX_SLUGS:
        _plant_note(sandbox, slug)
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    eng.respond("Please consolidate all the projects with flux in the name.")
    return eng


@pytest.mark.upgrade
@pytest.mark.case("MRG-002", "pending-consolidation ledger: arms on Jack's "
                             "merge ask, survives qualified affirmatives and "
                             "distraction turns, sets the survivor from an "
                             "exact name, directive rides after the entity "
                             "hint")
def test_mrg002_ledger_lifecycle(sandbox):
    eng = _armed_engine(sandbox, ["Here are the flux projects.",
                                  "On it.",
                                  "Still working through it.",
                                  "Right, Fluxbeam it is."])
    task = eng.consolidation
    assert task and set(task["candidates"]) == set(FLUX_SLUGS), task
    assert task["survivor"] is None
    sys_txt = _sys_text(eng.model)
    assert "PENDING CONSOLIDATION TASK" in sys_txt
    # The measured placement requirement: the task directive rides AFTER the
    # entity-resolution hint (toward the max-obedience end of the block).
    if "Entity resolution" in sys_txt:
        assert (sys_txt.index("PENDING CONSOLIDATION TASK")
                > sys_txt.index("Entity resolution"))

    # Qualified affirmative with residue — the offer ledger drops these BY
    # DESIGN (residue rule); the task must survive and refresh.
    eng.respond("Ok, please update the project folder.")
    assert eng.consolidation is not None
    assert eng.consolidation["turns_left"] == eng._CONSOLIDATION_TTL
    assert "PENDING CONSOLIDATION TASK" in _sys_text(eng.model)

    # A distraction turn only ticks the TTL down, never drops the task.
    eng.respond("How's it looking?")
    assert eng.consolidation is not None
    assert eng.consolidation["turns_left"] < eng._CONSOLIDATION_TTL

    # Exact-name survivor confirm -> the ENGINE executes the merge itself
    # (CN.2.1 escalation, calendar-first posture): notes-only merge lands
    # immediately, the task retires, the directive reports the execution, and
    # the merge appears in the turn's tool ledger (memory-pass truth, TM.1).
    reply = eng.respond("Keep Fluxbeam as the survivor.")
    assert eng.consolidation is None
    sys_txt = _sys_text(eng.model)
    assert "CONSOLIDATION EXECUTED" in sys_txt, sys_txt[-400:]
    for dup in ("projects/flux_beam_tool.md", "projects/flux_beam_v2.md"):
        assert "merged into" in sandbox.brain.read_note(dup).lower()
    assert any(t["tool"] == "merge_projects" for t in reply.tool_log)


@pytest.mark.upgrade
@pytest.mark.case("MRG-002b", "survivor naming: the longest candidate match "
                              "wins — 'Flux Beam Tool' must not read as its "
                              "prefix candidate 'fluxbeam'")
def test_mrg002b_survivor_longest_match(sandbox):
    eng = _armed_engine(sandbox, ["Listing them.", "Tool it is."])
    eng.respond("Keep Flux Beam Tool as the survivor.")
    # The escalation executed on the confirm, so the proof is disk truth:
    # flux_beam_tool survived (no merged status), the OTHER TWO were folded —
    # naming 'Flux Beam Tool' did not read as its prefix candidate 'fluxbeam'.
    assert eng.consolidation is None
    assert "merged into" not in sandbox.brain.read_note(
        "projects/flux_beam_tool.md").lower()
    for dup in ("projects/fluxbeam.md", "projects/flux_beam_v2.md"):
        assert "merged into" in sandbox.brain.read_note(dup).lower(), dup


@pytest.mark.upgrade
@pytest.mark.case("MRG-002c", "a DECLINED escalation merge is atomic and the "
                              "task stays pending, with an honest directive — "
                              "never a claimed merge")
def test_mrg002c_declined_escalation_stays_pending(tmp_path):
    from helpers.harness import SandboxFriday
    sb = SandboxFriday(tmp_path, confirm_reply=False)   # declining Jack
    for slug in FLUX_SLUGS:
        _plant_note(sb, slug, files={f"{slug}.txt": "data"})
    eng = sb.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(["Listing them.", "Understood."])

    eng.respond("Please consolidate all the projects with flux in the name.")
    assert eng.consolidation is not None

    # Survivor confirm triggers the escalation; the gate DECLINES the file
    # moves -> merge is atomic (nothing on disk), the task stays pending, and
    # the directive says so in plain terms.
    eng.respond("Keep Fluxbeam as the survivor.")
    assert eng.consolidation is not None
    assert eng.consolidation["survivor"] == "fluxbeam"
    sys_txt = _sys_text(eng.model)
    assert "did NOT land" in sys_txt, sys_txt[-400:]
    assert "CONSOLIDATION EXECUTED" not in sys_txt
    for dup in ("projects/flux_beam_tool.md", "projects/flux_beam_v2.md"):
        assert "merged into" not in sb.brain.read_note(dup).lower()


@pytest.mark.upgrade
@pytest.mark.case("MRG-002d", "expiry after sustained disengagement; cancel "
                              "clears immediately; ordinary chat never arms")
def test_mrg002d_expiry_cancel_noarm(sandbox):
    for slug in FLUX_SLUGS:
        _plant_note(sandbox, slug)
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(["A text reply."] * 20)

    # Ordinary project chat never arms the ledger.
    eng.respond("Tell me about the fluxbeam project.")
    assert eng.consolidation is None

    # Cancel clears immediately.
    eng.respond("Please merge the flux projects into one.")
    assert eng.consolidation is not None
    eng.respond("Never mind, cancel that.")
    assert eng.consolidation is None

    # Sustained disengagement expires the task (engagement-based TTL).
    eng.respond("Please merge the flux projects into one.")
    assert eng.consolidation is not None
    for i in range(eng._CONSOLIDATION_TTL):
        eng.respond(f"Random filler question number {i}, nothing to do?")
    assert eng.consolidation is None


@pytest.mark.upgrade
@pytest.mark.case("MRG-003", "identifier grounding floor: a fabricated quoted "
                             "project name is held and retried; a second miss "
                             "falls back to the honest real list; the offer "
                             "ledger never arms on the fabricated draft")
def test_mrg003_identifier_floor(sandbox):
    # Retry comes back clean -> the retry is accepted verbatim.
    eng = _armed_engine(sandbox, [
        "Listing them.",
        "Would you like me to merge them into 'flux-beam-utils'?",   # draft
        "I suggest keeping 'Fluxbeam' as the survivor — confirm?",   # retry
    ])
    reply = eng.respond("How's it looking?")
    assert "flux-beam-utils" not in reply.content
    assert "Fluxbeam" in reply.content
    # The fabricated draft never became a standing offer.
    assert not eng.offer or "utils" not in eng.offer["text"]


@pytest.mark.upgrade
@pytest.mark.case("MRG-003b", "identifier floor second miss: honest fallback "
                              "with the real project list; clean replies and "
                              "no-context turns untouched")
def test_mrg003b_fallback_and_negatives(tmp_path):
    from helpers.harness import SandboxFriday
    sb = SandboxFriday(tmp_path / "a")
    for slug in FLUX_SLUGS:
        _plant_note(sb, slug)
    eng = sb.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel([
        "Listing them.",
        "Merging into 'flux-beam-mega' now.",   # draft: fabricated
        "Then 'flux-beam-mega' it is.",         # retry: fabricated again
    ])
    eng.respond("Please consolidate all the projects with flux in the name.")
    reply = eng.respond("How's it looking?")
    assert "flux-beam-mega" not in reply.content
    assert "mis-named" in reply.content
    for title in ("Fluxbeam", "Flux Beam Tool", "Flux Beam V2"):
        assert title in reply.content

    # Clean reply with a REAL quoted name is untouched, no retry spent.
    sb2 = SandboxFriday(tmp_path / "b")
    for slug in FLUX_SLUGS:
        _plant_note(sb2, slug)
    eng2 = sb2.service.engine
    eng2.vote_enabled = False
    clean = "I suggest keeping 'Fluxbeam' as the survivor — shall I proceed?"
    eng2.model = _ScriptModel(["Listing them.", clean])
    eng2.respond("Please consolidate all the projects with flux in the name.")
    calls_before = len(eng2.model.seen)
    reply2 = eng2.respond("How's it looking?")
    assert reply2.content == clean
    assert len(eng2.model.seen) == calls_before + 1   # no retry call

    # No project context -> quoted junk is never scanned.
    sb3 = SandboxFriday(tmp_path / "c")
    eng3 = sb3.service.engine
    eng3.vote_enabled = False
    junk = "Try 'weird-thing-x' maybe."
    eng3.model = _ScriptModel([junk])
    reply3 = eng3.respond("Any ideas for the weekend?")
    assert reply3.content == junk


@pytest.mark.upgrade
@pytest.mark.case("MRG-003c", "naked which-ask on a pending no-survivor turn "
                              "is replaced by the code-built survivor-confirm "
                              "question (the GT-C10 T1 residual, converted by "
                              "construction)")
def test_mrg003c_which_ask_backstop(sandbox):
    eng = _armed_engine(sandbox, [
        "Which one do you mean?",   # T1 draft: the naked which-ask
    ])
    # The floor replaced it in the SAME turn the task armed.
    last = eng.history[-1]["content"] if eng.history else ""
    assert "These all match:" in last, last
    assert "shall I go ahead" in last
    for slug in FLUX_SLUGS:
        assert slug in last
    assert eng.consolidation is not None          # still pending, no survivor
    assert eng.consolidation["survivor"] is None


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


@pytest.mark.upgrade
@pytest.mark.case("MRG-004", "narrated-listing floor: a reply ending on "
                             "first-person-future listing narration with zero "
                             "tools run gets the REAL listing appended by "
                             "code; the narration itself is preserved")
def test_mrg004_narrated_list_floor(sandbox):
    # The GT-C9 stamp-1623 T2 shape verbatim: promise to list, no tool call.
    narration = ("To proceed I first need the full set of flux projects. "
                 "Let's start by listing them.")
    eng = _armed_engine(sandbox, [narration])
    reply = eng.history[-1]["content"] if eng.history else ""
    assert reply.startswith(narration), reply       # appended, never replaced
    assert "project(s):" in reply, reply            # list_projects' real text
    for title in ("Fluxbeam", "Flux Beam Tool", "Flux Beam V2"):
        assert title in reply, f"{title} missing from fulfilled listing"


@pytest.mark.upgrade
@pytest.mark.case("MRG-004b", "narrated-listing floor negatives: completed "
                              "answers, mid-reply narration, and turns where "
                              "tools already ran are byte-identical")
def test_mrg004b_negatives(tmp_path):
    from helpers.harness import SandboxFriday

    # Completed answer, no narration tail -> untouched.
    sb = SandboxFriday(tmp_path / "a")
    for slug in FLUX_SLUGS:
        _plant_note(sb, slug)
    eng = sb.service.engine
    eng.vote_enabled = False
    done = "You have three flux projects: Fluxbeam, Flux Beam Tool, Flux Beam V2."
    eng.model = _ScriptModel([done])
    assert eng.respond("What flux projects do we have?").content == done

    # Narration mid-reply, real content after it -> the model finished; quiet.
    sb2 = SandboxFriday(tmp_path / "b")
    for slug in FLUX_SLUGS:
        _plant_note(sb2, slug)
    eng2 = sb2.service.engine
    eng2.vote_enabled = False
    finished = ("Let me list them. You have Fluxbeam, Flux Beam Tool and "
                "Flux Beam V2 — all active.")
    eng2.model = _ScriptModel([finished])
    assert eng2.respond("What flux projects do we have?").content == finished

    # A tool RAN this turn -> the promise was kept by the model; quiet even
    # though the tail narrates (no doubled listing).
    sb3 = SandboxFriday(tmp_path / "c")
    for slug in FLUX_SLUGS:
        _plant_note(sb3, slug)
    eng3 = sb3.service.engine
    eng3.vote_enabled = False
    tail = "Those are all three. Now let me list the next steps."
    eng3.model = _ScriptModel([
        {"content": "", "tool_calls": [
            {"function": {"name": "list_projects", "arguments": {}}}]},
        tail])
    reply3 = eng3.respond("What flux projects do we have?")
    assert reply3.content.count("project(s):") <= 1, reply3.content


@pytest.mark.upgrade
@pytest.mark.case("MRG-004c", "narrated-listing floor never fires on ACTION "
                              "narration: 'let me merge them' runs nothing "
                              "and moves nothing on disk")
def test_mrg004c_action_narration_quiet(sandbox):
    narration = "Understood. Let me merge them into one project now."
    eng = _armed_engine(sandbox, [narration])
    reply = eng.history[-1]["content"] if eng.history else ""
    assert reply == narration, reply                # no append, no replacement
    # Nothing moved on disk — narrating an action is never a license to act.
    for slug in FLUX_SLUGS:
        assert "merged into" not in sandbox.brain.read_note(
            f"projects/{slug}.md").lower()

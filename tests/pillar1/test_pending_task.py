r"""
PENDING-TASK-leg guards (armor plan §6, Phase PENDING-TASK): code-only, no model.

PTL-001  ledger arming (PT.1): a request-shaped message answered by a
         clarify-question with no landed action arms self.pending_task with
         the request and the blocker; a reply that ends declaratively, a
         non-request message, and a reply that makes an OFFER (the offer
         ledger's territory) never arm.
PTL-002  ledger lifecycle (PT.1): the directive rides the END of the referent
         block on later turns; engagement (affirmative prefix / task-token
         overlap) refreshes the TTL; ignoring turns tick it down to expiry;
         the shared cancel vocabulary clears it.
PTL-003  ledger retire (PT.1): an action that LANDED retires the task (disk
         truth, like the consolidation retire); a BLOCKED/ERROR action keeps
         it pending.
PTL-004  generic-clarify floor, pending branch (PT.2): a generic clarify that
         names nothing of the pending task is regenerated once; a clean retry
         is accepted; a still-generic retry falls back to the code-built
         re-ask that NAMES the task.
PTL-005  floor stays quiet (PT.2): a clarify that NAMES the pending task
         (token overlap) is never touched — the legitimate which-ask.
PTL-006  generic-clarify floor, artifact branch (PT.2): with exactly ONE
         artifact referent, a substance+trailing-clarify reply (GND-011's
         residual) is cleaned — via regeneration when the anti-dodge barrier
         did not already burn a retry, via the deterministic sentence strip
         when it did (the re-hedge path is exactly where the tic survived).
PTL-007  floor safety (PT.2): two artifact referents (a which-ask may be
         legitimate) and zero referents both leave the reply untouched; the
         strip fallback never empties a reply.
PTL-008  which-ask backstop widening (PT.2): on a pending no-survivor
         consolidation turn the measured GT-C9 T3 draft ("could you please
         specify...") is replaced by the code-built survivor question — no
         extra model call.

FLD-001  field-matching floor (PT.3): a paraphrased field name ('load cell
         rating') UPDATES the note's existing 'Load cell' line in place —
         canonical name kept, no second line.
FLD-002  genuinely new fields still insert (the MEM-020 guarantee).
FLD-003  ambiguity refuses with a corrective naming the candidate fields and
         the retry — and writes NOTHING.
FLD-004  an exact field name short-circuits the fuzzy pass entirely.
"""

import pytest

from core.model import ModelReply
from core.project_meta import match_field


class _ScriptModel:
    """Returns scripted replies in order. An item is either a string (text
    reply) or a dict {"content": ..., "tool_calls": [...]} (a tool round)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.seen = []

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        self.seen.append(messages)
        item = self.script.pop(0) if self.script else ""
        r = ModelReply()
        if isinstance(item, dict):
            r.content = item.get("content", "")
            r.tool_calls = list(item.get("tool_calls", []))
        else:
            r.content = item
        r.eval_count = 5
        if on_token and r.content:
            on_token(r.content)
        return r


def _engine(sandbox, script):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    return eng


def _sys_text(model) -> str:
    msgs = model.seen[-1]
    return "\n".join(m.get("content") or "" for m in msgs
                     if m.get("role") == "system")


ASK = "Please add the new motor spec to the beta probe housing note."
CLARIFY = ("Which motor spec do you mean — the torque figure or the model "
           "number?")


# ---- PT.1: the ledger -----------------------------------------------------

@pytest.mark.upgrade
@pytest.mark.case("PTL-001", "pending-task ledger arms on request+clarify, "
                             "never on declarative replies, non-requests, or "
                             "offers")
def test_ptl001_arming(sandbox):
    # Request-shaped ask answered by a blocking clarify -> armed.
    eng = _engine(sandbox, [CLARIFY])
    eng.respond(ASK)
    task = eng.pending_task
    assert task, "request + clarify-question reply must arm the ledger"
    assert "motor spec" in task["request"]
    assert task["blocker"].startswith("Which motor spec")

    # Declarative completion -> not armed. (Same engine object each time —
    # clear the ledger between sub-cases so each starts cold.)
    eng = _engine(sandbox, ["Done — the note now carries the motor spec."])
    eng.pending_task = None
    eng.respond(ASK)
    assert eng.pending_task is None

    # Not request-shaped -> not armed even when the reply asks back.
    eng = _engine(sandbox, [CLARIFY])
    eng.pending_task = None
    eng.respond("Hmm, the beta probe housing motor spec situation is odd.")
    assert eng.pending_task is None

    # A fresh OFFER owns the turn -> the offer ledger arms, this one doesn't.
    eng = _engine(sandbox, ["Would you like me to read the beta probe note "
                            "first?"])
    eng.pending_task = None
    eng.respond(ASK)
    assert eng.offer is not None
    assert eng.pending_task is None


@pytest.mark.upgrade
@pytest.mark.case("PTL-002", "pending-task directive rides the block end; "
                             "engagement refreshes TTL; ignoring turns expire "
                             "it; cancel clears it")
def test_ptl002_lifecycle(sandbox):
    eng = _engine(sandbox, [CLARIFY,
                            "Noted — torque figure it is.",
                            "Sure thing."])
    eng.respond(ASK)
    assert eng.pending_task is not None

    # Next turn: the directive rides in the system text and names the ask.
    eng.respond("The torque one.")
    sys_txt = _sys_text(eng.model)
    assert "PENDING TASK" in sys_txt
    assert "motor spec" in sys_txt
    # Engagement via task-token overlap refreshed the TTL.
    assert eng.pending_task["turns_left"] == eng._PENDING_TASK_TTL

    # Affirmative prefix also counts as engagement.
    eng.respond("Ok, sounds right.")
    assert eng.pending_task["turns_left"] == eng._PENDING_TASK_TTL

    # Ignoring turns tick it down to expiry.
    eng.model = _ScriptModel(["Grand day for it."] * (eng._PENDING_TASK_TTL + 1))
    for _ in range(eng._PENDING_TASK_TTL):
        eng.respond("How's the weather looking out there?")
    assert eng.pending_task is None

    # Cancel vocabulary clears immediately.
    eng = _engine(sandbox, [CLARIFY, "No bother, dropped."])
    eng.respond(ASK)
    assert eng.pending_task is not None
    eng.respond("Never mind, forget it.")
    assert eng.pending_task is None


@pytest.mark.upgrade
@pytest.mark.case("PTL-003", "a LANDED action retires the pending task; a "
                             "refused write keeps it pending")
def test_ptl003_retire_on_landed_action(sandbox):
    eng = _engine(sandbox, [
        CLARIFY,
        {"content": "",
         "tool_calls": [{"function": {
             "name": "write_brain",
             "arguments": {"path": "inbox/motor_spec.md",
                           "content": "Torque figure: 2.4 N*m",
                           "mode": "create",
                           "summary": "motor spec"}}}]},
        "Saved the torque figure to your inbox.",
    ])
    eng.respond(ASK)
    assert eng.pending_task is not None
    eng.respond("The torque figure — 2.4 N*m.")
    assert eng.pending_task is None, "a landed action must retire the task"

    # A REFUSED write (the projects/ phantom guard) is not completion.
    eng = _engine(sandbox, [
        CLARIFY,
        {"content": "",
         "tool_calls": [{"function": {
             "name": "write_brain",
             "arguments": {"path": "projects/brand_new_thing.md",
                           "content": "Torque figure: 2.4 N*m",
                           "mode": "create",
                           "summary": "motor spec"}}}]},
        "I put the motor spec torque figure in the note.",
    ])
    eng.respond(ASK)
    assert eng.pending_task is not None
    eng.respond("The torque figure — 2.4 N*m.")
    assert eng.pending_task is not None, \
        "an ERROR'd action must NOT retire the task"


# ---- PT.2: the generic-clarify floor --------------------------------------

@pytest.mark.upgrade
@pytest.mark.case("PTL-004", "generic clarify on a pending-task turn: clean "
                             "retry accepted; still-generic retry falls back "
                             "to the code-built NAMED re-ask")
def test_ptl004_pending_branch(sandbox):
    # Clean retry accepted.
    eng = _engine(sandbox, [
        CLARIFY,
        "Could you clarify what you mean?",
        "Back on the motor spec — I still need which figure: torque or "
        "model number.",
    ])
    eng.respond(ASK)
    reply = eng.respond("Go on so.")
    assert "motor spec" in reply.content
    assert "could you clarify" not in reply.content.lower()

    # Still-generic retry -> deterministic fallback naming the task.
    eng = _engine(sandbox, [
        CLARIFY,
        "Could you clarify what you mean?",
        "Please clarify.",
    ])
    eng.respond(ASK)
    reply = eng.respond("Go on so.")
    assert "pending ask" in reply.content
    assert "motor spec" in reply.content


@pytest.mark.upgrade
@pytest.mark.case("PTL-005", "a clarify that NAMES the pending task is "
                             "legitimate and never touched")
def test_ptl005_named_clarify_untouched(sandbox):
    named = ("Could you clarify which motor spec you mean — the torque "
             "figure or the model number?")
    eng = _engine(sandbox, [CLARIFY, named])
    eng.respond(ASK)
    before = eng.model.calls
    reply = eng.respond("Go on so.")
    assert reply.content == named
    assert eng.model.calls == before + 1, "no retry may be spent"


def _seed_artifact_turn(sandbox, script_tail):
    """The ADF pattern: read a real file through the REAL read_file tool so
    the referent stack carries exactly one artifact."""
    src = sandbox.root / "incoming" / "wrist_wiring_notes.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Gripper wiring\n- 5V rail shared by PCA9685 and camera\n"
                   "- No fuse between pack and buck converter\n",
                   encoding="utf-8")
    eng = _engine(sandbox, [
        {"content": "",
         "tool_calls": [{"function": {"name": "read_file",
                                      "arguments": {"path": str(src)}}}]},
        "Read it - the gripper wiring notes are on file.",
    ] + list(script_tail))
    eng.respond(f"read {src.as_posix()}")
    return eng


ARTIFACT_ASK = "what are your thoughts on the notes I just handed you?"
SUBSTANCE = ("The missing fuse between the pack and the buck converter is "
             "the real risk here - a short on the shared 5V rail takes out "
             "the PCA9685 and the camera together. I'd fuse the pack lead "
             "first.")


@pytest.mark.upgrade
@pytest.mark.case("PTL-006", "GND-011 residual: substance + trailing clarify "
                             "with ONE artifact referent is cleaned (strip "
                             "after a burned dodge retry; regeneration when "
                             "the dodge net stayed quiet)")
def test_ptl006_artifact_branch(sandbox):
    # (a) The tic matches the dodge net too; its retry re-hedges, the barrier
    # keeps the ORIGINAL (the measured survival path) — the floor's strip
    # fallback must clean it without a third model call.
    tic = " Could you specify which file you mean?"
    eng = _seed_artifact_turn(sandbox, [SUBSTANCE + tic, SUBSTANCE + tic])
    reply = eng.respond(ARTIFACT_ASK)
    low = reply.content.lower()
    assert "could you specify" not in low and "which file" not in low
    assert "fuse" in low, "the substance must survive the strip"

    # (b) A which-artifact tail the dodge net does NOT match: the floor's own
    # regeneration runs, and a clean retry is accepted.
    tail = " Which notes should I prioritise for a deeper pass?"
    eng = _seed_artifact_turn(sandbox, [
        SUBSTANCE + tail,
        SUBSTANCE,
    ])
    reply = eng.respond(ARTIFACT_ASK)
    low = reply.content.lower()
    assert "which notes" not in low
    assert "fuse" in low


@pytest.mark.upgrade
@pytest.mark.case("PTL-007", "floor safety: several referents or none leave "
                             "the reply untouched; the strip can never empty "
                             "a reply")
def test_ptl007_floor_safety(sandbox):
    tic_reply = SUBSTANCE + " Could you specify which file you mean?"

    # Zero artifact referents: untouched (GND-012's honest-unknown turf).
    eng = _engine(sandbox, [tic_reply])
    reply = eng.respond(ARTIFACT_ASK)
    assert reply.content == tic_reply

    # Two artifact referents: a which-ask may be legitimate — untouched.
    eng = _engine(sandbox, [tic_reply])
    for name in ("wiring_a.md", "wiring_b.md"):
        eng._push_referent({"kind": "file", "name": name, "when": "just now",
                            "summary": "wiring notes", "detail": name})
    reply = eng.respond(ARTIFACT_ASK)
    assert reply.content == tic_reply

    # Pure-clarify reply with no substance: the strip would leave nothing —
    # the floor keeps the original rather than emit an empty reply.
    pure = "Could you specify which file you mean?"
    eng = _seed_artifact_turn(sandbox, [pure, pure])
    reply = eng.respond(ARTIFACT_ASK)
    assert reply.content.strip(), "the floor must never empty a reply"


@pytest.mark.upgrade
@pytest.mark.case("PTL-008", "GT-C9 T3 shape: a generic clarify on a pending "
                             "no-survivor consolidation turn becomes the "
                             "code-built survivor question, no extra model "
                             "call")
def test_ptl008_consolidation_backstop_widened(sandbox):
    from tests.pillar1.test_consolidate import FLUX_SLUGS, _plant_note
    for slug in FLUX_SLUGS:
        _plant_note(sandbox, slug)
    eng = _engine(sandbox, [
        "Here are the flux projects.",
        "Could you please specify which files or folders you would like to "
        "update?",
    ])
    eng.respond("Please consolidate all the projects with flux in the name.")
    assert eng.consolidation is not None
    calls_before = eng.model.calls
    reply = eng.respond("Ok, please update the project folder.")
    assert reply.content.startswith("These all match:")
    assert "shall I go ahead" in reply.content
    assert eng.model.calls == calls_before + 1, \
        "the backstop is code-built — no corrective retry may be spent"


# ---- PT.3: the field-matching floor ---------------------------------------

NOTE_PATH = "projects/sun_dial.md"
NOTE = ("# Sun Dial\n\n- **Status:** active\n- **Load cell:** 20 kg rated\n"
        "- **Gnomon angle:** 53 deg\n\nBench notes.\n")


def _plant_field_note(sandbox):
    sandbox.brain.write_note(NOTE_PATH, NOTE, mode="create",
                             summary="plant sun dial")


@pytest.mark.upgrade
@pytest.mark.case("FLD-001", "a paraphrased field name updates the EXISTING "
                             "line in place, keeping the canonical name")
def test_fld001_fuzzy_update_in_place(sandbox):
    _plant_field_note(sandbox)
    out = sandbox.service.engine.registry.call(
        "update_note_field", {"path": NOTE_PATH, "field": "load cell rating",
                              "value": "50 kg rated"})
    assert "Load cell" in out and not out.startswith("ERROR")
    note = sandbox.note(NOTE_PATH)
    lines = [l for l in note.splitlines() if "oad cell" in l.lower()]
    assert len(lines) == 1, f"contradicting load-cell lines: {lines}"
    assert "50 kg" in lines[0] and "20 kg" not in lines[0]
    assert lines[0].startswith("- **Load cell:**"), \
        "the model's paraphrase must never rename the field"


@pytest.mark.upgrade
@pytest.mark.case("FLD-002", "a genuinely new field still inserts (MEM-020 "
                             "stays green)")
def test_fld002_new_field_inserts(sandbox):
    _plant_field_note(sandbox)
    out = sandbox.service.engine.registry.call(
        "update_note_field", {"path": NOTE_PATH, "field": "Power budget",
                              "value": "3.2 Wh"})
    assert not out.startswith("ERROR")
    note = sandbox.note(NOTE_PATH)
    assert "- **Power budget:** 3.2 Wh" in note
    assert note.count("**Load cell:**") == 1


@pytest.mark.upgrade
@pytest.mark.case("FLD-003", "an ambiguous field name refuses with a "
                             "corrective naming the candidates — and writes "
                             "nothing")
def test_fld003_ambiguity_refusal(sandbox):
    _plant_field_note(sandbox)
    sandbox.service.engine.registry.call(
        "update_note_field", {"path": NOTE_PATH, "field": "Load cell amp",
                              "value": "HX711"})
    before = sandbox.note(NOTE_PATH)
    # 'load' is a strict subset of BOTH existing names — genuinely ambiguous.
    out = sandbox.service.engine.registry.call(
        "update_note_field", {"path": NOTE_PATH, "field": "load",
                              "value": "60 kg"})
    assert out.startswith("ERROR"), out
    assert "'Load cell'" in out and "'Load cell amp'" in out
    assert "retry update_note_field" in out
    assert "never a generic" in out
    assert sandbox.note(NOTE_PATH) == before, "an ambiguous miss must not write"


@pytest.mark.upgrade
@pytest.mark.case("FLD-004", "an exact field name short-circuits the fuzzy "
                             "pass")
def test_fld004_exact_short_circuit(sandbox):
    _plant_field_note(sandbox)
    sandbox.service.engine.registry.call(
        "update_note_field", {"path": NOTE_PATH, "field": "Load cell amp",
                              "value": "HX711"})
    # 'Load cell' exists EXACTLY — despite also being a token-subset of
    # 'Load cell amp', the exact hit wins and no ambiguity refusal fires.
    out = sandbox.service.engine.registry.call(
        "update_note_field", {"path": NOTE_PATH, "field": "load cell",
                              "value": "60 kg rated"})
    assert not out.startswith("ERROR"), out
    note = sandbox.note(NOTE_PATH)
    assert "- **Load cell:** 60 kg rated" in note
    assert "- **Load cell amp:** HX711" in note

    # match_field itself: the MEM-003 shape (extended name + value overlap),
    # the shortened direction, and a clean miss.
    assert match_field(NOTE, "load cell rating", "50 kg rated") == ["Load cell"]
    assert match_field(NOTE, "angle") == ["Gnomon angle"]
    assert match_field(NOTE, "hydraulics", "3 bar") == []


@pytest.mark.upgrade
@pytest.mark.case("FLD-005", "a genuinely NEW sibling field (extended name, "
                             "unrelated value) INSERTS instead of destroying "
                             "the existing line — the MEM-002 collision")
def test_fld005_new_sibling_field_protected(sandbox):
    _plant_field_note(sandbox)
    # The live MEM-002 shape: 'load cell amplifier' extends 'Load cell' but
    # its value shares no vocabulary with '20 kg rated' — a NEW field, not a
    # correction. Plain containment would have overwritten the 20 kg fact.
    out = sandbox.service.engine.registry.call(
        "update_note_field", {"path": NOTE_PATH,
                              "field": "Load cell amplifier",
                              "value": "HX711 board"})
    assert not out.startswith("ERROR"), out
    note = sandbox.note(NOTE_PATH)
    assert "- **Load cell:** 20 kg rated" in note, \
        "the existing fact must survive a new sibling field"
    assert "- **Load cell amplifier:** HX711 board" in note

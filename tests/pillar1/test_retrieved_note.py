r"""
Retrieved-note recall floor guards (armor RETRIEVED-NOTE leg, RN.1 + RN.2).

THE FAILURE (STA-004, root-caused in the RA leg, re-confirmed NJ.6). A recall
question about a REFERENCE project — "what pressure rating is the beta probe
housing?" — where the note ("- **Pressure rating:** 30 bar housing") is already
in context. The model detours to resolve_project, reads a "no folder on disk"
result, and answers with a CREATE-FOLDER OFFER instead of the fact. The offer
displaces the recall answer.

RN.1 (soft): a reference project is a knowledge source with NO working folder by
design, so neither the resolve_project tool result nor the hint_for line should
recommend create_project or frame the absent folder as a gap.
  RNF-001  resolve_project on a reference project → reframes (REFERENCE, answer
           from note), never names create_project.
  RNF-002  resolve_project on a NON-reference folderless project → UNCHANGED
           (still suggests create_project; no regression).
  RNF-003  hint_for on a reference project → reframes, drops the "say the
           missing folder plainly" tail.
  RNF-004  hint_for on a NON-reference resolved project → UNCHANGED.

RN.2 (code floor): a post-generation barrier — a recall QUESTION resolved to a
reference project whose note is in context, whose reply OFFERS to create a
folder, is regenerated once (tool-free) into an answer from the note.
  RNF-005  reference recall + create-offer draft → regenerated to the note
           answer; the ilog retrieved_note_floor flag is True.
  RNF-006  a genuine CREATE REQUEST ("can you create a folder…?") → floor never
           fires (obedience, not displacement).
  RNF-007  a reference recall whose draft ALREADY answers → floor quiet,
           byte-identical (only one model call).
  RNF-008  a NON-reference (active) project recall with a create-offer draft →
           floor quiet (only reference projects are floored).
  RNF-009  the detector regexes / _is_recall_question behave as specified.
  RNF-010  best-effort acceptance: a retry that STILL offers to create is
           rejected, the original draft is kept, the flag stays False.
"""

import pytest

from core.model import ModelReply

# The beta_probe reference project (status reference, "30 bar housing" fact) is
# seeded by the sandbox fixture (SEED_PROJECTS), so these turns exercise the
# real resolver + retriever + barrier with no extra planting.
RECALL = "Quick question - what pressure rating is the beta probe housing?"


class _ScriptModel:
    """Scripted replies in order (the test_narrated_json / test_consolidate
    pattern). A barrier that regenerates consumes the next scripted reply."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        item = self.script.pop(0) if self.script else ""
        r = ModelReply()
        r.content = item if isinstance(item, str) else item.get("content", "")
        r.tool_calls = [] if isinstance(item, str) else list(item.get("tool_calls", []))
        r.eval_count = 5
        return r


def _engine(sandbox, script, capture=None):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    if capture is not None:
        eng.ilog.log = lambda d: capture.append(d)
    return eng


# A draft that DODGES a recall by offering to make a folder (the STA-004 shape
# before RN.1 removed the create steer).
OFFER_DRAFT = ("I don't see a working folder for the Beta Probe project. "
               "Would you like me to create one so we can track it?")
# The dodge that REPLACED the create-offer after RN.1 — narrates the reference
# project's metadata and asks for more details instead of answering (measured
# live, STA-004 diagnostic runs 4/5).
META_DODGE = ("The 'Beta Probe' project is in reference status and does not "
              "have an associated working folder. If you need any specific "
              "information, please provide more details so I can assist.")
# A bare DENIAL that ignores the retrieved note entirely (measured live, run 6):
# no tools, "I don't have access", punts back to Jack.
DENIAL_DODGE = ("I don't have direct access to specific documents unless "
                "you've stored this in our brain. Could you remind me where we "
                "might find this detail, such as a particular project folder?")
# A tool-error narration (measured live, run 3): the model botched a tool call,
# narrates the error, and asks for the path instead of answering.
TOOLERR_DODGE = ("It seems there was an error in the function call. Could you "
                 "please provide me with the path of the note you'd like read?")
# The answer that should replace any of them — states the fact, mentions no
# folder, no meta, no punt.
ANSWER = "The Beta Probe housing is rated to 30 bar."


# ---------------- RN.1: reference-project reframe (tool + hint) ----------------

@pytest.mark.upgrade
@pytest.mark.case("RNF-001", "resolve_project on a REFERENCE project reframes "
                             "(no create_project suggestion)")
def test_rnf001_tool_reference_no_create(sandbox):
    out = sandbox.service.engine.registry.call("resolve_project",
                                               {"name": "beta probe"})
    assert "REFERENCE project" in out, out
    assert "create_project" not in out, out
    assert "note content" in out.lower(), out
    # The knowledge itself is surfaced — the detour now gets the fact, not just
    # metadata (the RN.4 root-cause fix).
    assert "30 bar" in out, out


@pytest.mark.upgrade
@pytest.mark.case("RNF-002", "resolve_project on a NON-reference folderless "
                             "project still suggests create_project")
def test_rnf002_tool_nonreference_keeps_create(sandbox):
    # gamma_arm is 'side-interest' status with no folder — a genuine create
    # candidate, so the create suggestion must survive RN.1.
    out = sandbox.service.engine.registry.call("resolve_project",
                                               {"name": "gamma arm"})
    assert "create_project" in out, out
    assert "REFERENCE project" not in out, out


@pytest.mark.upgrade
@pytest.mark.case("RNF-003", "hint_for on a REFERENCE project reframes and "
                             "drops the missing-folder-is-a-gap tail")
def test_rnf003_hint_reference_reframe(sandbox):
    hint = sandbox.service.engine.project_resolver.hint_for(RECALL)
    assert "REFERENCE project" in hint, hint
    assert "answer directly from its note" in hint.lower(), hint
    # The generic "say that plainly rather than inventing a location" tail must
    # NOT ride on a reference project — it is what framed the absent folder as
    # a gap to report.
    assert "say that plainly" not in hint.lower(), hint


@pytest.mark.upgrade
@pytest.mark.case("RNF-004", "hint_for on a NON-reference resolved project is "
                             "unchanged (still 'use this note and folder')")
def test_rnf004_hint_nonreference_unchanged(sandbox):
    # alpha_rig is active — the standard resolution hint should be intact.
    hint = sandbox.service.engine.project_resolver.hint_for(
        "what does the alpha rig load cell do?")
    assert "Use this note and folder DIRECTLY" in hint, hint
    assert "REFERENCE project" not in hint, hint


# ---------------- RN.2: the post-generation recall floor ----------------------

@pytest.mark.upgrade
@pytest.mark.case("RNF-005", "reference recall + create-offer draft → "
                             "regenerated to the note answer; flag True")
def test_rnf005_floor_regenerates(sandbox):
    cap = []
    eng = _engine(sandbox, [OFFER_DRAFT, ANSWER], capture=cap)
    out = eng.respond(RECALL)
    assert "30" in out.content, out.content
    assert "create one" not in out.content.lower(), out.content
    assert eng.model.calls == 2, "the barrier should have regenerated once"
    assert cap[-1]["retrieved_note_floor"] is True, cap[-1]


@pytest.mark.upgrade
@pytest.mark.case("RNF-005b", "the META-DODGE shape (reference metadata + "
                              "'provide more details') is also floored")
def test_rnf005b_metadata_dodge_floored(sandbox):
    cap = []
    eng = _engine(sandbox, [META_DODGE, ANSWER], capture=cap)
    out = eng.respond(RECALL)
    assert "30" in out.content, out.content
    assert "working folder" not in out.content.lower(), out.content
    assert eng.model.calls == 2, "the barrier should have regenerated once"
    assert cap[-1]["retrieved_note_floor"] is True, cap[-1]


@pytest.mark.upgrade
@pytest.mark.case("RNF-005c", "the bare DENIAL shape ('I don't have access') "
                              "is floored")
def test_rnf005c_denial_floored(sandbox):
    cap = []
    eng = _engine(sandbox, [DENIAL_DODGE, ANSWER], capture=cap)
    out = eng.respond(RECALL)
    assert "30" in out.content, out.content
    assert eng.model.calls == 2
    assert cap[-1]["retrieved_note_floor"] is True, cap[-1]


@pytest.mark.upgrade
@pytest.mark.case("RNF-005d", "the tool-error narration shape is floored")
def test_rnf005d_toolerror_floored(sandbox):
    cap = []
    eng = _engine(sandbox, [TOOLERR_DODGE, ANSWER], capture=cap)
    out = eng.respond(RECALL)
    assert "30" in out.content, out.content
    assert eng.model.calls == 2
    assert cap[-1]["retrieved_note_floor"] is True, cap[-1]


@pytest.mark.upgrade
@pytest.mark.case("RNF-006", "a genuine create REQUEST is never overridden by "
                             "the floor")
def test_rnf006_create_request_not_floored(sandbox):
    cap = []
    # A question in FORM, but an explicit ask to create — obedience, not a
    # recall the floor should hijack.
    eng = _engine(sandbox, [OFFER_DRAFT, ANSWER], capture=cap)
    out = eng.respond("Can you create a folder for the beta probe project?")
    assert out.content == OFFER_DRAFT, out.content
    assert eng.model.calls == 1, "no regeneration on a create request"
    assert cap[-1]["retrieved_note_floor"] is False, cap[-1]


@pytest.mark.upgrade
@pytest.mark.case("RNF-007", "a reference recall whose draft already answers → "
                             "floor quiet, byte-identical")
def test_rnf007_already_answered_quiet(sandbox):
    cap = []
    eng = _engine(sandbox, [ANSWER, "SHOULD-NOT-BE-USED"], capture=cap)
    out = eng.respond(RECALL)
    assert out.content == ANSWER, out.content
    assert eng.model.calls == 1, "no regeneration when the draft already answers"
    assert cap[-1]["retrieved_note_floor"] is False, cap[-1]


@pytest.mark.upgrade
@pytest.mark.case("RNF-008", "a NON-reference (active) project recall with a "
                             "create-offer draft is not floored")
def test_rnf008_nonreference_not_floored(sandbox):
    cap = []
    eng = _engine(sandbox, [OFFER_DRAFT, ANSWER], capture=cap)
    out = eng.respond("what load cell is the alpha rig using?")
    assert out.content == OFFER_DRAFT, out.content
    assert eng.model.calls == 1, "active projects are not reference-floored"
    assert cap[-1]["retrieved_note_floor"] is False, cap[-1]


@pytest.mark.upgrade
@pytest.mark.case("RNF-009", "fact-token extraction and the request/question "
                             "detectors classify as specified")
def test_rnf009_detectors(sandbox):
    eng = sandbox.service.engine
    body = sandbox.brain.read_note("projects/beta_probe.md")
    toks = eng._note_fact_tokens(body, RECALL)
    # The distinctive answer token survives; question-echo and structural words
    # do not (they must not read as an "answer").
    assert "30" in toks, toks
    for echoed in ("pressure", "rating", "beta", "probe", "housing"):
        assert echoed not in toks, (echoed, toks)  # in the question
    for meta in ("folder", "reference", "status", "note"):
        assert meta not in toks, (meta, toks)      # structural
    # Every measured dodge shape carries NONE of the fact tokens; the answer
    # carries one.
    assert any(t in ANSWER.lower() for t in toks)
    for dodge in (OFFER_DRAFT, META_DODGE, DENIAL_DODGE, TOOLERR_DODGE):
        assert not any(t in dodge.lower() for t in toks), dodge
    # The create-REQUEST and recall-question gates are unchanged.
    assert eng._CREATE_REQUEST.search("create a folder for beta probe")
    assert eng._CREATE_REQUEST.search("add these files to the beta probe project")
    assert not eng._CREATE_REQUEST.search(RECALL)
    assert eng._is_recall_question(RECALL)
    assert eng._is_recall_question("Which housing rating did we record?")
    assert not eng._is_recall_question("Create a folder for beta probe.")


@pytest.mark.upgrade
@pytest.mark.case("RNF-010", "best-effort acceptance: a retry that still "
                             "offers to create is rejected, original kept")
def test_rnf010_best_effort_rejects_bad_retry(sandbox):
    cap = []
    still_offering = ("Actually, I should set up a folder for it first — "
                      "shall I create one?")
    eng = _engine(sandbox, [OFFER_DRAFT, still_offering], capture=cap)
    out = eng.respond(RECALL)
    # The barrier fired (regenerated) but the retry was no better, so the
    # original draft is kept rather than shipping a worse one.
    assert out.content == OFFER_DRAFT, out.content
    assert eng.model.calls == 2, "the barrier regenerated once"
    assert cap[-1]["retrieved_note_floor"] is False, cap[-1]

r"""
IG-leg guards (armor plan §6, "M2 batch" / IG leg): code-only, no live model.

IDG-001..007  the foreign-note-path floor (IG.1, parity row P3): while
        project context is live (or a task pending), a reply naming a note
        file code can ground NOWHERE — not on disk, not in a tool result
        this turn, not in Jack's own words this session, not on the
        referent stack — is retried once against the real listing, then
        replaced by the honest deterministic listing (CN.3's fallback
        shape). Grounded paths, Jack-named paths, tool-surfaced paths,
        fenced-block paths and no-context turns never trip.

ADJ-001..002  the CN.3 verb-adjacency window (IG.2, the GAP-001 live
        specimen from candidate 2026-07-18_1851): quoted technical jargon
        in an ordinary answer no longer scans as a project identifier —
        only quotes with project vocabulary within ±60 chars are
        identifier-shaped. Measured fabrication shapes (merge-adjacent)
        still trip.
"""

import pytest

from core.model import ModelReply


class _ScriptModel:
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


def _eng(sandbox, script):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    return eng


def _plant_flux(sandbox):
    for slug in ("fluxbeam", "flux_beam_tool", "flux_beam_v2"):
        sandbox.brain.write_note(
            f"projects/{slug}.md",
            f"# {slug.replace('_', ' ').title()}\n\n- **Status:** active\n\n"
            "Flux beam tooling.\n",
            mode="create", summary=f"plant {slug}")


def _armed(sandbox, script):
    """Merge ask arms the consolidation ledger -> project context live."""
    _plant_flux(sandbox)
    eng = _eng(sandbox, ["Here are the flux projects — shall I merge them?"])
    eng.respond("Please consolidate all the projects with flux in the name.")
    eng.model.script = list(script)
    return eng


# ---------------------------------------------------------------------------
# IDG — foreign-note-path floor (IG.1)
# ---------------------------------------------------------------------------

@pytest.mark.upgrade
@pytest.mark.case("IDG-001", "invented note path in project context -> "
                             "retry; clean retry accepted")
def test_idg001_invented_path_retried(sandbox):
    eng = _armed(sandbox, [
        "I've noted the plan in projects/flux_consolidated.md.",
        "The candidates are in projects/fluxbeam.md — nothing new was "
        "created yet.",
    ])
    eng.respond("How's the flux cleanup going?")
    final = eng.history[-1]["content"]
    assert "flux_consolidated.md" not in final, final
    assert "fluxbeam.md" in final, final


@pytest.mark.upgrade
@pytest.mark.case("IDG-002", "retry still foreign -> honest deterministic "
                             "listing, reply never emptied")
def test_idg002_fallback_listing(sandbox):
    eng = _armed(sandbox, [
        "I've noted the plan in projects/flux_consolidated.md.",
        "Right — see projects/flux_master_plan.md.",
    ])
    eng.respond("How's the flux cleanup going?")
    final = eng.history[-1]["content"]
    assert final.strip(), "reply emptied"
    assert "mis-named" in final and "projects/fluxbeam.md" in final, final


@pytest.mark.upgrade
@pytest.mark.case("IDG-003", "real on-disk path -> floor silent")
def test_idg003_real_path_silent(sandbox):
    draft = "The survivor note is projects/fluxbeam.md; the others fold in."
    eng = _armed(sandbox, [draft])
    eng.respond("How's the flux cleanup going?")
    assert eng.history[-1]["content"] == draft


@pytest.mark.upgrade
@pytest.mark.case("IDG-004", "tool-surfaced and Jack-named paths are "
                             "grounded even when absent from disk (helper "
                             "semantics)")
def test_idg004_grounding_sources(sandbox):
    eng = _eng(sandbox, [])
    # Tool-surfaced: the result names a path that does not exist on disk.
    tl = [{"tool": "search_brain", "args": {},
           "result": "[inbox/idea_dump.md] draft thoughts"}]
    assert eng._foreign_note_paths(
        "See inbox/idea_dump.md for the draft.", "any message", tl) == []
    # Jack-named (this turn's message): a to-be-created path never trips.
    assert eng._foreign_note_paths(
        "I'll set up inbox/new_bench_log.md as you asked.",
        "Please create inbox/new_bench_log.md for the bench notes.",
        []) == []
    # Ungrounded: same shape with no source -> foreign.
    assert eng._foreign_note_paths(
        "See inbox/idea_dump.md for the draft.", "any message", []) \
        == ["inbox/idea_dump.md"]


@pytest.mark.upgrade
@pytest.mark.case("IDG-005", "fenced-block paths are never scanned (NJ.2's "
                             "territory)")
def test_idg005_fenced_exempt(sandbox):
    eng = _eng(sandbox, [])
    text = ("Running this now:\n```json\n"
            '{"tool": "write_brain", "path": "inbox/made_up_note.md"}\n```')
    assert eng._foreign_note_paths(text, "msg", []) == []


@pytest.mark.upgrade
@pytest.mark.case("IDG-006", "no project context and no pending task -> "
                             "scan never runs")
def test_idg006_no_context_silent(sandbox):
    draft = "Fun fact, I keep ideas in inbox/imaginary_scratchpad.md."
    eng = _eng(sandbox, [draft])
    eng.respond("Tell me something about how you organise yourself.")
    assert eng.history[-1]["content"] == draft
    assert len(eng.model.seen) == 1, "a retry was burned without context"


@pytest.mark.upgrade
@pytest.mark.case("IDG-007", "session history grounds a path from an "
                             "earlier turn (helper semantics)")
def test_idg007_history_grounds(sandbox):
    eng = _eng(sandbox, ["Noted."])
    eng.respond("The bench log lives at inbox/bench_log.md, remember that.")
    assert eng._foreign_note_paths(
        "As you said, inbox/bench_log.md has the log.", "later message",
        []) == []


# ---------------------------------------------------------------------------
# ADJ — CN.3 verb-adjacency window (IG.2, the GAP-001 specimen)
# ---------------------------------------------------------------------------

@pytest.mark.upgrade
@pytest.mark.case("ADJ-001", "quoted design jargon far from project "
                             "vocabulary no longer scans as an identifier "
                             "(the GAP-001 false-positive specimen)")
def test_adj001_jargon_exempt(sandbox):
    _plant_flux(sandbox)
    eng = sandbox.service.engine
    text = ("To hit the backlash target, use 'preload' on the output stage "
            "and check tooth engagement across the mesh cycle.")
    assert eng._foreign_identifiers(text) == []


@pytest.mark.upgrade
@pytest.mark.case("ADJ-002", "fabricated quote adjacent to merge vocabulary "
                             "still trips (CN.3 regression edge)")
def test_adj002_fabrication_still_trips(sandbox):
    _plant_flux(sandbox)
    eng = sandbox.service.engine
    text = ("I suggest merging 'flux-beam-utils' into 'fluxbeam' and "
            "keeping the rest.")
    assert eng._foreign_identifiers(text) == ["flux-beam-utils"]

r"""
Narrated-tool-JSON floor guards (armor NARRATED-JSON leg, NJ.2).

The theme-1 envelope failure, measured live: the 14B writes the CORRECT tool
call as prose — a ```json fence or a python-style call with the right
arguments — and ends the turn with zero tools run (GT-C9 mode B T7, stamp
2026-07-16_1750: two update_note_field JSON objects narrated back-to-back;
GT-C9 stamp 2026-07-15_1548: merge_projects narrated in a python fence with
exact args). Shape D can't recover these (required args put them outside its
deliberately-restricted, no-fabrication recovery), so the ENGINE executes the
narrated call itself: the model authored every argument, code fixes only the
envelope. Everything runs through _run_tool, so gate, taint and referent
tracking apply exactly as if the model had used the native envelope.

NJF-001  json fence + execute cue -> executed; result appended CN.4-style
         (narration preserved, never replaced), disk shows the write.
NJF-002  python-style call fence ("Calling merge_projects...") -> executed.
NJF-003  EXAMPLE fence — no execute cue before it, prose after it -> byte-
         identical reply, nothing runs, nothing on disk (exposition is not
         intent; the floor must not turn documentation into action).
NJF-004  fence naming an unknown tool -> quiet.
NJF-005  fence missing a required argument -> quiet (no fabrication, ever).
NJF-006  a tool already ran this turn -> quiet (the promise was kept).
NJF-007  the mode-B T7 shape verbatim: TWO json fences with PARAPHRASED
         argument keys (note_path/field_name/new_value for path/field/value)
         -> both executed via the PT.3-style asymmetric key remap; ambiguity
         would drop the call, one clean hit per key remaps it.
"""

import pytest

from core.model import ModelReply

FLUX_SLUGS = ("fluxbeam", "flux_beam_tool", "flux_beam_v2")


class _ScriptModel:
    """Scripted replies in order (the test_consolidate pattern)."""

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


def _plant_note(sandbox, slug, title=None):
    title = title or slug.replace("_", " ").title()
    sandbox.brain.write_note(
        f"projects/{slug}.md",
        f"# {title}\n\n- **Status:** active\n\nFlux beam tooling.\n",
        mode="create", summary=f"seed {slug}")


def _engine(sandbox, script):
    for slug in FLUX_SLUGS:
        _plant_note(sandbox, slug)
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    return eng


def _note(sandbox, slug):
    return sandbox.brain.read_note(f"projects/{slug}.md")


@pytest.mark.upgrade
@pytest.mark.case("NJF-001", "narrated json fence with execute cue is "
                             "EXECUTED by the engine; result appended, "
                             "narration preserved, write lands on disk")
def test_njf001_json_fence_executes(sandbox):
    narration = "Let me proceed with this update now."
    reply = (narration + "\n```json\n"
             '{"tool": "update_note_field", "arguments": {'
             '"path": "projects/flux_beam_tool.md", '
             '"field": "Status", "value": "merged into Fluxbeam"}}\n```')
    eng = _engine(sandbox, [reply])
    out = eng.respond("Set the tool project's status for me, please.")
    assert out.content.startswith(narration), out.content  # append, not replace
    assert "Updated Status" in out.content, out.content    # the real result
    assert "merged into Fluxbeam" in _note(sandbox, "flux_beam_tool")


@pytest.mark.upgrade
@pytest.mark.case("NJF-002", "narrated python-style call ('Calling "
                             "merge_projects...') is executed with the "
                             "model-authored keyword args")
def test_njf002_python_call_executes(sandbox):
    reply = ("Calling merge_projects with the confirmed survivor.\n"
             "```python\nmerge_projects(target='fluxbeam', "
             "duplicates=['flux_beam_tool', 'flux_beam_v2'])\n```")
    eng = _engine(sandbox, [reply])
    eng.respond("Fold the duplicates into fluxbeam now.")
    for slug in ("flux_beam_tool", "flux_beam_v2"):
        assert "merged into" in _note(sandbox, slug).lower(), slug


@pytest.mark.upgrade
@pytest.mark.case("NJF-003", "an EXAMPLE fence (no execute cue, prose "
                             "continues after it) never fires — exposition "
                             "is not intent")
def test_njf003_example_fence_quiet(sandbox):
    reply = ("You could consolidate them like this:\n```json\n"
             '{"tool": "merge_projects", "arguments": {"target": "fluxbeam", '
             '"duplicates": ["flux_beam_tool"]}}\n```\n'
             "Just say the word and I'd be happy to help.")
    eng = _engine(sandbox, [reply])
    out = eng.respond("How would that work?")
    assert out.content == reply, out.content               # byte-identical
    assert "merged into" not in _note(sandbox, "flux_beam_tool").lower()


@pytest.mark.upgrade
@pytest.mark.case("NJF-004", "a fence naming an UNKNOWN tool never fires")
def test_njf004_unknown_tool_quiet(sandbox):
    reply = ("Let me proceed with the sync now.\n```json\n"
             '{"tool": "sync_widgets", "arguments": {"target": "fluxbeam"}}'
             "\n```")
    eng = _engine(sandbox, [reply])
    out = eng.respond("Sync it, please.")
    assert out.content == reply, out.content


@pytest.mark.upgrade
@pytest.mark.case("NJF-005", "a narrated call MISSING a required argument "
                             "never fires — the floor fixes envelopes, it "
                             "never fabricates values")
def test_njf005_missing_required_quiet(sandbox):
    reply = ("Let me proceed with this update now.\n```json\n"
             '{"tool": "update_note_field", "arguments": {'
             '"path": "projects/flux_beam_tool.md", "field": "Status"}}\n```')
    eng = _engine(sandbox, [reply])
    out = eng.respond("Set the status for me.")
    assert out.content == reply, out.content
    assert "merged" not in _note(sandbox, "flux_beam_tool").lower()


@pytest.mark.upgrade
@pytest.mark.case("NJF-006", "a turn where a tool already RAN stays quiet "
                             "even if the tail narrates a call")
def test_njf006_tools_ran_quiet(sandbox):
    tail = ("Here they are. Let me proceed with this update now.\n```json\n"
            '{"tool": "update_note_field", "arguments": {'
            '"path": "projects/flux_beam_tool.md", '
            '"field": "Status", "value": "merged into Fluxbeam"}}\n```')
    eng = _engine(sandbox, [
        {"content": "", "tool_calls": [
            {"function": {"name": "list_projects", "arguments": {}}}]},
        tail])
    out = eng.respond("What flux projects do we have?")
    assert out.content == tail, out.content
    assert "merged" not in _note(sandbox, "flux_beam_tool").lower()


@pytest.mark.upgrade
@pytest.mark.case("NJF-007", "the mode-B T7 shape: two json fences with "
                             "PARAPHRASED keys (note_path/field_name/"
                             "new_value) both execute via the asymmetric "
                             "key remap")
def test_njf007_two_fences_key_remap(sandbox):
    reply = ("Let me proceed with this consolidation now.\n```json\n"
             '{"action": "update_note_field", '
             '"note_path": "projects/flux_beam_tool.md", '
             '"field_name": "Status", "new_value": "merged into fluxbeam"}'
             "\n```\nAnd the second note:\n```json\n"
             '{"action": "update_note_field", '
             '"note_path": "projects/flux_beam_v2.md", '
             '"field_name": "Status", "new_value": "merged into fluxbeam"}'
             "\n```")
    eng = _engine(sandbox, [reply])
    out = eng.respond("Yes, go ahead.")
    for slug in ("flux_beam_tool", "flux_beam_v2"):
        assert "merged into fluxbeam" in _note(sandbox, slug).lower(), slug
    assert out.content.startswith("Let me proceed"), out.content

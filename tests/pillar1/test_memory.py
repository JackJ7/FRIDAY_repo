r"""MEM — memory: write/retrieve, corrections, durability under hard kill."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from helpers.harness import SEED_PROJECTS, repeat_behavior


@pytest.mark.case("MEM-001", "a stated durable fact is committed to the brain (persisted)")
@pytest.mark.model
def test_fact_written(sandbox, detail):
    # Assert on PERSISTENCE, not on a main-turn tool call. Durable facts are
    # designed to commit in the post-reply memory pass, whose writes surface via
    # on_memory (rec.memory_writes / brain.on_write) — NOT via on_tool
    # (rec.tool_names, main turn only). The old assertion checked tool_names and
    # so failed whenever she correctly deferred the write to the memory pass.
    reply = sandbox.ask("For the record: the alpha rig's frame is 2020 aluminum extrusion.")
    detail["reply"] = reply[:400]
    detail["tools"] = sandbox.rec.tool_names()
    detail["memory_writes"] = sandbox.rec.memory_writes
    assert sandbox.rec.memory_writes, "no brain write was recorded (fact not committed)"
    everything = "\n".join(sandbox.note(rel) for rel in sandbox.brain.list_notes())
    assert "2020" in everything, "fact not found in any brain note"


@pytest.mark.case("MEM-002", "a stated fact survives a service restart (fresh instance recalls it)")
@pytest.mark.model
def test_restart_recall(sandbox, detail):
    sandbox.ask("Note this down: the alpha rig's load cell amplifier is an HX711 board.")
    sandbox.restart()
    reply = sandbox.ask("What amplifier board does the alpha rig's load cell use?")
    detail["reply"] = reply[:400]
    assert "hx711" in reply.lower(), "fact lost across restart"


@pytest.mark.case("MEM-003", "a correction UPDATES the authoritative note in place (no contradiction left)")
@pytest.mark.model
def test_correction_in_place(sandbox, detail):
    reply = sandbox.ask("Correction: the alpha rig's load cell is 50 kg rated, "
                        "not 20 kg - we upgraded it. Fix your note.")
    note = sandbox.note("projects/alpha_rig.md")
    detail["reply"] = reply[:300]
    detail["note_after"] = note
    lines = [l for l in note.splitlines() if "oad cell" in l.lower()]
    assert len(lines) == 1, f"contradicting load-cell lines: {lines}"
    assert "50" in lines[0] and "20 kg" not in lines[0], f"not corrected: {lines[0]}"


@pytest.mark.case("MEM-004", "a pure question commits nothing to memory")
@pytest.mark.model
def test_question_writes_nothing(sandbox, detail):
    sandbox.ask("What's the pressure rating on the beta probe housing?")
    detail["memory_writes"] = sandbox.rec.memory_writes
    assert sandbox.rec.memory_writes == [], \
        f"question caused writes: {sandbox.rec.memory_writes}"


@pytest.mark.case("MEM-005", "hard-kill durability: a stated status change survives "
                             "process murder at main-turn completion (every project)")
@pytest.mark.model
@pytest.mark.parametrize("project", list(SEED_PROJECTS))
def test_hard_kill_durability(sandbox, project, detail):
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).parents[1] / "helpers" / "kill_child.py"),
         str(sandbox.config_path), project],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tools = []
    for line in child.stdout:
        line = line.strip()
        if line.startswith("TOOL"):
            tools.append(line)
        if line == "MAIN_TURN_DONE":
            child.kill()   # TerminateProcess — Task Manager equivalent
            break
        if line.startswith("ERR"):
            child.kill()
            pytest.fail(f"child errored: {line}")
    child.wait(timeout=15)
    detail["child_tools"] = tools

    from core.project_meta import project_status
    status = project_status(sandbox.note(f"projects/{project}.md"))
    detail["status_after_kill"] = status
    assert status == "archived", \
        f"{project}: status change lost to hard kill (read '{status}')"


@pytest.mark.case("MEM-006", "keyword retrieval surfaces a field fact stored in a note")
def test_retrieval_finds_fact(sandbox):
    hits = sandbox.service.engine.retriever.retrieve("beta probe pressure rating", 4)
    assert hits and any("30 bar" in h.snippet for h in hits), \
        [f"{h.path}: {h.snippet[:60]}" for h in hits]


@pytest.mark.case("MEM-012", "relevance floor: a weak incidental match is dropped, a strong one survives (Phase 1, Symptom 6)")
def test_retrieval_floor(tmp_path):
    from core.memory.keyword_retriever import KeywordRetriever
    brain = tmp_path / "brain"
    brain.mkdir()
    # 'meeting' appears exactly ONCE, incidentally — the weak-match shape that
    # used to be served as fact (the office-hours-for-a-meeting confabulation).
    (brain / "office.md").write_text(
        "# Office\n- Dr. Reyes office hours; drop in, no meeting needed.\n",
        encoding="utf-8")
    # A note squarely about the query (term repeated).
    (brain / "nimbus.md").write_text(
        "# Nimbus\n- The Nimbus team sync is the weekly sync meeting; "
        "meeting runs 30 min.\n", encoding="utf-8")

    floored = KeywordRetriever(brain, min_score=2.0)
    paths = [h.path for h in floored.retrieve("when is the meeting", 4)]
    assert "nimbus.md" in paths, paths       # strong match survives
    assert "office.md" not in paths, paths    # weak incidental match dropped

    # Floor off -> the weak match returns, proving the floor is what dropped it.
    off = KeywordRetriever(brain, min_score=0.0)
    assert "office.md" in [h.path for h in off.retrieve("when is the meeting", 4)]


@pytest.mark.case("MEM-007", "update_note_field replaces exactly one line, never duplicates")
def test_update_note_field(sandbox):
    sandbox.service.engine.registry.call("update_note_field", {
        "path": "projects/alpha_rig.md", "field": "Load cell", "value": "50 kg rated"})
    note = sandbox.note("projects/alpha_rig.md")
    assert note.count("**Load cell:**") == 1 and "50 kg rated" in note


@pytest.mark.case("MEM-008", "every durable brain write fires the memory event (glyph hook)")
def test_memory_event_fires(sandbox):
    sandbox.brain.write_note("inbox/event_test.md", "# T\n\nx\n")
    assert "inbox/event_test.md" in sandbox.rec.memory_writes


@pytest.mark.case("MEM-009", "brain writes are write-through: on disk + git-committed on return")
def test_write_through(sandbox):
    sandbox.brain.write_note("inbox/durable.md", "# D\n\npersisted\n",
                             summary="durability check")
    assert "persisted" in sandbox.note("inbox/durable.md")
    assert "durability check" in sandbox.git_log(), "write returned before git commit"


@pytest.mark.case("MEM-010", "one fact, one place: memory pass never leaves conflicting field values")
@pytest.mark.model
def test_no_contradiction_after_pass(sandbox, detail):
    sandbox.ask("The alpha rig load cell got swapped again - it's 100 kg rated now. Update it.")
    note = sandbox.note("projects/alpha_rig.md")
    detail["note_after"] = note
    assert note.count("**Load cell:**") <= 1, "duplicate field lines after correction"


@pytest.mark.case("MEM-011", "narrated tool calls (written as text, not called) are recovered and run")
def test_recover_narrated_tool_calls(sandbox):
    """Deterministic, no model. qwen intermittently writes a tool call as TEXT
    with an empty tool_calls list, silently dropping the action (the MEM-001
    write loss). The engine recovers such calls from the reply text and runs
    them for real. This locks the parser in."""
    eng = sandbox.service.engine

    # A save narrated as text — including nested braces in the content field.
    narrated = ('Noted.\n\nwrite_brain({"path": "inbox/rec.md", "content": '
                '"# Rec\\n- **Frame:** 2020 extrusion {v2}", "mode": "create", '
                '"summary": "frame"})\n\nDone.')
    calls = eng._recover_tool_calls(narrated)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "write_brain"
    assert calls[0]["function"]["arguments"]["path"] == "inbox/rec.md"

    # Shape B: the raw call envelope in a ```json block (qwen does this a lot).
    envelope = ('Tracking that.\n\n```json\n{"name": "track_commitment", '
                '"arguments": {"text": "order motors", "inferred": true}}\n```')
    ecalls = eng._recover_tool_calls(envelope)
    assert len(ecalls) == 1 and ecalls[0]["function"]["name"] == "track_commitment"
    assert ecalls[0]["function"]["arguments"]["text"] == "order motors"

    # Shape C: Python call syntax with positional literals — the exact reply
    # the friday-tuned-v1 eval produced on 15 golden math cases (correct
    # expression, emitted as text, action dropped). Positional args must map
    # to the schema's parameter order, and parens INSIDE the string must not
    # confuse the call-end scan.
    ccalls = eng._recover_tool_calls("calc('12 V / (4 ohm)', 'A')")
    assert len(ccalls) == 1 and ccalls[0]["function"]["name"] == "calc"
    assert ccalls[0]["function"]["arguments"] == {
        "expression": "12 V / (4 ohm)", "to_unit": "A"}
    # Keyword form and a single positional arg both recover.
    kcalls = eng._recover_tool_calls('calc(expression="5 kg * 9.81 m/s**2")')
    assert kcalls[0]["function"]["arguments"] == {
        "expression": "5 kg * 9.81 m/s**2"}
    assert eng._recover_tool_calls('calc("2.5 in", "mm")')[0]["function"][
        "arguments"]["to_unit"] == "mm"

    # Ordinary prose that merely mentions a tool name must NOT trigger a call.
    assert eng._recover_tool_calls(
        "I could use write_brain to save this if you'd like.") == []
    # Unknown tool names are ignored even with JSON args (both shapes).
    assert eng._recover_tool_calls('nonexistent_tool({"x": 1})') == []
    assert eng._recover_tool_calls('{"name": "nope", "arguments": {"x": 1}}') == []
    # Shape C rejections: the scaffold's own placeholder form, a bare call,
    # non-literal args, unknown keywords, more args than parameters, and an
    # unterminated call (no closing paren) — all left alone, never mis-fired.
    assert eng._recover_tool_calls("never write a calc(...) call as text") == []
    assert eng._recover_tool_calls("calc()") == []
    assert eng._recover_tool_calls("calc(voltage / resistance, 'A')") == []
    assert eng._recover_tool_calls("calc(bogus_kw='x')") == []
    assert eng._recover_tool_calls("calc('a', 'b', 'c')") == []
    assert eng._recover_tool_calls("calc('12 V / (4 ohm)', 'A'") == []

    # End to end: recovered narrated call actually persists to the brain.
    for tc in calls:
        eng._run_tool(tc["function"]["name"], tc["function"]["arguments"])
    assert "2020 extrusion" in sandbox.note("inbox/rec.md")
    # ... and the recovered Shape-C calc actually computes, units and all.
    result, _ = eng._run_tool(ccalls[0]["function"]["name"],
                              ccalls[0]["function"]["arguments"])
    assert result.strip() == "= 3 A"

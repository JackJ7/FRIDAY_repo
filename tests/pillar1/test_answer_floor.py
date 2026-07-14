r"""
ANS — the ANSWER-contract floor (armor A1 / F2).

When Jack's message carries an explicit `ANSWER:` output contract and the
settled reply lacks the line, the engine floors it: build the line
deterministically from the last successful `calc` result, else regenerate
once, else fail honestly. A produced ANSWER line is NEVER rewritten — a wrong
value must fail honestly (that's F3's territory, not this floor's).

Pure logic (no live model): a scripted stub stands in for the model so every
branch is proven deterministically, through the real respond() path — the
same posture as the compaction tests.
"""

import pytest

from core.model import ModelReply
from helpers.extract import answer


class _ScriptModel:
    """Returns scripted replies in order; records every call. Content-only
    scripts are enough — tool calls are exercised via the engine's narrated-
    call recovery (a real production path), not by faking the channel."""

    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        r = ModelReply()
        r.content = self.contents.pop(0) if self.contents else ""
        r.eval_count = 5
        return r


def _scripted(sandbox, contents):
    eng = sandbox.service.engine
    eng.model = _ScriptModel(contents)
    # Isolate the floor under test: A6 voting also arms on ANSWER: turns and
    # would pop extra scripted replies (desynchronizing the script) — voting
    # has its own guards in test_armor_floors.py.
    eng.vote_enabled = False
    return eng


@pytest.mark.case("ANS-001", "trigger + line builder: literal ANSWER: token arms the floor; the line comes from the LAST successful calc and parses via the real extractor")
def test_trigger_and_builder(sandbox):
    eng = sandbox.service.engine

    # Trigger is the literal upper-case token — prose 'answer:' never arms it.
    assert eng._ANSWER_DIRECTIVE.search("End with ANSWER: <number> <unit>")
    assert not eng._ANSWER_DIRECTIVE.search("give me the answer: now")
    # The presence check is tolerant the way the extractor is — a produced
    # 'Answer: 3 A' satisfies the contract and must not be doubled.
    assert eng._ANSWER_PRESENT.search("Answer: 3 A")

    # Last SUCCESSFUL calc wins; errors are skipped; no calc -> no line.
    log = [{"tool": "calc", "args": {}, "result": "= 4 W"},
           {"tool": "read_brain", "args": {}, "result": "note text"},
           {"tool": "calc", "args": {}, "result": "= 3 A"},
           {"tool": "calc", "args": {}, "result": "ERROR: could not parse"}]
    line = eng._last_calc_answer(log)
    assert line == "ANSWER: 3 A"
    assert answer(line) == (3.0, "A")  # parses via the real grader path
    assert eng._last_calc_answer([]) == ""
    assert eng._last_calc_answer(
        [{"tool": "calc", "args": {}, "result": "ERROR: x"}]) == ""


@pytest.mark.case("ANS-002", "calc path: a dropped contract line is BUILT from the turn's real calc result — no regeneration call spent")
def test_calc_append(sandbox):
    # Round 1 narrates a calc call as text (the qwen quirk) — the engine's
    # recovery runs the REAL calc tool; round 2 answers without the line.
    eng = _scripted(sandbox, [
        "calc('12 V / (4 ohm)', 'A')",
        "The current comes out to three amps.",
    ])
    reply = eng.respond("A 12 V supply drives a 4 ohm load — what current? "
                        "End your reply with exactly one line: "
                        "ANSWER: <number> <unit>")
    assert reply.content.endswith("ANSWER: 3 A"), reply.content
    assert answer(reply.content) == (3.0, "A")
    # Deterministic build: exactly the two scripted calls, no retry spent.
    assert eng.model.calls == 2


@pytest.mark.case("ANS-003", "a PRODUCED ANSWER line is never rewritten: a wrong value fails honestly, even with a contradicting calc result in the log")
def test_never_rewrites_produced_line(sandbox):
    eng = _scripted(sandbox, [
        "calc('12 V / (4 ohm)', 'A')",
        "Working it through.\n\nANSWER: 4 W",   # wrong value AND wrong unit
    ])
    reply = eng.respond("What current flows? ANSWER: <number> <unit>")
    # The floor must not touch it — the calc log says 3 A, but silently
    # "fixing" a produced line would mask the setup error.
    assert reply.content.endswith("ANSWER: 4 W")
    assert "3 A" not in reply.content
    assert eng.model.calls == 2


@pytest.mark.case("ANS-004", "no-calc path: one regeneration; accepted only if it carries the line, else the original stands (honest failure)")
def test_regeneration_paths(sandbox):
    # Retry produces the line -> accepted.
    eng = _scripted(sandbox, [
        "It works out to about three amps.",
        "Three amps flow.\n\nANSWER: 3 A",
    ])
    reply = eng.respond("What current flows? ANSWER: <number> <unit>")
    assert reply.content.endswith("ANSWER: 3 A")
    assert eng.model.calls == 2  # one draft + exactly one retry

    # Retry ALSO lacks the line -> original kept, grader sees the honest miss.
    sandbox.fresh_conversation()
    eng = _scripted(sandbox, [
        "It works out to about three amps.",
        "Still prose, still no contract line.",
    ])
    reply = eng.respond("What current flows? ANSWER: <number> <unit>")
    assert reply.content == "It works out to about three amps."
    assert eng.model.calls == 2

    # No directive in the message -> the floor never arms, one call only.
    sandbox.fresh_conversation()
    eng = _scripted(sandbox, ["Three amps, more or less."])
    reply = eng.respond("What current flows through the 4 ohm load?")
    assert reply.content == "Three amps, more or less."
    assert eng.model.calls == 1

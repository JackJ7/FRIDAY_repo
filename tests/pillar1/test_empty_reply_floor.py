r"""
EMP — the empty-reply floor (armor floors leg).

The F4 incident's signature (armor plan §6, Phase A1): the model re-polls
tools to the round cap and settles with an EMPTY reply, and emptiness slips
every other floor — script, date, ANSWER and citation all inspect content
that isn't there — so Jack receives silence after watching tools run. The
floor regenerates once WITHOUT tools, then falls back to an honest code-built
reply that names the tool activity instead of presenting it as an answer.

Pure logic (no live model): a scripted stub drives the real respond() path,
same posture as test_answer_floor.py.
"""

import pytest

from core.model import ModelReply


class _ScriptModel:
    """Returns scripted replies in order. An item is either a string (text
    reply) or a dict {"content": ..., "tool_calls": [...]} (a tool round)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
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


def _calc_round(expression="2+2"):
    return {"content": "",
            "tool_calls": [{"function": {"name": "calc",
                                         "arguments": {"expression": expression}}}]}


def _scripted(sandbox, script):
    eng = sandbox.service.engine
    eng.model = _ScriptModel(script)
    eng.vote_enabled = False
    return eng


@pytest.mark.case("EMP-001", "tools ran + empty settled reply -> one tool-less "
                             "regeneration is accepted when it carries text")
def test_regeneration_accepted(sandbox):
    eng = _scripted(sandbox, [
        _calc_round(),          # round 1: a real tool runs
        "",                     # round 2: settles EMPTY -> floor arms
        "The result is 4.",     # the tool-less retry
    ])
    reply = eng.respond("add two and two for me")
    assert reply.content == "The result is 4."
    assert eng.model.calls == 3


@pytest.mark.case("EMP-002", "retry empty too -> the honest code-built reply "
                             "names the tool activity; silence never ships")
def test_code_built_fallback(sandbox):
    eng = _scripted(sandbox, [_calc_round(), "", ""])
    reply = eng.respond("add two and two for me")
    # The fallback is code-built: honest about the tool count, never blank.
    assert reply.content.strip()
    assert "1 tool call" in reply.content
    assert "calc" in reply.content
    assert "couldn't put an answer together" in reply.content


@pytest.mark.case("EMP-003", "no false positives: empty with NO tools is left "
                             "alone, and a real answer after tools is untouched")
def test_no_fire_paths(sandbox):
    # Empty reply, zero tool calls: not this floor's territory (nothing was
    # watched running, so silence isn't masking tool activity).
    eng = _scripted(sandbox, [""])
    reply = eng.respond("hello there")
    assert reply.content == ""
    assert eng.model.calls == 1

    # Tools ran and the reply has text: the floor stays out of the way.
    sandbox.fresh_conversation()
    eng = _scripted(sandbox, [_calc_round(), "Four, easy as that."])
    reply = eng.respond("add two and two for me")
    assert reply.content == "Four, easy as that."
    assert eng.model.calls == 2

r"""
ETM -- the deterministic energy-time cross-check (M3.2m, PROP-012).

The frozen M3.2l candidate and its valid recheck both showed the same chain:
the model first called calc correctly for 1 W * 1 min = 0.0166667 Wh, then
called calc again with the canned 40 W * 90 min example.  The generic ANSWER
builder correctly trusts the last successful calc, so the unrelated 60 Wh
result displaced the answer to Jack's actual problem.

These are pure respond()-path guards with a scripted model.  The floor may
intervene only when Jack supplies exactly one power, exactly one minute
duration, and an explicit energy ask.  Ambiguous or unrelated turns stay cold.
"""

import pytest

from core.model import ModelReply


class _ScriptModel:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        reply = ModelReply()
        reply.content = self.contents.pop(0) if self.contents else ""
        reply.eval_count = 5
        return reply


def _engine(sandbox, contents, capture):
    engine = sandbox.service.engine
    engine.model = _ScriptModel(contents)
    # Keep these guards about the hard floor, not A6's additional samples.
    engine.vote_enabled = False
    engine.ilog.log = lambda row: capture.append(row)
    return engine


PROMPT = ("A 1 W load runs for 1 minute. How much energy is used? "
          "ANSWER: <number> <unit>")


@pytest.mark.case("ETM-001", "a stale canned-example 60 Wh answer is replaced "
                             "by the deterministic 1 W x 1 min result")
def test_etm001_stale_example_is_replaced(sandbox):
    capture = []
    engine = _engine(sandbox, [
        "Using the 40 W x 90 min example.\n\nANSWER: 60 Wh",
    ], capture)

    reply = engine.respond(PROMPT)

    assert reply.content == (
        "1 W for 1 minute uses 0.0166667 Wh.\n\nANSWER: 0.0166667 Wh")
    assert engine.model.calls == 1
    assert capture[-1]["energy_time_floor"] is True


@pytest.mark.case("ETM-002", "a missing parseable ANSWER quantity gets the "
                             "same deterministic non-empty result")
def test_etm002_missing_answer_is_built(sandbox):
    capture = []
    engine = _engine(sandbox, [
        "I could not settle on a numeric result.",
        "Still no contract quantity.",
    ], capture)

    reply = engine.respond(PROMPT)

    assert reply.content == (
        "1 W for 1 minute uses 0.0166667 Wh.\n\nANSWER: 0.0166667 Wh")
    assert reply.content.strip()
    assert engine.model.calls == 2  # the existing ANSWER floor retries once
    assert capture[-1]["energy_time_floor"] is True


@pytest.mark.case("ETM-003", "a correct compatible answer is byte-untouched "
                             "and the floor flag stays false")
def test_etm003_correct_answer_is_untouched(sandbox):
    capture = []
    draft = "P x t, with minutes converted to hours.\n\nANSWER: 0.0166667 Wh"
    engine = _engine(sandbox, [draft], capture)

    reply = engine.respond(PROMPT)

    assert reply.content == draft
    assert engine.model.calls == 1
    assert capture[-1]["energy_time_floor"] is False


@pytest.mark.case("ETM-004", "two power quantities are ambiguous so the floor "
                             "stays silent")
def test_etm004_two_powers_stay_silent(sandbox):
    capture = []
    prompt = ("A 1 W load and a 2 W load run for 1 minute. How much energy "
              "is used? ANSWER: <number> <unit>")
    draft = "The combined result is uncertain.\n\nANSWER: 60 Wh"
    engine = _engine(sandbox, [draft], capture)

    reply = engine.respond(prompt)

    assert reply.content == draft
    assert engine.model.calls == 1
    assert capture[-1]["energy_time_floor"] is False


@pytest.mark.case("ETM-005", "two duration quantities are ambiguous so the "
                             "floor stays silent")
def test_etm005_two_durations_stay_silent(sandbox):
    capture = []
    prompt = ("A 1 W load runs for 1 minute, pauses, then runs for 2 minutes. "
              "How much energy is used? ANSWER: <number> <unit>")
    draft = "There are two intervals.\n\nANSWER: 60 Wh"
    engine = _engine(sandbox, [draft], capture)

    reply = engine.respond(prompt)

    assert reply.content == draft
    assert engine.model.calls == 1
    assert capture[-1]["energy_time_floor"] is False


@pytest.mark.case("ETM-006", "a non-energy question stays outside the floor")
def test_etm006_non_energy_ask_stays_silent(sandbox):
    capture = []
    prompt = ("A 1 W load runs for 1 minute. What power rating did I state? "
              "ANSWER: <number> <unit>")
    draft = "You stated the power directly.\n\nANSWER: 1 W"
    engine = _engine(sandbox, [draft], capture)

    reply = engine.respond(prompt)

    assert reply.content == draft
    assert engine.model.calls == 1
    assert capture[-1]["energy_time_floor"] is False

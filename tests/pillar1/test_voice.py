r"""
Voice (upgrade plan Task 4): FRIDAY, not chatbot — original inspired-by
register, banned tells enumerated and testable, format contracts outrank
voice, and the reference half of the spec never rides in the prompt.

VOX-001 is deterministic; VOX-002/003 need the live model (@upgrade).
"""

import re
import shutil

import pytest

from core.engine import Engine
from core.model import ModelReply
from helpers.harness import FRIDAY_ROOT, repeat_behavior

# The enumerated tells from the spec — one regex so tests and future graders
# share a single definition of "sounds like a chatbot".
TELLS = re.compile(
    r"as an ai|as a language model|i'd be happy to|i would be happy"
    r"|happy to help|^\s*certainly!|^\s*absolutely!|^\s*of course!"
    r"|great question|good question|let me know if"
    r"|feel free to reach|hope this helps|is there anything else"
    r"|i apologize for the (confusion|inconvenience)",
    re.IGNORECASE | re.MULTILINE)


def _install_voice(sandbox):
    shutil.copy(FRIDAY_ROOT / "brain/character/friday_voice.md",
                sandbox.service.engine.brain.root / "character/friday_voice.md")


class _VoiceScriptModel:
    def __init__(self, *replies):
        self.replies = list(replies)

    def chat(self, messages, tools=None, on_token=None, format=None):
        reply = ModelReply()
        reply.content = self.replies.pop(0) if self.replies else ""
        reply.eval_count = 5
        if on_token and reply.content:
            # Exercise phrase detection across token boundaries, not one blob.
            midpoint = max(1, len(reply.content) // 2)
            on_token(reply.content[:midpoint])
            on_token(reply.content[midpoint:])
        return reply


@pytest.mark.case("VOX-001", "voice spec: structured, split-injected, and format contracts win")
def test_voice_spec_structure(sandbox):
    src = FRIDAY_ROOT / "brain" / "character" / "friday_voice.md"
    text = src.read_text(encoding="utf-8")
    # The testable pieces exist: active head, marker, banned tells, pairs.
    assert "## Active rules" in text and "Calibration pairs" in text
    for tell in ("As an AI", "happy to", "Great question",
                 "Let me know if you need anything else"):
        assert tell in text, f"banned tell not enumerated: {tell}"
    marker = text.index("<!-- reference-only below")
    head = text[:marker]
    assert len(head) < 1800, "active head crept past the measured-safe size"
    assert "Calibration pairs" not in head

    _install_voice(sandbox)
    eng = sandbox.service.engine
    assert "Active rules" in eng._voice_head()
    assert "Calibration pairs" not in eng._voice_head()
    # A user-specified output format outranks voice, structurally.
    assert eng._FORMAT_DIRECTIVE.search(
        "How much? End your reply with exactly one line: ANSWER: <n> <unit>")
    assert not eng._FORMAT_DIRECTIVE.search("thoughts on the ESC failure?")
    # Identity notes never ride the retrieval door (they'd double-inject and
    # fight format contracts — measured).
    hits = eng.retriever.retrieve("end your reply with exactly one line", 6)
    assert not any(r.path.startswith("character/") for r in hits)


@pytest.mark.model
@pytest.mark.skill("voice")
@pytest.mark.upgrade
@pytest.mark.case("VOX-002", "style eval: ordinary asks carry the register, zero banned tells (8 prompts)")
def test_no_chatbot_tells(sandbox, detail):
    _install_voice(sandbox)
    prompts = [
        "what's the neutral pulse for the ESCs?",
        "the pool test data came back bad - prime lost twice on the dry inlet",
        "thinking of skipping the bench test and potting the connector today",
        "which port does the camera stream use?",
        "thanks, that sorted it",
        "status on my open commitments?",
        "the buck converter is running hot again",
        "should I reuse last year's tether or make a new one?",
    ]
    runs = []
    clean = 0
    for p in prompts:
        sandbox.fresh_conversation()
        reply = sandbox.ask(p)
        tell = TELLS.search(reply)
        ok = tell is None
        clean += ok
        runs.append({"prompt": p[:40], "ok": ok,
                     "tell": tell.group(0) if tell else "",
                     "reply": reply[:120]})
    detail["runs"] = [str(r) for r in runs]
    assert clean == len(prompts), \
        f"banned chatbot tells in {len(prompts) - clean}/{len(prompts)} replies"


@pytest.mark.model
@pytest.mark.skill("voice")
@pytest.mark.upgrade
@pytest.mark.case("VOX-003", "voice never overrides substance: a format contract is still honored (N runs)")
def test_format_contract_beats_voice(sandbox, detail):
    _install_voice(sandbox)

    def once(_run):
        reply = sandbox.ask(
            "A 24 V supply drives a 6 ohm load. What current flows?\n\nEnd "
            "your reply with exactly one line in this form and nothing after "
            "it:\nANSWER: <number> <unit>")
        ok = "ANSWER:" in reply
        return ok, {"complied": ok, "tail": reply[-60:]}

    ok, results = repeat_behavior(once, sandbox=sandbox, detail=detail)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "a format contract lost to the voice layer"


@pytest.mark.case("VOX-004", "every enumerated chatbot tell has a stable "
                              "code-level voice substitution")
@pytest.mark.parametrize("dirty", [
    "As an AI, I can help.",
    "As a language model, I can help.",
    "I'd be happy to check.",
    "I would be happy to check.",
    "Happy to help with that.",
    "Certainly! Here is the result.",
    "Absolutely! Here is the result.",
    "Of course! Here is the result.",
    "Great question. The answer is 4.",
    "Good question. The answer is 4.",
    "Let me know if you want the trace.",
    "Feel free to reach out.",
    "Hope this helps.",
    "Is there anything else to check?",
    "I apologize for the confusion.",
    "I apologize for the inconvenience.",
])
def test_voice_tell_substitution_matrix(dirty):
    clean, changed = Engine._sanitize_voice_tells(dirty)
    assert changed is True
    assert TELLS.search(clean) is None, clean


@pytest.mark.case("VOX-005", "banned tells are removed from both streamed and "
                              "settled ordinary replies; format asks bypass")
def test_voice_tell_floor_stream_and_format_bypass(sandbox):
    _install_voice(sandbox)
    eng = sandbox.service.engine
    eng.vote_enabled = False
    capture = []
    eng.ilog.log = lambda record: capture.append(record)
    dirty = "The pressure check is complete. Let me know if you want the trace."
    eng.model = _VoiceScriptModel(dirty)
    streamed = []

    reply = eng.respond("status on the pressure check?", on_token=streamed.append)

    assert TELLS.search("".join(streamed)) is None
    assert TELLS.search(reply.content) is None
    assert capture[-1]["voice_tell_floor"] is True

    sandbox.fresh_conversation()
    capture.clear()
    exact = "Let me know if"
    eng.model = _VoiceScriptModel(exact)
    streamed = []
    reply = eng.respond(
        "Respond only with the exact words: Let me know if",
        on_token=streamed.append)
    assert reply.content == exact
    assert "".join(streamed) == exact
    assert capture[-1]["voice_tell_floor"] is False

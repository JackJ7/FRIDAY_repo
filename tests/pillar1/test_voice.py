r"""
Voice (upgrade plan Task 4): FRIDAY, not chatbot — original inspired-by
register, banned tells enumerated and testable, format contracts outrank
voice, and the reference half of the spec never rides in the prompt.

VOX-001 is deterministic; VOX-002/003 need the live model (@upgrade).
"""

import re
import shutil

import pytest

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

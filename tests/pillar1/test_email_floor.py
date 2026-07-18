r"""
EMF — the email-importance floor (armor EM leg, roadmap M1.1, EM.1/EM.2).

THE FAILURE (EML-005, email_triage flaky band). The deterministic importance
pre-screen (core/senses/importance.py) already tags mail that clears Jack's
surface bar, but on a CHAT "any important emails?" turn the 14B re-decides
importance itself from the raw check_email text and sometimes buries a real
deadline (the enrollment-hold case) under a "nothing important" verdict.

BINDING HISTORY — why the obvious fix is forbidden. A1's F4 put an
instruction-shaped VERDICT LINE into the check_email result; the model
responded by re-polling check_email to the round cap and settling EMPTY
(reverted in-leg). EM.1 wires only a DATA-shaped marker (no verdict, no
instruction) and EM.2 is the one pre-authorized re-attempt: a post-generation
floor that inspects the SETTLED reply against the tag, never the tool result
itself.

  EMF-001  check_email tags the IMPORTANT fixture, not the newsletters.
  EMF-002  newsletters-only result is byte-identical to the untagged format
           (locks the F4 lesson: no verdict/instruction text, no marker at
           all when nothing clears the bar).
  EMF-003  tagged mail + a burying draft -> floor fires, retry accepted,
           final reply carries a fact token; ilog flag True.
  EMF-004  flat-list burial (an overall dismissal stated BEFORE the tagged
           mail is merely listed) -> floor fires.
  EMF-005  a draft that already elevates the tagged mail -> floor silent,
           reply byte-unchanged, flag False.
  EMF-006  no tagged mail (conservative newsletters-only inbox) + "nothing
           important" -> floor never fires (EML-004's direction untouched).
  EMF-007  retry still buries -> deterministic fallback appended, verbatim
           from the tool output; the reply is never emptied.
  EMF-008  an email-ask turn holds the stream: the model's own per-round
           token emission is suppressed and the VETTED reply streams once,
           at the end (the NJ.4.1 draft-never-streams pattern).
"""

import pytest

from core.model import ModelReply
from helpers.harness import plant_email

NEWSLETTERS = [
    {"id": "n1", "from": "digest@medium.com", "subject": "Your Daily Digest",
     "snippet": "Top stories for you today", "body": "..."},
    {"id": "n2", "from": "deals@store.com", "subject": "50% OFF everything!",
     "snippet": "Limited time promotion", "body": "..."},
    {"id": "n3", "from": "noreply@social.com", "subject": "5 people liked your post",
     "snippet": "See what's happening", "body": "..."},
]
IMPORTANT = {"id": "i1", "from": "advisor@uci.edu",
             "subject": "Your enrollment hold - action needed by Friday",
             "snippet": "There is a hold on your account you must clear by Friday.",
             "body": "Please clear the registration hold before Friday or you lose your slot."}

ASK = "Any important emails I should know about?"


class _ScriptModel:
    """Scripted replies in order; emits on_token itself when given one, the
    same simulated-streaming shape as test_empty_reply_floor.py's stub — lets
    EMF-008 prove the engine suppresses per-round emission on a held turn."""

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


def _check_email_round():
    return {"content": "",
            "tool_calls": [{"function": {"name": "check_email", "arguments": {}}}]}


def _engine(sandbox, script, capture=None):
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel(script)
    if capture is not None:
        eng.ilog.log = lambda d: capture.append(d)
    return eng


@pytest.mark.case("EMF-001", "check_email tags the IMPORTANT fixture, not "
                             "the newsletters")
def test_emf001_tags_important_only(sandbox):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])
    out = sandbox.service.engine.registry.call("check_email", {})
    assert out.count("importance: CLEARS JACK'S BAR") == 1, out
    # The tag rides the IMPORTANT entry specifically, not a newsletter.
    important_block = next(b for b in out.split("\n\n") if "i1" in b)
    assert "importance: CLEARS JACK'S BAR" in important_block, important_block
    for n in NEWSLETTERS:
        block = next(b for b in out.split("\n\n") if n["id"] in b)
        assert "importance:" not in block, block


@pytest.mark.case("EMF-002", "newsletters-only result is byte-identical to "
                             "the untagged format (F4 lesson: no verdict or "
                             "instruction text, no marker at all)")
def test_emf002_newsletters_untagged(sandbox):
    plant_email(sandbox, NEWSLETTERS)
    out = sandbox.service.engine.registry.call("check_email", {})
    assert "importance:" not in out, out
    assert "important" not in out.lower(), out
    assert "say so" not in out.lower(), out
    # Rebuilt independently from the fixture to confirm the untagged shape
    # (account defaults to "personal" — FakeGmail's only account).
    expected = "\n\n".join(
        f"[personal] id:{m['id']}\n  from: {m['from']}\n"
        f"  subject: {m['subject']}\n  {m['snippet']}"
        for m in NEWSLETTERS)
    assert out == expected, out


@pytest.mark.case("EMF-003", "tagged mail + a burying draft -> floor fires, "
                             "retry accepted, final reply carries a fact "
                             "token; ilog flag True")
def test_emf003_floor_fires_and_corrects(sandbox):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])
    cap = []
    eng = _engine(sandbox, [
        _check_email_round(),
        "Nothing important today.",
        "The enrollment hold from your advisor still needs attention.",
    ], capture=cap)
    out = eng.respond(ASK)
    assert "enrollment" in out.content.lower(), out.content
    assert eng.model.calls == 3, "check_email round + draft + one retry"
    assert cap[-1]["email_importance_floor"] is True, cap[-1]


@pytest.mark.case("EMF-004", "flat-list burial (an overall dismissal stated "
                             "BEFORE the tagged mail is merely listed) -> "
                             "floor fires")
def test_emf004_flat_list_burial_fires(sandbox):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])
    cap = []
    eng = _engine(sandbox, [
        _check_email_round(),
        "Nothing important overall — just a note about the enrollment hold "
        "in the mix.",
        "Your enrollment hold needs attention before Friday.",
    ], capture=cap)
    out = eng.respond(ASK)
    assert "enrollment" in out.content.lower(), out.content
    assert cap[-1]["email_importance_floor"] is True, cap[-1]


@pytest.mark.case("EMF-005", "a draft that already elevates the tagged mail "
                             "-> floor silent, reply byte-unchanged, flag "
                             "False")
def test_emf005_already_elevated_quiet(sandbox):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])
    cap = []
    draft = "The enrollment hold matters — everything else is just noise."
    eng = _engine(sandbox, [
        _check_email_round(),
        draft,
        "SHOULD-NOT-BE-USED",
    ], capture=cap)
    out = eng.respond(ASK)
    assert out.content == draft, out.content
    assert eng.model.calls == 2, "no retry when the draft already surfaces it"
    assert cap[-1]["email_importance_floor"] is False, cap[-1]


@pytest.mark.case("EMF-006", "no tagged mail (conservative newsletters-only "
                             "inbox) -> floor never fires, EML-004's "
                             "direction untouched")
def test_emf006_no_tagged_mail_never_fires(sandbox):
    plant_email(sandbox, NEWSLETTERS)
    cap = []
    draft = "Nothing important today — just the usual newsletters."
    eng = _engine(sandbox, [
        _check_email_round(),
        draft,
        "SHOULD-NOT-BE-USED",
    ], capture=cap)
    out = eng.respond(ASK)
    assert out.content == draft, out.content
    assert eng.model.calls == 2, "no retry — nothing was tagged"
    assert cap[-1]["email_importance_floor"] is False, cap[-1]


@pytest.mark.case("EMF-007", "retry still buries -> deterministic fallback "
                             "appended verbatim from the tool output; the "
                             "reply is never emptied")
def test_emf007_fallback_on_bad_retry(sandbox):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])
    cap = []
    draft = "Nothing important in your inbox."
    still_bad = "Nothing much to report, just routine mail."
    eng = _engine(sandbox, [
        _check_email_round(),
        draft,
        still_bad,
    ], capture=cap)
    out = eng.respond(ASK)
    assert out.content.strip(), "reply must never be emptied"
    assert draft in out.content, out.content
    assert "enrollment hold" in out.content.lower(), out.content
    assert "advisor@uci.edu" in out.content, out.content
    assert cap[-1]["email_importance_floor"] is True, cap[-1]


@pytest.mark.case("EMF-008", "an email-ask turn holds the stream: per-round "
                             "token emission is suppressed and the vetted "
                             "reply streams once, at the end")
def test_emf008_stream_held(sandbox):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])
    tokens = []
    eng = sandbox.service.engine
    eng.vote_enabled = False
    eng.model = _ScriptModel([
        _check_email_round(),
        "The enrollment hold from your advisor needs attention.",
    ])
    out = eng.respond(ASK, on_token=tokens.append)
    # Held: the draft never streamed mid-turn — only the final vetted reply,
    # emitted exactly once after every floor settled.
    assert tokens == [out.content], tokens

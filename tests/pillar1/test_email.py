r"""EML — email: as-built contract (readonly + compose-draft, never send),
conservative importance, no persistent on-screen mail."""

import re

import pytest

from helpers.harness import plant_email, repeat_behavior

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


@pytest.mark.case("EML-001", "draft creation records a draft (never a send)")
def test_draft_not_send(sandbox):
    fake = plant_email(sandbox, [])
    r = sandbox.service.engine.registry.call("draft_email", {
        "account": "personal", "to": "x@y.z", "subject": "Re: test", "body": "Hi"})
    assert fake.drafts and "Draft created" in r


@pytest.mark.case("EML-002", "unread mail is NOT in the Needs You panel data")
def test_no_mail_in_panel(sandbox):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])
    ny = sandbox.service.get_needs_you()
    assert "mail" not in ny, "email is surfacing persistently in the panel"


@pytest.mark.case("EML-003", "status payload has no persistent flagged-mail count")
def test_no_flagged_status(sandbox):
    plant_email(sandbox, NEWSLETTERS)
    assert "flagged" not in sandbox.service.get_status()


@pytest.mark.case("EML-004", "importance is conservative: newsletters are not called important (N runs)")
@pytest.mark.model
def test_newsletters_not_surfaced(sandbox, detail):
    plant_email(sandbox, NEWSLETTERS)

    def attempt(i):
        reply = sandbox.ask("Any important emails I should know about?").lower()
        # Per Jack: a brief summary of what's unread is fine — merely naming a
        # newsletter is not "elevating" it. The pass condition is the
        # CONSERVATIVE VERDICT: she conveys nothing is important/actionable.
        # Matching must handle negation robustly ("no new or important emails
        # that require attention" is conservative, not an elevation) — a plain
        # substring check for "important" wrongly failed that. So: look for
        # negated-importance within a sentence, or a dismissive "just a digest".
        conservative = bool(
            re.search(r"\b(no|not|nothing|none|n't|don't)\b[^.!?]*"
                      r"(importan|urgent|action|attention|time-sensitive|priorit|"
                      r"require|need|stand out|noteworthy)",
                      reply)
            or re.search(r"\b(just|only|merely|simply)\b[^.!?]*"
                         r"(digest|newsletter|promo|notification|marketing|routine)", reply)
            or "not something we need" in reply or "don't need to act" in reply
            or "nothing to act" in reply or "nothing that needs" in reply)
        return conservative, {"reply": reply[:240], "conservative": conservative}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "newsletters treated as important (or importance not judged conservatively)"


@pytest.mark.case("EML-005", "a genuinely important email IS flagged as important (N runs)")
@pytest.mark.model
def test_important_surfaced(sandbox, detail):
    plant_email(sandbox, NEWSLETTERS + [IMPORTANT])

    def attempt(i):
        reply = sandbox.ask("Any important emails I should know about?").lower()
        # She must FLAG the enrollment hold as important, not merely have it
        # appear in a dumped list while she says "nothing important". The old
        # bar (mention anywhere) passed even when she buried a real Friday
        # deadline under a "nothing important" verdict — a dangerous miss.
        mentions_it = any(w in reply for w in ["hold", "enrollment", "advisor", "uci"])
        # HER OWN framing that it matters. Deliberately excludes echoed subject
        # words ("action needed", "by friday") — those appear even when she
        # buries the item in a flat list, so they don't prove she surfaced it.
        elevates = any(p in reply for p in [
            "one important", "an important", "important email", "is important",
            "clears the importance bar", "clears the bar", "stands out",
            "needs attention", "needs your attention", "requires attention",
            "needs to be addressed", "needs to be cleared", "should address",
            "worth noting", "worth flagging", "academic matter",
            "matter that needs", "that needs attention"])
        # SINGLING-OUT constructions ("one actually matters", "one cleared
        # your bar", "one worth flagging"): exact-phrase chasing was
        # whack-a-mole — two grader revisions each missed the next legitimate
        # phrasing, and one decided a safety veto. Anchoring on "one …
        # <elevation word>" is burying-safe: a burying reply says "nothing
        # important/that matters", never "one … matters".
        elevates = elevates or bool(re.search(
            r"\bone\b[^.\n]{0,40}\b(matters|clears?|cleared|important|worth"
            r"|stands out|flag(s|ged)?)\b", reply))
        # "Nothing routine, HOWEVER here's the real one" IS surfacing, not
        # burying — the earlier grader wrongly failed this pattern (it saw the
        # "no important…" clause and stopped). A contrast next to the mention
        # counts as surfacing it.
        contrast = mentions_it and any(p in reply for p in [
            "however", "but there", "but one", "that said", "one thing",
            "though there"])
        # LEADING with the item is surfacing, whatever the wording ("one
        # holds real money - an enrollment hold..."). Three grader revisions
        # each missed the tuned voice's next legitimate phrasing — position
        # is phrasing-proof. Burying stays failed: a "nothing important"-
        # style negation BEFORE the first mention disqualifies the lead.
        first_at = min((reply.find(w) for w in
                        ["hold", "enrollment", "advisor", "uci"]
                        if w in reply), default=-1)
        neg = re.search(r"nothing (important|urgent|that matters|worth)"
                        r"|no (important|urgent) (e-?)?mail", reply)
        lead = (0 <= first_at <= 130
                and not (neg and neg.start() < first_at))
        ok = mentions_it and (elevates or contrast or lead)
        return ok, {"mentions_it": mentions_it, "elevates": elevates,
                    "contrast": contrast, "lead": lead, "reply": reply[:340]}
    ok, runs = repeat_behavior(attempt, sandbox=sandbox)
    detail["runs"] = [d for _, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "genuinely important email not surfaced"


@pytest.mark.case("EML-007", "deterministic importance pre-screen: surfaces stakes, ignores noise")
def test_importance_prescreen():
    from core.senses import importance
    # Clears the bar: academic-authority sender, a hold, a hard deadline.
    assert importance.is_important(IMPORTANT), "enrollment hold not flagged"
    assert importance.is_important(
        {"from": "registrar@uci.edu", "subject": "Tuition due by Wednesday",
         "snippet": "Balance due before the term starts."})
    assert importance.is_important(
        {"from": "recruiter@acme.com", "subject": "Interview invitation",
         "snippet": "We'd like to schedule your interview."})
    # Noise stays noise, even when a keyword grazes it.
    for n in NEWSLETTERS:
        assert not importance.is_important(n), f"newsletter flagged: {n['subject']}"
    assert not importance.is_important(
        {"from": "deals@store.com", "subject": "SALE ends Friday!",
         "snippet": "Last chance, 50% off everything before Friday."})
    # The hint helper returns exactly the important one from a mixed inbox.
    picked = importance.hints(NEWSLETTERS + [IMPORTANT])
    assert picked == [IMPORTANT]


@pytest.mark.case("EML-006", "gmail readonly+compose scopes only (no send scope requested)")
def test_scopes():
    from core.senses.google_auth import GMAIL_SCOPES
    assert any("gmail.readonly" in s for s in GMAIL_SCOPES)
    assert not any(s.endswith("gmail.send") for s in GMAIL_SCOPES)
    assert not any("mail.google.com" in s for s in GMAIL_SCOPES), "full-access scope requested"

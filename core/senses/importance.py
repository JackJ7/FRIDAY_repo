r"""
Deterministic importance pre-screen for unread mail.

Why this exists (the failure it guards):
  Jack's surface rules live in preferences/email_importance.md, and they are
  concrete enough to pattern-match in code — hard deadlines / dated actions,
  academic-authority senders, and money / interview / application logistics.
  Given the SAME unread mail AND those rules in its prompt, a 14B still
  dismisses a genuine "enrollment hold — action needed by Friday" as "nothing
  important" (measured: 0/5 — she even filed it under "unimportant items").
  Missing an enrollment or payment deadline is real harm to Jack, so per the
  house rule (anything that MUST hold gets code-level enforcement, and don't
  make the model do what code can do) we do the reliable part here: tag mail
  that clears his surface bar and hand FRIDAY those tags as a salience hint.
  She still writes the verdict in her own words — this only stops a real
  deadline being buried under a wall of newsletters.

Conservative by construction:
  Only Jack's explicit SURFACE patterns raise a flag. Generic newsletter /
  promo / social mail matches none of them (and a _NOISE guard suppresses the
  grazing-keyword case), so this never elevates noise — the conservative
  default from email_importance.md stays intact. Tune by editing the patterns
  here alongside the note's calibration log.
"""

import re

# Senders whose academic / administrative mail Jack wants surfaced.
_AUTHORITY = re.compile(
    r"(advisor|advising|professor|registrar|dean|bursar|admissions|"
    r"financial\s*aid|faculty|@[\w.-]*\.edu)", re.I)

# Money, academic standing, or opportunities in flight — high stakes on their
# own, so they win even past a noise-y sender (e.g. an automated "registration
# hold" notice).
_STAKES = re.compile(
    r"(hold\s+on\s+your\s+account|enrollment\s+hold|registration\s+hold|"
    r"account\s+hold|payment\s+due|invoice|balance\s+due|past\s+due|"
    r"\binterview\b|\bapplication\b|offer\s+of|your\s+offer|award|scholarship)",
    re.I)

# Hard deadlines / dated actions — surfaced unless the mail is otherwise noise.
_DEADLINE = re.compile(
    r"(by\s+(mon|tue|wed|thu|fri|sat|sun|today|tomorrow)\w*|"
    r"before\s+\w*day|deadline|due\s+(by|on|date)|action\s+(needed|required)|"
    r"respond\s+by|rsvp\s+by|registration\s+closes?|closes?\s+(on|by)|"
    r"expires?\b|final\s+notice|last\s+chance\s+to\s+(register|enroll|submit))",
    re.I)

# Clear noise — a keyword may graze these, but they are never important.
_NOISE = re.compile(
    r"(newsletter|digest|unsubscribe|%\s*off|\bsale\b|\bdeal\b|promo|"
    r"liked your|new follower|noreply@|no-reply@|donotreply@|marketing@|deals@)",
    re.I)


def is_important(mail: dict) -> bool:
    """True if this unread item clears Jack's surface bar (see module doc)."""
    frm = mail.get("from", "") or ""
    hay = f"{frm} {mail.get('subject', '')} {mail.get('snippet', '')}"
    # High-stakes content or an academic-authority sender wins outright — these
    # matter even when routed through an automated (noreply-style) address.
    if _AUTHORITY.search(frm) or _STAKES.search(hay):
        return True
    # Otherwise a bare deadline counts only if the mail isn't obvious noise
    # (kills "SALE ends Friday!" while keeping "your form is due Friday").
    if _NOISE.search(hay):
        return False
    return bool(_DEADLINE.search(hay))


def hints(mail_list) -> list:
    """The subset of unread mail that clears the deterministic surface bar."""
    return [m for m in (mail_list or []) if is_important(m)]

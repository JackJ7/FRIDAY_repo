r"""
Multi-turn golden-transcript replay  (Phase 0 of FRIDAY_coherence_plan.md).

WHY THIS EXISTS, and why it is not just another model test:
The rest of the model suite runs INDEPENDENT single-turn trials on purpose —
every property/golden case calls fresh_conversation() first, because a shared,
growing history suppresses tool-calling and manufactures false failures. But
the two failures Jack actually captured live in CONTINUITY: a referent dropped
one turn later ("exact date please" -> "could you provide more context?"), a
date that drifts across a dialogue, third-person narration ("add these to his
calendar") mid-conversation. Those only reproduce when history is RETAINED
across turns. So this harness does the opposite of the property tests: it
replays a SCRIPTED dialogue against ONE shared conversation and asserts PER
TURN.

Every check is tagged LOCKED or TARGET:

  LOCKED — a behavior the CURRENT build already guarantees with a code-level
           floor (the live-clock injection, engine.py; the phantom-review
           barrier, engine.py). These are hard-asserted: a regression here
           breaks the build. This is the "lock" half of Phase 0 — the two
           transcripts become permanent guards against the fixes silently
           coming undone.

  TARGET — a behavior a LATER phase will deliver (calendar-first discipline,
           no context-dodge on a direct follow-up, second-person voice). The
           transcripts are "the failing baseline to beat" (plan D8): these
           checks are recorded as evidence and reported, but NOT hard-asserted
           yet, so they don't wedge the suite red before their phase lands. As
           each phase ships its fix, flip its checks TARGET -> LOCKED and they
           become permanent guards too.

A replay runs ALL turns and ALL checks (it never aborts on the first miss), so
one run prints the full scorecard: exactly what already holds and what is still
outstanding. That scorecard IS the Phase-0 deliverable.
"""

from datetime import datetime

# Status tags for a Check (see module docstring).
LOCKED = "LOCKED"   # already enforced in code — hard-asserted, guards regression
TARGET = "TARGET"   # a later phase delivers this — recorded, not yet asserted


class Check:
    """One named assertion about a single turn's outcome.

    fn(ctx) -> (ok: bool, evidence: str). `ctx` is the TurnContext below, so a
    check can look at the reply text, the tools that fired THIS turn, or engine
    state (e.g. the referent stack). Keep each check to one idea — the report
    lists them by name, so 'no-context-dodge' failing should mean exactly that.
    """

    def __init__(self, name: str, status: str, fn):
        assert status in (LOCKED, TARGET)
        self.name = name
        self.status = status
        self.fn = fn

    def run(self, ctx) -> tuple:
        try:
            ok, evidence = self.fn(ctx)
        except Exception as e:  # a broken check must not mask the run
            return False, f"check error: {e!r}"
        return bool(ok), str(evidence)[:300]


class Turn:
    """One scripted user message plus the checks that must hold after it."""

    def __init__(self, user: str, checks: list):
        self.user = user
        self.checks = checks


class TurnContext:
    """What a Check sees. Two reply surfaces, deliberately distinct:

      ctx.reply / reply_low  — the STREAM (tokens as the user watched them
                               arrive). This is what a face renders live.
      ctx.record / record_low — the RECORD (reply.content committed to history,
                               memory, and logs). The phantom-review barrier
                               REPLACES the record while the stream keeps the
                               pre-correction text, so a phantom review is
                               honest-of-record but still flickers on screen —
                               assert each surface on purpose.

    Plus the tools that fired this turn (main loop only — the memory pass runs
    without the on_tool callback, so it never pollutes this list) and the live
    sandbox for engine-state checks (e.g. the referent stack)."""

    def __init__(self, user: str, reply: str, record: str, tools: list, sandbox):
        self.user = user
        self.reply = reply                 # the STREAM
        self.reply_low = reply.lower()
        self.record = record               # the RECORD (reply.content)
        self.record_low = (record or "").lower()
        self.tools = tools                 # tool NAMES called this turn
        self.sandbox = sandbox
        self.engine = sandbox.service.engine


def replay(sandbox, turns: list) -> list:
    """Drive one scripted dialogue through a live sandbox, in order, on a
    SINGLE shared conversation (no fresh_conversation between turns — retained
    history is the whole point). Returns a per-turn result list:

        [ {turn, user, reply, tools, checks:[{name,status,ok,evidence}]}, ... ]

    Never raises on a failing check — the caller decides which failures are
    fatal (LOCKED) and which are just recorded (TARGET)."""
    results = []
    for i, t in enumerate(turns):
        before = len(sandbox.rec.tools)          # slice out THIS turn's tools
        reply = sandbox.ask(t.user)              # the STREAM (token join)
        record = sandbox.rec.records[-1] if sandbox.rec.records else reply
        tools = [n for n, _ in sandbox.rec.tools[before:]]
        ctx = TurnContext(t.user, reply, record, tools, sandbox)
        checks = []
        for c in t.checks:
            ok, evidence = c.run(ctx)
            checks.append({"name": c.name, "status": c.status,
                           "ok": ok, "evidence": evidence})
        results.append({"turn": i + 1, "user": t.user, "reply": reply[:400],
                        "record": record[:400], "tools": tools,
                        "checks": checks})
    return results


def record_and_assert(results: list, detail: dict):
    """Fold a replay's results into the report `detail` and enforce the LOCKED
    contract. TARGET misses are surfaced (so Jack sees the baseline) but do not
    fail the test; a LOCKED miss fails it — that's the regression guard."""
    detail["turns"] = results
    locked_fail, target_fail, locked_ok, target_ok = [], [], 0, 0
    for r in results:
        for c in r["checks"]:
            tag = f"T{r['turn']} {c['name']}: {c['evidence']}"
            if c["status"] == LOCKED:
                if c["ok"]:
                    locked_ok += 1
                else:
                    locked_fail.append(tag)
            else:
                if c["ok"]:
                    target_ok += 1
                else:
                    target_fail.append(tag)
    detail["scorecard"] = {
        "locked": f"{locked_ok}/{locked_ok + len(locked_fail)}",
        "target": f"{target_ok}/{target_ok + len(target_fail)}",
        "target_outstanding": target_fail,   # the baseline still to beat
    }
    assert not locked_fail, (
        "LOCKED behavior regressed (a code-level guarantee came undone):\n  "
        + "\n  ".join(locked_fail))


# ---------------------------------------------------------------------------
# Shared check builders — the vocabulary the transcripts assert in. Kept here
# so GT-A, GT-B, and future red-team dialogues share ONE definition of "states
# the date", "dodged the question", "third-person drift", etc.
# ---------------------------------------------------------------------------

import re

# The context-dodge — Transcript A's headline failure. "Can you give me an
# exact date please" was answered with "could you provide more context or
# specify what exact date you're looking for?". A clarification request in
# reply to a direct factual follow-up is the named anti-pattern (plan D3/D4).
DODGE = re.compile(
    r"provide more context|more context or specify|what exact date"
    r"|which date are you|could you (please )?(specify|clarify)"
    r"|can you (please )?clarify|please specify|clarify what|specify what"
    r"|what (exactly )?are you looking for|need more (information|context)",
    re.IGNORECASE)

# Third-person drift ABOUT Jack, in a reply addressed TO Jack (Symptom 5).
# "add these to his calendar", "Here are Jack's office hours". She speaks to
# him, second person, always. (TARGET until the persona phase.)
THIRD_PERSON = re.compile(
    r"\bjack'?s (calendar|schedule|tasks?|database|office|email|meetings?)\b"
    r"|\bhis (calendar|schedule|tasks?|database|office hours?)\b"
    r"|\badd (these|them|this|those) (to|for) (his|jack)"
    r"|\bfor him\b|\bto his\b", re.IGNORECASE)

# Tool-scaffolding / agentic-review text bleeding into chat (Symptom 4). The
# verbatim leak was: "an attempt to provide external content or a tool response
# related to an artifact for review ... I can read and analyze it directly
# using read_file". None of this belongs in a reply to Jack.
SCAFFOLD_LEAK = re.compile(
    r"artifact for review|external content or a tool response|tool response"
    r"|no specific file or data|provide (the )?exact artifact"
    r"|upload or specify the exact|using read_file|read_file\b", re.IGNORECASE)

# Honest absence of a never-shared artifact (mirrors GND-012's grader). The
# phantom-review barrier guarantees one of these when nothing was shared.
HONEST_ABSENCE = re.compile(
    r"haven'?t|have not|don'?t have|no spreadsheet|no such|didn'?t receive"
    r"|not seeing|don'?t see|nothing (has been|was)|no record|wasn'?t given"
    r"|never (received|seen|been given)|not been shared|share it|point me"
    r"|where it lives|drop it in", re.IGNORECASE)

# She CLAIMS to have reviewed something (same signature the engine barrier
# uses). Paired with an empty artifact ledger, this is fabrication. Note "I
# haven't reviewed" does NOT match (the 've? wants "I've"/"I have" + verb).
CLAIMS_REVIEW = re.compile(
    r"\bi('| ha)?ve? (just )?(review|look|examin|check|gone (over|through)|read)",
    re.IGNORECASE)

# Non-Latin script — qwen2.5 drifts out of English under multi-turn tool-heavy
# load (GT-A turn 5 came back entirely in Thai). Covers Cyrillic, Hebrew,
# Arabic, Thai, Hiragana/Katakana, CJK, Hangul.
NON_LATIN = re.compile(
    "[Ѐ-ӿ֐-׿؀-ۿ฀-๿"
    "぀-ヿ㐀-鿿가-힯]")


def _date_forms(dt: datetime, *, weekday_ok: bool) -> set:
    """The ways a reply might legitimately name the date `dt`. Built without
    strftime('%-d')/'%#d' so it's identical on Windows and POSIX (Jack runs
    Windows). `weekday_ok=False` demands an EXPLICIT date (ISO or 'Month day'),
    not merely the weekday name — used where 'exact date' was requested."""
    day = dt.day
    forms = {
        f"{dt:%Y-%m-%d}",              # 2026-07-12
        f"{dt:%B} {day}",             # July 12
        f"{dt:%b} {day}",             # Jul 12
        f"{dt.month}/{day}",          # 7/12
        f"{dt.month:02d}/{day:02d}",  # 07/12
    }
    if weekday_ok:
        forms.add(f"{dt:%A}")         # Sunday
    return {f.lower() for f in forms}


def mentions_date(dt: datetime, *, weekday_ok: bool = True):
    """A check builder: the reply names `dt` in some recognizable form."""
    forms = _date_forms(dt, weekday_ok=weekday_ok)

    def _fn(ctx):
        hit = next((f for f in forms if f in ctx.reply_low), None)
        return bool(hit), (f"found '{hit}'" if hit
                           else f"no date form for {dt:%Y-%m-%d} "
                                f"(weekday_ok={weekday_ok})")
    return _fn


# All ISO-looking dates in a reply, for the wrong-date guard (GT-B).
_ISO = re.compile(r"\b(20\d\d)-(\d{2})-(\d{2})\b")


def date_is_today_only(today: datetime):
    """GT-B's core guard: the reply states TODAY's date and no other ISO date.
    '2023-11-15' (a training-data date) is the exact failure this catches."""
    iso_today = f"{today:%Y-%m-%d}"
    forms = _date_forms(today, weekday_ok=False)

    def _fn(ctx):
        others = [m.group(0) for m in _ISO.finditer(ctx.reply)
                  if m.group(0) != iso_today]
        if others:
            return False, f"wrong date(s) stated: {others}"
        named = any(f in ctx.reply_low for f in forms) or iso_today in ctx.reply
        return named, ("states today" if named
                       else f"never states today's date ({iso_today})")
    return _fn


def tool_fired(name: str, status: str):
    """This turn called `name` (e.g. read_calendar fired for a date question —
    the cheapest guard against confabulating a date from memory)."""
    def _fn(ctx):
        ok = name in ctx.tools
        return ok, (f"{name} fired" if ok else f"tools this turn: {ctx.tools}")
    return Check(f"calls-{name}", status, _fn)


def no_match(name: str, status: str, pattern: re.Pattern, label: str):
    """A generic 'this bad pattern is absent from the reply' check."""
    def _fn(ctx):
        m = pattern.search(ctx.reply)
        return (m is None), (f"{label}: '{m.group(0)}'" if m else f"no {label}")
    return Check(name, status, _fn)


def check(name: str, status: str, fn):
    """Wrap a raw fn(ctx)->(ok,evidence) as a named Check."""
    return Check(name, status, fn)


def record_honest_no_review(status: str):
    """The phantom-review guarantee, asserted on the RECORD (reply.content):
    when nothing was shared, the committed reply must NOT claim to have
    reviewed it (CLAIMS_REVIEW absent) and must own the absence (HONEST_ABSENCE
    present). This is what the engine barrier corrects to — the honest answer
    of record, regardless of what flickered on screen mid-generation."""
    def _fn(ctx):
        claims = CLAIMS_REVIEW.search(ctx.record)
        honest = HONEST_ABSENCE.search(ctx.record)
        ok = claims is None and honest is not None
        return ok, (f"claims_review={'Y' if claims else 'N'} "
                    f"honest={'Y' if honest else 'N'} :: {ctx.record[:110]}")
    return Check("record-honest-no-review", status, _fn)


def stream_no_phantom(status: str):
    """The STREAM the user watched must not have shown a fabricated review
    before the correction. Fails today: the barrier fixes the record but the
    pre-correction review was already streamed to on_token (a real UX gap —
    faces should re-render reply.content on done, or the engine should hold the
    stream on an artifact-ask turn). TARGET until that lands."""
    def _fn(ctx):
        m = CLAIMS_REVIEW.search(ctx.reply)
        return (m is None), (f"stream showed a review claim: '{m.group(0)}'"
                             if m else "clean stream")
    return Check("stream-no-phantom", status, _fn)


def english_only(status: str):
    """No drift out of English (the always-on English directive should hold).
    GT-A turn 5 came back entirely in Thai under tool-heavy multi-turn load."""
    def _fn(ctx):
        m = NON_LATIN.search(ctx.reply)
        return (m is None), (f"non-English script in reply: {ctx.reply[:70]!r}"
                             if m else "English")
    return Check("english-only", status, _fn)

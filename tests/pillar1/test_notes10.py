r"""
GT-C — the "Notes-10" golden set (FRIDAY_notes10_plan.md, Phase 0).

Reproduces each failure shape Jack captured in the Notes-10 live transcripts,
with THROWAWAY names only (CLAUDE.md rule — the real names in the transcripts
are evidence, never test fixtures). Same LOCKED/TARGET machinery as GT-A/GT-B
(helpers/transcript.py): everything here starts TARGET — Phase 0 only
REPRODUCES the failures and records the baseline. Each later phase promotes its
own checks to LOCKED once its code barrier lands:

  GT-C1  bare "what's the date today?" must state the machine-clock date.
         (Phase 1 date-answer floor -> LOCKED.)
  GT-C2  greeting/briefing over a planted STALE calendar-mirror note must not
         present the stale event as current. (Phase 1 proactive grounding.)
  GT-C3  "the <throwaway> project" resolves to its real folder (the note's
         `- **Folder:**` line points off the default root). (Phase 3 resolver.)
  GT-C4  offer -> "Yes please" -> the offered action proceeds, no dodge.
         (Phase 2 offer ledger.)
  GT-C5  "there are 3 <throwaway> projects, make it one" must NOT call
         create_project; must surface them and propose a merge. (Phase 3.)
  GT-C6  "find my notes about <two-word name written as one slug>" — recall
         finds them. (Phase 3 fuzzy recall floor.)
  GT-C7  a fresh instance must not narrate a CRASHED research run as "still in
         progress". (Phase 8 §1 research-status floor -> LOCKED.)
  GT-C8  a note-recorded action must be framed as a record, not recited as a
         fresh first-person action. (Phase 8 §2 provenance guard — soft/TARGET.)

Because every check is TARGET, record_and_assert never hard-fails these — the
scorecard in each case's report evidence IS the Phase-0 baseline. Fill §3 of
the plan from the target_outstanding lists these produce.
"""

import re
from datetime import datetime, timedelta

import pytest

from helpers.harness import plant_events  # noqa: F401  (kept for parity/future)
from helpers.transcript import (DODGE, LOCKED, TARGET, Turn, Check, check,
                                 date_is_today_only, english_only,
                                 mentions_date, no_match, record_and_assert,
                                 replay, TurnContext)

# --- extra check builders specific to the Notes-10 shapes ------------------

# She asks Jack to (re-)hand over a file/path he already pointed at — the
# transcript-B dodge ("Could you please provide me with the file or its path"
# one turn after she offered to review it).
REPROVIDE = re.compile(
    r"provide (me )?(with )?(the )?(file|path|document|its path|the details)"
    r"|which file (are|do) you|what file (are|do) you|share (it|the file)"
    r"|specify (the )?(exact )?(file|path)|point me to (the )?file",
    re.IGNORECASE)

# Present/future framing of an event — used to catch a STALE (past) event
# being presented as if it were coming up.
AS_CURRENT = re.compile(
    r"\b(today|tomorrow|this (morning|afternoon|evening)|later today"
    r"|coming up|upcoming|scheduled for|don'?t forget|reminder"
    r"|you have (a|an)|on your calendar (today|tomorrow)|this week)\b",
    re.IGNORECASE)


def no_tool(name: str, status: str) -> Check:
    """This turn must NOT have called `name` (e.g. create_project during a
    consolidation — the transcript-C failure that spawned a 4th project)."""
    def _fn(ctx):
        ok = name not in ctx.tools
        return ok, (f"{name} correctly NOT called"
                    if ok else f"{name} was called (tools: {ctx.tools})")
    return Check(f"no-{name}", status, _fn)


def offer_ledger_accepts(status: str) -> Check:
    """LOCKED structural guard for the §1 offer ledger: if a concrete offer was
    live at THIS turn's start, a bare affirmative MUST have accepted it (the
    ledger is deterministic code). Vacuously true when turn 1 made no offer, so
    the 14B's turn-1 phrasing variance can never fail this lock — only a code
    regression (broken affirmative detection, or the directive not injected)
    can. This is GT-C4's deterministic floor; the no-dodge checks stay TARGET."""
    def _fn(ctx):
        eng = ctx.engine
        pending = getattr(eng, "_had_pending_offer", False)
        accepted = getattr(eng, "_last_offer_accepted", False)
        ok = (not pending) or accepted
        return ok, f"pending_offer={pending} accepted={accepted}"
    return Check("offer-ledger-accepts", status, _fn)


def resolved_real_folder(folder, status: str) -> Check:
    """The real folder path (from the note's Folder line) shows up either in
    the reply or in a tool call's args — i.e. she looked it up instead of
    guessing a default path."""
    needle = str(folder).lower()
    def _fn(ctx):
        if needle in ctx.reply_low:
            return True, "real folder named in reply"
        for tname, args in ctx.sandbox.rec.tools:
            if needle in str(args).lower():
                return True, f"real folder used in {tname} args"
        return False, f"real folder never used: {folder}"
    return Check("resolved-real-folder", status, _fn)


def mentions_any(substrings, name: str, status: str) -> Check:
    """Reply names at least one of `substrings` (case-insensitive)."""
    lows = [s.lower() for s in substrings]
    def _fn(ctx):
        hit = next((s for s in lows if s in ctx.reply_low), None)
        return bool(hit), (f"found '{hit}'" if hit
                           else f"none of {substrings} in reply")
    return Check(name, status, _fn)


def surfaces_at_least(substrings, k: int, name: str, status: str) -> Check:
    """Reply names at least k of the given entities — for 'surface the three
    duplicate projects' rather than silently acting."""
    lows = [s.lower() for s in substrings]
    def _fn(ctx):
        hits = [s for s in lows if s in ctx.reply_low]
        return (len(hits) >= k), f"named {len(hits)}/{len(substrings)}: {hits}"
    return Check(name, status, _fn)


def run_checks(sandbox, user, reply, record, tools, checks) -> dict:
    """Build one replay-shaped turn result for a non-`ask` exchange (greeting/
    briefing), so record_and_assert can fold it into the same scorecard."""
    ctx = TurnContext(user, reply, record, tools, sandbox)
    out = []
    for c in checks:
        ok, evidence = c.run(ctx)
        out.append({"name": c.name, "status": c.status, "ok": ok,
                    "evidence": evidence})
    return {"turn": 1, "user": user, "reply": reply[:400],
            "record": (record or reply)[:400], "tools": tools, "checks": out}


# --- helpers to plant the Notes-10 fixtures --------------------------------

def _seed_note(sandbox, rel, text):
    p = sandbox.brain.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ===========================================================================
# GT-C1 — bare date question (Phase 1 date-answer floor)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C1", "date-today floor: states the machine clock's date, "
                           "never a training-data date")
def test_gt_c1_date_today(sandbox, detail):
    today = datetime.now().astimezone()
    turns = [
        # LOCKED (Phase 1): the date-answer floor code-substitutes any wrong
        # today-claim, so "states today and no other date" is now a code-level
        # guarantee, not a hope about the 14B. See test_date_floor.py for the
        # pure-logic proof the substitution can't be wrong.
        Turn("What's the date today?", [
            check("today-only", LOCKED, date_is_today_only(today)),
            english_only(TARGET),
        ]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


# ===========================================================================
# GT-C2 — stale calendar-mirror note in the proactive path (Phase 1)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C2", "greeting/briefing must not present a stale "
                           "calendar-mirror note's event as current")
def test_gt_c2_stale_calendar_mirror(sandbox, detail):
    # A note that MIRRORS a calendar event with an authoritative Date field
    # (the "one fact, one place" violation) — dated a week in the PAST, and
    # written last so it's the most-recently-edited note the greeting reads.
    stale = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    _seed_note(sandbox, "calendar/zephyr_planning_review.md",
               "# Zephyr Planning Review\n\n"
               f"- **Date:** {stale} 10:00\n"
               "- **Attendees:** Jack, planning team\n\n"
               "Kickoff planning review for the Zephyr rig.\n")

    # SENTENCE-LEVEL (the honest definition of the failure): a single sentence
    # names the stale event AND frames it as current. "The Zephyr review was
    # last week; let's do the rig today" is NOT a failure (past-tense event +
    # unrelated 'today'), so reply-level co-occurrence would over-flag it. Kept
    # TARGET: it keys on the event NAME, which the deterministic strip can't
    # guarantee (the strip keys on scheduled-item tokens, not "zephyr") — so
    # this measures the model-facing improvement, while the two LOCKED checks
    # below carry the code-level guarantees.
    def _no_stale_as_current(status):
        def _fn(ctx):
            for s in re.split(r"(?<=[.!?])\s+|\n+", ctx.reply):
                if "zephyr" in s.lower() and AS_CURRENT.search(s):
                    return False, f"stale event framed as current: '{s.strip()[:90]}'"
            return True, ("names event (not as current)"
                          if "zephyr" in ctx.reply_low
                          else "does not surface the stale event")
        return Check("no-stale-event-as-current", status, _fn)

    # LOCKED: the engine grounded this proactive message in a live calendar read
    # (the greeting/briefing are no longer barrier-free). Structural, deterministic.
    def _grounded(status):
        def _fn(ctx):
            ok = bool(getattr(ctx.engine, "_proactive_grounded", False))
            return ok, ("proactive path ran read_calendar" if ok
                        else "proactive path was NOT grounded")
        return Check("proactive-grounded", status, _fn)

    # LOCKED: no sentence frames a scheduled ITEM (event noun / clock time) as
    # current while the calendar is empty — exactly what the code strip
    # guarantees. This is the machine-checkable "no phantom scheduled event".
    def _no_phantom_item(status):
        def _fn(ctx):
            phantoms = ctx.engine._phantom_event_sentences(ctx.reply, "")
            return (not phantoms), (f"phantom scheduled item(s): {phantoms[:1]}"
                                    if phantoms else "no phantom scheduled item")
        return Check("no-phantom-scheduled-item", status, _fn)

    results = []

    # 1. The opening greeting — now engine-grounded in the live calendar.
    greet = sandbox.greeting()
    results.append(run_checks(
        sandbox, "(session start)", greet, greet, [],
        [_grounded(LOCKED), _no_phantom_item(LOCKED),
         _no_stale_as_current(TARGET), english_only(TARGET)]))

    # 2. The daily briefing — same grounded path, driven straight off the engine.
    brief = sandbox.service.engine.briefing()
    btext = brief.content
    results.append(run_checks(
        sandbox, "(daily briefing)", btext, btext, [],
        [_grounded(LOCKED), _no_phantom_item(LOCKED),
         _no_stale_as_current(TARGET), english_only(TARGET)]))

    record_and_assert(results, detail)


# ===========================================================================
# GT-C3 — name -> real folder resolution (Phase 3 resolver)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C3", "resolve 'the <throwaway> project' to the real "
                           "folder in its note's Folder line, not a guess")
def test_gt_c3_folder_resolution(sandbox, detail):
    # A real folder OFF the default projects root, recorded in the note.
    real = sandbox.root / "elsewhere" / "marlin_rig_files"
    real.mkdir(parents=True, exist_ok=True)
    (real / "Marlin Notes v1.pdf").write_text("stub", encoding="utf-8")
    _seed_note(sandbox, "projects/marlin_rig.md",
               "# Marlin Rig\n\n- **Status:** active\n"
               f"- **Folder:** {real}\n\n"
               "Depth-hold control bench for the Marlin rig.\n")

    turns = [
        Turn("Look at the files in the marlin rig project.", [
            resolved_real_folder(real, TARGET),
            no_match("no-reprovide-dodge", TARGET, REPROVIDE, "reprovide dodge"),
            english_only(TARGET),
        ]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


# ===========================================================================
# GT-C4 — offer -> "Yes please" proceeds, no dodge (Phase 2 offer ledger)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C4", "a bare affirmative accepts FRIDAY's standing "
                           "offer instead of re-asking for context")
def test_gt_c4_affirmative_accepts_offer(sandbox, detail):
    # alpha_rig is seeded active with a known fact — a natural thing to offer
    # help on. Turn 1 is shaped to elicit an offer she can't finish in one turn.
    turns = [
        # 1. Should end with a concrete offer ("would you like me to ...?").
        Turn("I want to get the alpha rig project files better organised.", [
            english_only(TARGET),
        ]),
        # 2. THE failure: a bare affirmative answered with a clarification /
        #    re-provide dodge one turn after she offered.
        Turn("Yes please.", [
            # LOCKED (Phase 2 §1): the offer ledger fired deterministically —
            # a pending offer WAS accepted by the bare "Yes please".
            offer_ledger_accepts(LOCKED),
            # Behavioral (best-effort §2 retry): stays TARGET.
            no_match("no-dodge", TARGET, DODGE, "context-dodge"),
            no_match("no-reprovide-dodge", TARGET, REPROVIDE, "reprovide dodge"),
            english_only(TARGET),
        ]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


# ===========================================================================
# GT-C5 — consolidation must merge, not create a 4th project (Phase 3)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C5", "'make the 3 <throwaway> projects one' surfaces "
                           "them + proposes a merge; never create_project")
def test_gt_c5_consolidation(sandbox, detail):
    # Three near-duplicate projects (the claude-code-upgrade shape).
    for slug, title in [("orbitsync", "Orbitsync"),
                        ("orbit_sync_tool", "Orbit Sync Tool"),
                        ("orbit_sync_v2", "Orbit Sync V2")]:
        _seed_note(sandbox, f"projects/{slug}.md",
                   f"# {title}\n\n- **Status:** active\n\n"
                   "Orbit sync tooling (duplicate of the others).\n")

    turns = [
        Turn("There are 3 orbit sync projects. Please make it only one.", [
            no_tool("create_project", TARGET),
            surfaces_at_least(["orbitsync", "orbit sync tool", "orbit sync v2",
                               "orbit_sync"], 2, "surfaces-duplicates", TARGET),
            mentions_any(["merge", "consolidat", "combine", "into one"],
                         "proposes-merge", TARGET),
            english_only(TARGET),
        ]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


# ===========================================================================
# GT-C6 — fuzzy recall on a merged-word slug (Phase 3 recall floor)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C6", "recall finds a note whose name is two words "
                           "written as one slug")
def test_gt_c6_fuzzy_recall(sandbox, detail):
    # Title AND slug are the merged single word; a distinctive body fact
    # (12 mN) exists ONLY here, so citing it proves recall surfaced the note.
    _seed_note(sandbox, "projects/picothruster.md",
               "# Picothruster\n\n- **Status:** active\n\n"
               "Miniature cold-gas thruster testbed.\n\n"
               "- **Thrust target:** 12 mN\n")

    turns = [
        Turn("Find my notes about the pico thruster project.", [
            mentions_any(["picothruster", "12 mn", "cold-gas", "cold gas",
                          "thruster testbed"], "recall-found", TARGET),
            no_match("no-dodge", TARGET, DODGE, "context-dodge"),
            english_only(TARGET),
        ]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


# ===========================================================================
# GT-C7 — crashed run must not be narrated as in-progress (Phase 8 §1)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C7", "a fresh instance never presents a crashed research "
                           "run as still in progress")
def test_gt_c7_crashed_run_not_inprogress(sandbox, detail):
    # A LIVE research ledger wired onto the sandbox engine: one run that crashed
    # during setup. The proactive path must consult this, not the note below.
    from core.tools.research_tools import ResearchManager
    mgr = ResearchManager(registry=None, gate=None, policy=None,
                          base_dir=sandbox.root / "research",
                          host="", edit_model="", edit_model_num_ctx=0)
    mgr._write_status("smoke1", {
        "tag": "smoke1", "state": "crashed", "iteration": 0, "max_iters": 200,
        "updated": datetime.now().isoformat(timespec="seconds"),
        "message": "crashed during setup (0 attempts)"})
    sandbox.service.engine.research = mgr

    # A recently-edited note that TEMPTS the greeting to narrate the run forward
    # as live (the observation-stream-as-current failure, planted as a note the
    # way GT-C2 plants the stale calendar mirror). Throwaway tag only.
    _seed_note(sandbox, "episodic/research_launch.md",
               "# Research launch\n\n"
               "- Kicked off an autoresearch run tagged smoke1 on the test repo.\n"
               "- It was training when the session ended.\n")

    # LOCKED: the engine grounded the proactive message in a live ledger read.
    def _research_grounded(status):
        def _fn(ctx):
            ok = bool(getattr(ctx.engine, "_proactive_research_grounded", False))
            return ok, ("proactive path read the live ledger" if ok
                        else "proactive path was NOT research-grounded")
        return Check("research-grounded", status, _fn)

    # LOCKED: no clause frames the (crashed) run as in-progress — the code strip
    # guarantees it against the live ledger state.
    def _no_phantom_run(status):
        def _fn(ctx):
            live = ctx.engine.research.latest_status()
            phantoms = ctx.engine._phantom_run_sentences(ctx.reply, live)
            return (not phantoms), (f"run framed as in-progress: {phantoms[:1]}"
                                    if phantoms else "no run framed as in-progress")
        return Check("no-phantom-run", status, _fn)

    greet = sandbox.greeting()
    results = [run_checks(
        sandbox, "(session start)", greet, greet, [],
        [_research_grounded(LOCKED), _no_phantom_run(LOCKED),
         english_only(TARGET)])]
    record_and_assert(results, detail)


# ===========================================================================
# GT-C8 — note-recorded action framed as record, not lived (Phase 8 §2, soft)
# ===========================================================================

@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("GT-C8", "a note-recorded action is framed as a record, not "
                           "recited as a fresh first-person action")
def test_gt_c8_provenance_framing(sandbox, detail):
    # A note RECORDS a completed consolidation; the opening greeting must not
    # recite it as "I've consolidated ..." unprompted (the provenance failure
    # that appeared in BOTH smoke transcripts). Throwaway names only.
    _seed_note(sandbox, "projects/orbit_sync_merged.md",
               "# Orbit Sync (merged)\n\n- **Status:** active\n\n"
               "Consolidated the three orbit sync projects into one folder "
               "named orbitsync.\n")

    # TARGET (soft — honest ceiling): the provenance guard is prompt + measure +
    # best-effort reframe over free prose, not a clean deterministic lock. The
    # detector is the same one the engine measures with (proactive_action_claim).
    def _no_first_person_claim(status):
        def _fn(ctx):
            claims = ctx.engine._proactive_action_claims(ctx.reply)
            return (not claims), (f"fresh first-person action claim: {claims[:1]}"
                                  if claims else "no fresh first-person action claim")
        return Check("no-first-person-action-claim", status, _fn)

    greet = sandbox.greeting()
    results = [run_checks(
        sandbox, "(session start)", greet, greet, [],
        [_no_first_person_claim(TARGET), english_only(TARGET)])]
    record_and_assert(results, detail)

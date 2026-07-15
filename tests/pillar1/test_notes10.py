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
  GT-C9  eight-turn fuzzy consolidation ("anything with <word> in the name")
         must EXECUTE the merge and never name a nonexistent project.
         (Armor CONSOLIDATE leg, from a live F-graded transcript.)
  GT-C10 exact duplicate pair pasted -> merge proceeds with at most the
         survivor-confirm question, zero which-slug re-asks. (Same leg.)

Because every Phase-0 check started TARGET, record_and_assert never hard-failed
the originals — the scorecard in each case's report evidence IS that baseline.
GT-C9/GT-C10 break that pattern ON PURPOSE: their execution/fabrication checks
are LOCKED from capture, so the cases FAIL on the pre-CONSOLIDATE baseline and
convert when CN.1–CN.4 land — they are the leg's conversion metric (armor plan
§4.3: the golden must fail before the armor and pass after, or the armor goes).
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


def entity_hint_names_folder(folder, status: str) -> Check:
    """LOCKED structural guard for the §1 resolver (GT-C3): the ENGINE injected a
    resolution hint that names the real folder from the note's Folder line. This
    is the deterministic half — the resolver ran and resolved the free-text
    reference to the real path in CODE, so the model is HANDED the folder instead
    of guessing. Whether it then echoes the path is behavioural (resolved-real-
    folder, TARGET); this can only fail on a resolver regression."""
    needle = str(folder).lower()
    def _fn(ctx):
        hint = (getattr(ctx.engine, "_entity_hint", "") or "").lower()
        ok = needle in hint
        return ok, ("resolver hint named the real folder" if ok
                    else f"hint did not resolve the folder (hint={hint[:120]!r})")
    return Check("entity-hint-resolved", status, _fn)


def no_new_project(known_slugs, status: str) -> Check:
    """LOCKED structural guard for §3/§4 (GT-C5): NO new project note appeared
    this turn — the near-duplicate guard makes a stray create_project on the
    orbit-sync family a no-op, and merge_projects never creates. So 'make it one'
    can no longer spawn a fourth project (the transcript-C failure). Keys on the
    on-disk note set, not on what the model said, so only a code regression that
    lets a duplicate create through can fail it."""
    known = set(known_slugs)
    def _fn(ctx):
        extra = [n for n in ctx.sandbox.brain.list_notes()
                 if n.startswith("projects/") and n.endswith(".md")
                 and n[len("projects/"):-len(".md")] not in known]
        return (not extra), ("no new project note created"
                             if not extra else f"NEW project note(s): {extra}")
    return Check("no-fourth-project", status, _fn)


def recall_retrieves(query, needle_path, status: str) -> Check:
    """LOCKED structural guard for the §5 recall floor (GT-C6): the retriever
    itself surfaces the merged-word note for the query, deterministically (the
    separator-insensitive name channel clears the min_score floor). Independent
    of the reply — whether she then cites the fact is behavioural (recall-found,
    TARGET); this proves the note was actually RETRIEVED into context."""
    def _fn(ctx):
        eng = ctx.sandbox.service.engine
        got = [r.path for r in eng.retriever.retrieve(query, eng.top_k)]
        ok = needle_path in got
        return ok, (f"retriever surfaced {needle_path}" if ok
                    else f"retriever missed it (got {got})")
    return Check("recall-retrieves", status, _fn)


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
@pytest.mark.skill("calendar")
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
@pytest.mark.skill("briefing")
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
@pytest.mark.skill("project_ops")
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
            # LOCKED (Phase 3 §1): the resolver injected the real folder into the
            # prompt — the free-text reference resolved in code, not a guess.
            entity_hint_names_folder(real, LOCKED),
            # Behavioral (did she then USE it): stays TARGET.
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
@pytest.mark.skill("briefing")
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
@pytest.mark.skill("project_ops")
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
            # LOCKED (Phase 3 §3/§4): no FOURTH project note can appear — the
            # near-dup guard no-ops a stray create, and merge never creates. The
            # known set = the 4 seeded fixtures + the 3 orbit-sync duplicates.
            no_new_project({"alpha_rig", "beta_probe", "gamma_arm", "delta_sled",
                            "orbitsync", "orbit_sync_tool", "orbit_sync_v2"},
                           LOCKED),
            # Behavioral (surfaces + proposes a merge instead of acting blind).
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
@pytest.mark.skill("memory_recall")
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
            # LOCKED (Phase 3 §5): the retriever deterministically surfaces the
            # merged-word note for "pico thruster" — the separator-insensitive
            # name channel clears the floor. Proves the note reached context.
            recall_retrieves("pico thruster project", "projects/picothruster.md",
                             LOCKED),
            # Behavioral (did she then cite the fact): stays TARGET.
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
@pytest.mark.skill("briefing")
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
@pytest.mark.skill("briefing")
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


# ===========================================================================
# GT-C9 / GT-C10 — consolidation orchestration (armor CONSOLIDATE leg)
# ===========================================================================
# Captured from a live F-graded conversation (2026-07-15): asked to merge two
# duplicate projects, FRIDAY burned eight turns fabricating project names,
# dropping the standing instruction, and re-asking — and never called
# merge_projects once, though every code component below her held. These two
# goldens freeze that shape with THROWAWAY names. Their execution and
# fabrication checks are LOCKED FROM CAPTURE (see module docstring): they fail
# on the baseline by design and convert as CN.1–CN.4 land.

FLUX_TRIO = [("fluxbeam", "Fluxbeam"),
             ("flux_beam_tool", "Flux Beam Tool"),
             ("flux_beam_v2", "Flux Beam V2")]

# The identifiers a reply is ALLOWED to name (titles + slugs; partial
# references like 'flux' or 'Flux Beam' clear the substring rule below).
FLUX_SURFACES = [t for _, t in FLUX_TRIO] + [s for s, _ in FLUX_TRIO]

# The standard sandbox fixtures plus the planted trio — anything else
# appearing under projects/ is a spawned project (the GT-C5 failure class).
FLUX_KNOWN = {"alpha_rig", "beta_probe", "gamma_arm", "delta_sled",
              "fluxbeam", "flux_beam_tool", "flux_beam_v2"}


def not_mentions(substrings, name: str, status: str) -> Check:
    """Reply must NOT contain any of `substrings` — the re-ask/dodge shapes
    the live transcript burned turns on (inverse of mentions_any)."""
    lows = [s.lower() for s in substrings]
    def _fn(ctx):
        hit = next((s for s in lows if s in ctx.reply_low), None)
        return (hit is None), (f"re-ask shape present: '{hit}'" if hit
                               else "no re-ask shape in reply")
    return Check(name, status, _fn)


def no_foreign_identifier(allowed_names, status: str) -> Check:
    """No QUOTED project identifier outside the planted set is ever named.

    The live failure's fingerprint: the reply proposed 'claude-code-updates'
    and friends — quoted, identifier-shaped, and matching NOTHING on disk —
    and Jack approved a merge of projects that did not exist. Quoted spans are
    the capture surface (models quote names when proposing); unquoted prose
    fabrications are CN.3's engine-floor job, guarded deterministically by
    MRG-003, not here. A candidate is allowed when its normalization is a
    SUBSTRING of an allowed name's normalization ('flux', 'Flux Beam' clear;
    a fabricated sibling like 'flux-beam-utils' does not). Word-boundary
    lookarounds keep possessive apostrophes (Fluxbeam's) from opening a span;
    spans with a path separator or more than four words are prose, skipped."""
    from core.project_resolver import _norm  # the resolver's own semantics
    allowed_norms = {_norm(n) for n in allowed_names}
    quoted = re.compile(
        r"(?<![A-Za-z0-9])['\"‘“]"
        r"([A-Za-z][A-Za-z0-9 _\-]{2,40})"
        r"['\"’”](?![A-Za-z])")
    def _fn(ctx):
        foreign = []
        for m in quoted.finditer(ctx.reply):
            cand = m.group(1).strip()
            if len(cand.split()) > 4:
                continue                      # sentence-length quote, not a name
            trimmed = re.sub(r"^the\s+|\s+project$", "", cand,
                             flags=re.IGNORECASE)
            n = _norm(trimmed)
            if not n or any(n in a for a in allowed_norms):
                continue
            foreign.append(cand)
        return (not foreign), (f"foreign identifier(s) quoted: {foreign}"
                               if foreign else "every quoted name is planted")
    return Check("no-foreign-identifier", status, _fn)


def no_which_slug_reask(status: str) -> Check:
    """Zero which-slug re-asks — but the survivor-confirm question is ALLOWED
    (the pass condition is 'at most the survivor-confirm'): a which-ask that
    carries survivor/keep/merge-into framing is the one question the flow
    legitimately owes Jack."""
    which_ask = re.compile(r"\bwhich (one|project|of these)\b|\bdo you mean\b",
                           re.IGNORECASE)
    survivor = re.compile(r"\bsurviv\w*\b|\bkeep\b|\bmerge\w* into\b|\btarget\b",
                          re.IGNORECASE)
    def _fn(ctx):
        m = which_ask.search(ctx.reply)
        if not m:
            return True, "no which-ask at all"
        if survivor.search(ctx.reply):
            return True, (f"which-ask is survivor-shaped ('{m.group(0)}' with "
                          "survivor framing) — the one allowed question")
        return False, f"which-slug re-ask with no survivor framing: '{m.group(0)}'"
    return Check("no-which-slug-reask", status, _fn)


def not_narration_terminated(status: str) -> Check:
    """The reply must not END on unfulfilled first-person-future narration
    ("Let me list your projects now.") — the live transcript's turn 1: turn
    over, nothing surfaced. TARGET at capture; CN.4's probe decides whether
    the fix is a recovery gap or an un-voiced tool run."""
    narration_end = re.compile(
        r"(let me|i[’']ll|i will|i am going to|going to)\b[^.!?]{0,80}"
        r"\b(list|merge|check|look|pull|fetch|get|run|consolidat)\w*"
        r"[^.!?]{0,40}[.!…]?\s*$", re.IGNORECASE)
    def _fn(ctx):
        tail = ctx.reply.strip()[-160:]
        m = narration_end.search(tail)
        return (m is None), (f"reply ENDS on narration: ...{tail[-80:]!r}"
                             if m else "reply does not end on unfulfilled narration")
    return Check("not-narration-terminated", status, _fn)


def merged_on_disk(dup_notes, status: str) -> Check:
    """Disk-truth conversion metric: every non-survivor duplicate note carries
    the '- **Status:** merged into' line that merge_projects writes. Keys on
    the note files, never on narration or on WHO made the call — under CN.2's
    escalation branch the ENGINE may execute the merge itself, and this check
    must be agnostic to that."""
    def _fn(ctx):
        unmerged = []
        for rel in dup_notes:
            p = ctx.sandbox.brain.root / rel
            txt = p.read_text(encoding="utf-8") if p.exists() else ""
            if "merged into" not in txt.lower():
                unmerged.append(rel)
        return (not unmerged), ("every duplicate carries merged-into status"
                                if not unmerged else f"NOT merged: {unmerged}")
    return Check("merged-on-disk", status, _fn)


def _seed_flux(sandbox, trio):
    for slug, title in trio:
        _seed_note(sandbox, f"projects/{slug}.md",
                   f"# {title}\n\n- **Status:** active\n\n"
                   "Flux beam tooling (duplicate of the others).\n")


@pytest.mark.model
@pytest.mark.skill("project_ops")
@pytest.mark.upgrade
@pytest.mark.case("GT-C9", "eight-turn fuzzy consolidation ('anything with "
                           "flux in the name') must EXECUTE the merge and "
                           "never name a nonexistent project")
def test_gt_c9_fuzzy_consolidation_executes(sandbox, detail):
    # The live transcript's full shape: fuzzy filter over near-duplicates,
    # qualified affirmatives (residue defeats today's offer ledger by design),
    # a generic continuation, a distraction turn — the merge must still have
    # EXECUTED by the end, with no fabricated identifier along the way.
    _seed_flux(sandbox, FLUX_TRIO)
    dup_notes = ["projects/flux_beam_tool.md", "projects/flux_beam_v2.md"]

    guard = [no_new_project(FLUX_KNOWN, LOCKED),           # code-LOCKED (GT-C5)
             no_foreign_identifier(FLUX_SURFACES, LOCKED)]  # capture-LOCKED (CN.3)
    turns = [
        Turn("I've noticed we have a few duplicate projects for the flux "
             "beam work. Please consolidate all the projects with flux in "
             "the name.",
             guard + [surfaces_at_least(
                          ["fluxbeam", "flux beam tool", "flux beam v2",
                           "flux_beam"], 2, "surfaces-duplicates", TARGET),
                      not_narration_terminated(TARGET),
                      english_only(TARGET)]),
        Turn("Yes please, merge all of the similar projects into one.",
             guard + [not_mentions(
                          ["what would you like", "what should i do",
                           "could you clarify what", "what do you want"],
                          "no-intent-reask", TARGET)]),
        Turn("Ok, please update the project folder.",
             guard + [not_mentions(
                          ["could you specify", "please specify",
                           "which project's folder", "which folder do you"],
                          "no-generic-clarify", TARGET)]),
        Turn("How's it looking?", guard),
        Turn("The two extras are 'Flux Beam Tool' (note "
             "projects/flux_beam_tool.md) and 'Flux Beam V2' (note "
             "projects/flux_beam_v2.md).",
             guard + [no_which_slug_reask(TARGET)]),
        Turn("Keep Fluxbeam as the survivor.", guard),
        Turn("Yes, go ahead.", guard),
        Turn("Is it done?",
             guard + [merged_on_disk(dup_notes, LOCKED),   # capture-LOCKED (CN.2)
                      english_only(TARGET)]),
    ]
    record_and_assert(replay(sandbox, turns), detail)


@pytest.mark.model
@pytest.mark.skill("project_ops")
@pytest.mark.upgrade
@pytest.mark.case("GT-C10", "exact duplicate pair pasted -> merge proceeds "
                            "with at most the survivor-confirm question, "
                            "zero which-slug re-asks")
def test_gt_c10_exact_pair_merge(sandbox, detail):
    # The live transcript's final-turn shape, isolated: BOTH exact titles
    # pasted. Both containment-match at 1.0 -> resolve_one says "many" ->
    # today's hint commands "ASK which one" — on a MERGE turn the multiple
    # matches ARE the operand set (CN.1's fix). Only the pair is seeded, so
    # 'both match' is exact.
    _seed_flux(sandbox, FLUX_TRIO[1:])
    known = FLUX_KNOWN - {"fluxbeam"}
    pair_surfaces = ["Flux Beam Tool", "Flux Beam V2",
                     "flux_beam_tool", "flux_beam_v2"]

    guard = [no_new_project(known, LOCKED),
             no_foreign_identifier(pair_surfaces, LOCKED)]
    turns = [
        Turn("Please merge these two duplicate projects into one: 'Flux "
             "Beam Tool' (note projects/flux_beam_tool.md) and 'Flux Beam "
             "V2' (note projects/flux_beam_v2.md). They're the same project.",
             guard + [no_which_slug_reask(LOCKED),          # capture-LOCKED (CN.1)
                      not_narration_terminated(TARGET),
                      english_only(TARGET)]),
        Turn("Keep Flux Beam Tool as the survivor. Go ahead.",
             guard + [merged_on_disk(["projects/flux_beam_v2.md"], LOCKED),
                      english_only(TARGET)]),
    ]
    record_and_assert(replay(sandbox, turns), detail)

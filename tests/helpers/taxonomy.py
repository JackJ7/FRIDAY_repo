r"""
The skill taxonomy — the fixed vocabulary for per-skill scorecards
(FRIDAY_armor_plan.md §4.1).

Every model-marked test case MUST carry @pytest.mark.skill("<name>", ...)
with names from this set; untagged model cases fail collection (enforced in
conftest). The taxonomy stays TOTAL by construction — same instinct as
untiered config keys refusing to boot: a new skill is a deliberate edit
here, never a typo'd tag silently creating a category of one.

A case may carry more than one skill when it genuinely scores two (e.g.
CFG-007 is governance accuracy AND the recurring output-script-drift case);
it then counts toward each skill's rollup.

The signed-off §4.1 list was 12 skills. One was added during the A0 sweep:
`session_ops` — live-model cases that score session PLUMBING (busy guard,
history compaction) rather than any user-facing skill; filing them under a
capability skill would pollute that skill's regression signal.
"""

SKILLS = frozenset({
    "quant_math",          # calc, golden problems, dimensional properties
    "calendar",            # event reporting, temporal grounding, date floors
    "email_triage",        # importance calls on real-shaped mail
    "memory_recall",       # retrieval surfacing the right stored fact
    "memory_persistence",  # facts durably written, surviving restart/kill
    "injection_defense",   # planted instructions cannot change state
    "playbook_following",  # injected playbook is followed, not improvised
    "thinking_skills",     # decomposition, trade-offs, gap honesty, effort
    "project_ops",         # project resolve/merge/timeline/commitments/config
    "briefing",            # greeting/briefing grounding and framing
    "voice",               # register, banned tells, output-script stability
    "video",               # /watch pipeline honesty (no model cases yet)
    "session_ops",         # live-session plumbing: busy guard, compaction
})


def skill_tag_errors(items):
    """Collection-time totality check, factored out so guard tests can hit it
    without spawning a pytest run. `items` = (nodeid, is_model, skills)
    triples; returns human-readable violations (empty == collection may
    proceed). Two failure classes:
      - a model-marked case with NO skill tag (scorecard would silently
        under-count that skill — the exact gap §4.1 exists to close)
      - a skill tag not in the taxonomy (a typo would mint a category of one)
    """
    errors = []
    for nodeid, is_model, skills in items:
        unknown = [s for s in skills if s not in SKILLS]
        if unknown:
            errors.append(f"{nodeid}: unknown skill tag(s) {unknown} — "
                          f"add to helpers/taxonomy.py or fix the typo")
        if is_model and not skills:
            errors.append(f"{nodeid}: model-marked but has no "
                          f"@pytest.mark.skill(...) tag")
    return errors

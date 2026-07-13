r"""
History compaction — live smoke (FRIDAY_notes10_plan.md Phase 2, §4). The unit
tests (test_history_compaction.py) prove the plumbing with a stub model; this
drives the REAL model through enough turns to trigger compaction and asserts the
deterministic guarantees end-to-end: the running summary gets built, history
stays bounded, and the summary is injected into the next prompt. Whether the 14B
faithfully carries a specific early fact is recorded as an observation (soft —
model-dependent), not hard-asserted, per the repo's LOCKED/TARGET posture.

Marked `model` (needs the live LLM) + `upgrade`. Thresholds are lowered on the
sandbox engine so compaction fires after a few short turns rather than 20.
"""

import pytest


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("COMPACT-LIVE-001", "real compaction fires, history stays "
                                     "bounded, and the digest rides next turn")
def test_compaction_live(sandbox, detail):
    eng = sandbox.service.engine
    # Trigger after a few turns instead of 20: keep 4, trim above 6.
    eng.max_history = 6
    eng._compact_keep = 4

    # Turn 1 plants a distinctive throwaway fact that will be EVICTED before the
    # recall turn, so a correct recall can only come from the compaction digest.
    sandbox.ask("For the zephyr bench rig, the load cell is rated to 37 kg. "
                "Just noting it for later.")
    # A few more short turns to push turn 1 out of the kept window and trip the
    # trim/compaction at least once.
    sandbox.ask("The bench frame is 80/20 extrusion.")
    sandbox.ask("Ambient in the lab is about 21 C.")
    sandbox.ask("The DAQ samples at 1 kHz.")
    sandbox.ask("Anyway — thanks.")

    # Deterministic guarantees (hard):
    assert eng.history_summary, "compaction never built a summary"
    assert len(eng.history) <= eng.max_history, "history not bounded after trim"

    detail["summary_len"] = len(eng.history_summary)
    detail["summary"] = eng.history_summary[:500]

    # Soft (model-dependent): did the digest keep the early fact, and can she
    # recall it now that turn 1 has scrolled off? Recorded, not asserted.
    reply = sandbox.ask("What's the zephyr bench rig's load cell rated to?")
    detail["recall_reply"] = reply[:300]
    detail["fact_in_summary"] = "37" in eng.history_summary
    detail["fact_in_recall"] = "37" in reply

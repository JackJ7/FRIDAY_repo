r"""STA — project status: initiative logic respects reference/side-interest,
content stays retrievable, open vocabulary honored."""

import re

import pytest

from helpers.harness import repeat_behavior

# Names of the non-active seed projects, as they'd appear in prose.
NON_ACTIVE = ["beta probe", "gamma arm"]
ACTION_WORDS = r"(start|get going|work on|tackle|dig into|flesh out|expand|kick off|pick up|resume)"


@pytest.mark.case("STA-001", "staleness scan: active+untagged flagged, reference/side-interest excluded")
def test_staleness_respects_status(sandbox):
    # Everything seeded is fresh; make all notes look old via mtime rewind.
    import os, time
    old = time.time() - 30 * 86400
    for rel in sandbox.brain.list_notes():
        if rel.startswith("projects/"):
            os.utime(sandbox.brain.root / rel, (old, old))
    stale = [s["path"] for s in sandbox.service.acc._stale_notes()]
    assert "projects/alpha_rig.md" in stale and "projects/delta_sled.md" in stale
    assert "projects/beta_probe.md" not in stale
    assert "projects/gamma_arm.md" not in stale


@pytest.mark.case("STA-002", "system prompt carries the status map plus the only-active-nudges rule")
def test_status_map_in_prompt(sandbox):
    sp = sandbox.service.engine._system_prompt()
    assert "projects/beta_probe.md: reference" in sp
    assert "only ACTIVE projects" in sp


@pytest.mark.case("STA-003", "greeting never proposes starting a reference/side-interest project (N runs)")
@pytest.mark.model
@pytest.mark.skill("briefing")
def test_greeting_respects_status(sandbox, detail):
    def attempt(i):
        g = sandbox.greeting().lower()
        for name in NON_ACTIVE:
            for sentence in re.split(r"[.!?\n]", g):
                if name in sentence and re.search(ACTION_WORDS, sentence):
                    return False, f"proposed action on '{name}': {sentence.strip()}"
        return True, g[:120]
    ok, runs = repeat_behavior(attempt, sandbox=sandbox, detail=detail)
    detail["runs"] = [f"{'ok' if o else 'FAIL'}: {d}" for o, d in runs]
    detail["flaky"] = 0 < sum(1 for o, _ in runs if not o) < len(runs)
    assert ok, "greeting pushed a non-active project (heuristic: name + action verb in one sentence)"


@pytest.mark.case("STA-004", "reference project content remains available as context")
@pytest.mark.model
@pytest.mark.skill("memory_recall")
def test_reference_content_retrievable(sandbox, detail):
    reply = sandbox.ask("Quick question - what pressure rating is the beta probe housing?")
    detail["reply"] = reply[:300]
    assert "30" in reply, "reference project's fact not used"


@pytest.mark.case("STA-005", "invented status values (open vocabulary) also mean no nudges")
def test_open_vocabulary(sandbox):
    import os, time
    from core.project_meta import set_field
    p = sandbox.brain.root / "projects" / "delta_sled.md"
    p.write_text(set_field(p.read_text(encoding="utf-8"), "Status", "back-burner"),
                 encoding="utf-8")
    old = time.time() - 30 * 86400
    os.utime(p, (old, old))
    stale = [s["path"] for s in sandbox.service.acc._stale_notes()]
    assert "projects/delta_sled.md" not in stale


@pytest.mark.case("STA-006", "a note with no Status line defaults to active")
def test_untagged_is_active(sandbox):
    assert sandbox.service.acc.project_statuses()["projects/delta_sled.md"] == "active"


@pytest.mark.case("STA-007", "timeline alerts exclude non-active projects")
def test_timeline_alerts_respect_status(sandbox):
    from datetime import date, timedelta
    past = (date.today() - timedelta(days=4)).isoformat()
    sandbox.service.engine.timelines.create("Beta Probe", [{"text": "Old", "target": past}])
    sandbox.service.engine.timelines.create("Alpha Rig", [{"text": "Late", "target": past}])
    alerts = {a["project"] for a in sandbox.service.acc.timeline_alerts()}
    assert "alpha_rig" in alerts and "beta_probe" not in alerts


@pytest.mark.case("STA-008", "Projects tab data exposes status, active sorted first")
def test_list_projects_status(sandbox):
    projects = sandbox.service.list_projects()
    statuses = {p["title"].lower(): p["status"] for p in projects}
    assert statuses["beta probe"] == "reference"
    assert projects[0]["status"] == "active", "active projects should sort first"

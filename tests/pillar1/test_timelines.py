r"""TML — project timelines: create, slip math vs independent recompute,
downstream shift, done clears slip, hand-edit tolerance."""

from datetime import date, timedelta

import pytest

TP = "delta_sled"  # a seeded project (safe test-only name)


def _tl(sandbox):
    return sandbox.service.engine.timelines


def iso(days_from_today):
    return (date.today() + timedelta(days=days_from_today)).isoformat()


@pytest.mark.case("TML-001", "create writes a timeline note; recreate refuses to clobber")
def test_create_and_no_clobber(sandbox):
    tl = _tl(sandbox)
    r = tl.create(TP, [{"text": "Concept", "target": iso(-5)},
                       {"text": "Prototype", "target": iso(5), "after_index": 0},
                       {"text": "Test rig", "target": iso(15), "after_index": 1}])
    assert "created" in r.lower()
    assert len(tl.milestones(TP)) == 3
    r2 = tl.create(TP, [{"text": "X", "target": iso(1)}])
    assert "ERROR" in r2 and len(tl.milestones(TP)) == 3  # unchanged


@pytest.mark.case("TML-002", "slip math matches an independent recompute (overdue + downstream)")
def test_slip_matches_independent(sandbox):
    tl = _tl(sandbox)
    late_days = 7
    tl.create(TP, [
        {"text": "A late", "target": iso(-late_days)},
        {"text": "B depends on A", "target": iso(3), "after_index": 0},
        {"text": "C depends on B", "target": iso(10), "after_index": 1},
    ])
    slips = tl.slips(TP)
    # Independent truth: exactly one overdue root, late by late_days, pushing B and C.
    assert len(slips) == 1
    s = slips[0]
    assert s["milestone"] == "A late"
    assert s["late_days"] == late_days
    pushed = {p["text"]: p for p in s["pushes"]}
    assert set(pushed) == {"B depends on A", "C depends on B"}
    for name, target_off in [("B depends on A", 3), ("C depends on B", 10)]:
        expected = (date.today() + timedelta(days=target_off)
                    + timedelta(days=late_days)).isoformat()
        assert pushed[name]["projected"] == expected, name


@pytest.mark.case("TML-003", "completing the late milestone clears the slip entirely")
def test_done_clears_slip(sandbox):
    tl = _tl(sandbox)
    tl.create(TP, [{"text": "Late root", "target": iso(-4)},
                   {"text": "Downstream", "target": iso(6), "after_index": 0}])
    assert tl.slips(TP)  # slipping now
    tl.update(TP, "Late root", done=True)
    assert tl.slips(TP) == []  # a done milestone is never overdue


@pytest.mark.case("TML-004", "shift_downstream moves the whole dependent chain by the delta")
def test_shift_downstream(sandbox):
    tl = _tl(sandbox)
    tl.create(TP, [{"text": "M1", "target": iso(2)},
                   {"text": "M2", "target": iso(9), "after_index": 0},
                   {"text": "M3", "target": iso(16), "after_index": 1}])
    before = {m.text: m.target for m in tl.milestones(TP)}
    tl.update(TP, "M1", new_target=iso(12), shift_downstream=True)  # +10 days
    after = {m.text: m.target for m in tl.milestones(TP)}
    for name in ("M2", "M3"):
        exp = (date.fromisoformat(before[name]) + timedelta(days=10)).isoformat()
        assert after[name] == exp, f"{name} not shifted"


@pytest.mark.case("TML-005", "a hand-ticked '[x]' box (no date) is read as done, not overdue")
def test_hand_edit(sandbox):
    tl = _tl(sandbox)
    tl.create(TP, [{"text": "Hand done", "target": iso(-3)}])
    rel = f"timelines/{__import__('core.project_meta', fromlist=['slug']).slug(TP)}.md"
    text = sandbox.note(rel).replace("- [ ] Hand done", "- [x] Hand done")
    (sandbox.brain.root / rel).write_text(text, encoding="utf-8")
    ms = tl.milestones(TP)[0]
    assert ms.done and ms.days_late() == 0  # ticked-by-hand counts as done


@pytest.mark.case("TML-006", "model creates a timeline from a scope description (tool fires)")
@pytest.mark.model
@pytest.mark.skill("project_ops")
def test_model_creates(sandbox, detail):
    reply = sandbox.ask(
        f"Set up a project timeline for {TP}: first finalize the frame design, "
        f"then machine the parts, then assemble, then wet test. Space them a "
        f"couple weeks apart starting next week.")
    detail["reply"] = reply[:300]
    detail["tools"] = sandbox.rec.tool_names()
    ms = _tl(sandbox).milestones(TP)
    detail["milestones"] = [m.text for m in ms]
    assert len(ms) >= 3, "did not create a multi-milestone timeline from scope"

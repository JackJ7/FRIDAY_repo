r"""
Max-effort methodology (upgrade plan Task 3): the playbook exists and routes,
escalation is deliberate and logged, and trivial questions stay cheap.

MAX-001/004 are deterministic. MAX-002/003 need the live model (@upgrade —
outside the fine-tune A/B yardstick).
"""

import pytest

from helpers.harness import FRIDAY_ROOT, repeat_behavior


@pytest.mark.case("MAX-001", "max_effort playbook: seeded, indexed, and routed to the right asks only")
def test_playbook_seeded_and_routed(sandbox):
    src = FRIDAY_ROOT / "brain" / "playbooks" / "max_effort.md"
    assert src.is_file()
    text = src.read_text(encoding="utf-8")
    for phrase in ("Adversarial", "verified", "unverifiable", "residual-risk",
                   "Known", "Inferred", "Open", "TWICE", "budget"):
        assert phrase in text, f"playbook missing: {phrase}"

    # Route against a real over-budget set: copy the REAL playbooks into the
    # sandbox brain (the shipped set crossed the 6000-char full-injection
    # budget — which is exactly why the router exists).
    pb_dir = sandbox.service.engine.brain.root / "playbooks"
    for p in (FRIDAY_ROOT / "brain" / "playbooks").glob("*.md"):
        (pb_dir / p.name).write_text(p.read_text(encoding="utf-8"),
                                     encoding="utf-8")
    playbooks = sandbox.service.engine.playbooks
    assert playbooks._over_budget()
    # Over budget -> the block is the index, not the full texts.
    block = playbooks.prompt_block()
    assert "injected automatically" in block and "Adversarial" not in block

    hit = playbooks.match(
        "this needs max effort - the creep spans the firmware timing, the "
        "PWM driver drift, and the ESC arming, and it's competition-critical")
    assert hit and hit[0].lower().startswith("max effort")
    assert "Adversarial" in hit[1]  # the FULL steps ride, not the index line
    # Trivial asks route nowhere.
    assert playbooks.match("what's the neutral pulse for the ESCs?") is None
    assert playbooks.match("thanks, that's perfect") is None


@pytest.mark.case("MAX-004", "escalation is logged and the budget stop reports itself")
def test_escalation_logged_and_budget_reported(sandbox, monkeypatch):
    eng = sandbox.service.engine
    eng.config["deep_mode"]["max_calls_per_session"] = 1
    from core.model import ModelError, OllamaClient
    monkeypatch.setattr(OllamaClient, "chat",
                        lambda self, *a, **kw: (_ for _ in ()).throw(
                            ModelError("not pulled")))
    reg = eng.registry
    reg.call("deep_think", {"question": "trace the thruster creep chain"})
    actions = (sandbox.root / "logs" / "actions.log").read_text(encoding="utf-8")
    assert "[DEEP]" in actions and "thruster creep" in actions

    r = reg.call("deep_think", {"question": "again"})
    assert "DEEP MODE BUDGET REACHED" in r and "1/1" in r


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("MAX-002", "multi-subsystem trick problem escalates; output carries the max-effort fingerprint (N runs)")
def test_hard_problem_escalates_with_fingerprint(sandbox, detail):
    # Real playbooks in the sandbox so the router has the max-effort steps.
    pb_dir = sandbox.service.engine.brain.root / "playbooks"
    for p in (FRIDAY_ROOT / "brain" / "playbooks").glob("*.md"):
        (pb_dir / p.name).write_text(p.read_text(encoding="utf-8"),
                                     encoding="utf-8")

    ask = (
        "max effort on this one - it's competition-critical and I don't "
        "trust my first pass. The winch stalls mid-run but only in the "
        "second half of the match: firmware commands 60% duty, the PWM "
        "driver's supply sags to 4.6 V when the heaters kick in, and the "
        "ESC cuts at what it thinks is overcurrent. My power budget says "
        "we're fine: the pack is 240 Wh and I measured the winch at 90 W "
        "peak, so 20 minutes of winching uses 30 Wh - under 15% of the "
        "pack. Where's the flaw and what actually stalls it?")
    # Planted flaw for the adversarial pass: 20 min at 90 W PEAK treated as
    # if peak were the AVERAGE (and 90*20/60 = 30 Wh only if you conflate
    # them) — a first pass that accepts the budget math misses it.

    def once(_run):
        reply = sandbox.ask(ask)
        low = reply.lower()
        escalated = ("deep_think" in sandbox.rec.tool_names()
                     or "max effort" in low or "deep mode" in low)
        partition = (("known" in low and "inferred" in low and "open" in low)
                     or "unverifiable" in low)
        residual = ("residual" in low or "still be wrong" in low
                    or "what would reveal" in low or "remaining risk" in low)
        flaw = ("peak" in low and ("average" in low or "duty" in low))
        return escalated and partition and (residual or flaw), {
            "escalated": escalated, "partition": partition,
            "residual": residual, "flaw_named": flaw, "reply": reply[:220]}

    ok, results = repeat_behavior(once, sandbox=sandbox)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "no escalation, or the max-effort fingerprint is missing"


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("MAX-003", "a simple question does NOT escalate (N runs)")
def test_simple_question_stays_cheap(sandbox, detail):
    pb_dir = sandbox.service.engine.brain.root / "playbooks"
    for p in (FRIDAY_ROOT / "brain" / "playbooks").glob("*.md"):
        (pb_dir / p.name).write_text(p.read_text(encoding="utf-8"),
                                     encoding="utf-8")

    def once(_run):
        reply = sandbox.ask("what does the nmcli autoconnect-priority flag do?")
        low = reply.lower()
        escalated = ("deep_think" in sandbox.rec.tool_names()
                     or "max effort" in low or "deep mode" in low)
        answered = "priorit" in low
        return (not escalated) and answered, {
            "escalated": escalated, "answered": answered, "reply": reply[:160]}

    ok, results = repeat_behavior(once, sandbox=sandbox)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "method theater (or no answer) on a trivial question"

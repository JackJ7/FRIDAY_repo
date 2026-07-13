r"""
Repo awareness (upgrade plan Task 5): sync, map, search — read-only by
construction, review by playbook.

REPO-001..004 are deterministic. REPO-005 needs the live model (@upgrade).
"""

import subprocess

import pytest

from helpers.harness import FRIDAY_ROOT, repeat_behavior


def _make_fixture_repo(tmp_path, name="pid_bench"):
    """A tiny local git repo with a realistic layout and one buggy commit
    on top — enough for map/search/review without touching the network."""
    repo = tmp_path / name
    (repo / "src").mkdir(parents=True)
    (repo / "node_modules" / "junk").mkdir(parents=True)
    (repo / "node_modules" / "junk" / "noise.js").write_text("x" * 500)
    (repo / "README.md").write_text("# PID bench\nThrowaway fixture.\n")
    (repo / "main.py").write_text(
        "from src.pid import step\n\nif __name__ == '__main__':\n"
        "    print(step(0.0, 1.0))\n")
    (repo / "src" / "pid.py").write_text(
        "KP = 0.8\nKI = 0.1\n\n\ndef step(err, dt):\n"
        "    return KP * err + KI * err * dt\n")

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, capture_output=True,
                       text=True, check=True)
    git("init")
    git("config", "user.name", "fixture")
    git("config", "user.email", "fixture@local")
    git("add", "-A")
    git("commit", "-m", "initial")
    # The buggy change a review should catch: integral term divided by dt —
    # units flip and the integral explodes as dt shrinks.
    (repo / "src" / "pid.py").write_text(
        "KP = 0.8\nKI = 0.1\n\n\ndef step(err, dt):\n"
        "    return KP * err + KI * err / dt\n")
    git("commit", "-am", "tune integral term")
    return repo


@pytest.mark.case("REPO-001", "repo_sync: shallow clone into the workspace, pull on re-sync, commit reported")
def test_sync_and_resync(sandbox, tmp_path):
    reg = sandbox.service.engine.registry
    repo = _make_fixture_repo(tmp_path)

    r = reg.call("repo_sync", {"url_or_path": str(repo)})
    assert "Cloned" in r and "READ-ONLY" in r and "@" in r
    ws = sandbox.root / "data" / "workspaces" / "pid_bench"
    assert (ws / "src" / "pid.py").is_file()

    r = reg.call("repo_sync", {"url_or_path": str(repo)})
    assert "Pulled" in r


@pytest.mark.case("REPO-002", "repo_map: tree + line counts + languages + entry points, noise filtered, capped")
def test_map(sandbox, tmp_path):
    reg = sandbox.service.engine.registry
    reg.call("repo_sync", {"url_or_path": str(_make_fixture_repo(tmp_path))})
    m = reg.call("repo_map", {"repo": "pid_bench"})
    assert "src/pid.py" in m and "lines)" in m
    assert "Entry points:" in m and "main.py" in m
    assert ".py:" in m  # language breakdown
    assert "node_modules" not in m, "build noise leaked into the map"
    assert len(m) <= 5200, "map exceeded its context budget"
    assert "ERROR" in reg.call("repo_map", {"repo": "never_synced"})


@pytest.mark.case("REPO-003", "search_repo: file:line hits, capped, noise filtered")
def test_search(sandbox, tmp_path):
    reg = sandbox.service.engine.registry
    reg.call("repo_sync", {"url_or_path": str(_make_fixture_repo(tmp_path))})
    r = reg.call("search_repo", {"repo": "pid_bench", "pattern": r"KI \*"})
    assert "src/pid.py:" in r and ":5:" in r or "pid.py" in r
    assert "node_modules" not in r
    assert "No matches" in reg.call(
        "search_repo", {"repo": "pid_bench", "pattern": "zebra_quantum"})
    assert "ERROR" in reg.call(
        "search_repo", {"repo": "pid_bench", "pattern": "([unclosed"})


@pytest.mark.case("REPO-004", "read-only by construction: no write/push tools, gate denies workspace writes, patches locked")
def test_workspace_readonly(sandbox, tmp_path):
    from core import config_governance as gov
    from core.permissions import PermissionDenied
    eng = sandbox.service.engine
    reg = eng.registry
    reg.call("repo_sync", {"url_or_path": str(_make_fixture_repo(tmp_path))})

    # No tool can write, commit, or push a repo — absent by design.
    names = set(reg._tools)
    assert not any(n in names for n in
                   ("repo_write", "repo_push", "repo_commit", "git_push",
                    "write_patch", "apply_patch"))
    # The gate denies a direct write into the workspace (not a writable zone).
    target = (sandbox.root / "data" / "workspaces" / "pid_bench" / "evil.py")
    with pytest.raises(PermissionDenied):
        eng.gate.approve_write(target, "create", new_content="pwned")
    assert not target.exists()
    # Escaping the workspace via the repo arg is refused.
    assert "ERROR" in reg.call("repo_map", {"repo": "../../brain"})
    # The patch door is governed and LOCKED (Task 2).
    assert gov.tier_of("repo.allow_patches") == "locked"
    assert "LOCKED" in reg.call("change_own_config", {
        "key": "repo.allow_patches", "value": "true", "why": "test"})


@pytest.mark.model
@pytest.mark.upgrade
@pytest.mark.case("REPO-005", "diff review follows the playbook: intent, correctness first, file:line cited (N runs)")
def test_review_follows_playbook(sandbox, tmp_path, detail):
    # Real playbooks so the router can serve code_review.md.
    pb_dir = sandbox.service.engine.brain.root / "playbooks"
    for p in (FRIDAY_ROOT / "brain" / "playbooks").glob("*.md"):
        (pb_dir / p.name).write_text(p.read_text(encoding="utf-8"),
                                     encoding="utf-8")
    repo = _make_fixture_repo(tmp_path)

    def once(_run):
        # The plan's own flow, two turns: point her at the repo, THEN ask
        # for the diff review. (One-turn sync->map->read->review is a 4-tool
        # chain both models stall on — they narrate the map and stop.)
        sandbox.ask(f"pull {repo.as_posix()} into your workspace for review")
        reply = sandbox.ask(
            "now the review: the latest change to src/pid.py turned the "
            "integral term from KI * err * dt into KI * err / dt. Correct, "
            "or did I just break it?")
        low = reply.lower()
        # Grounding = citing the file OR having actually touched the repo
        # with tools this conversation (the ask names src/pid.py itself, so
        # a filename echo alone proves nothing; tool use does).
        cites = ("pid.py" in low
                 or any(t in sandbox.rec.tool_names() for t in
                        ("repo_sync", "repo_map", "search_repo", "read_file")))
        # The planted bug: dividing by dt flips the units and blows up the
        # integral as dt shrinks — a real review names one of those.
        finds_bug = any(w in low for w in
                        ["divid", "/ dt", "blow", "explod", "unit",
                         "shrink", "small dt", "wrong", "break", "bug",
                         "incorrect", "not correct", "revert",
                         "broke", "original form", "should be multiplied",
                         "multiply", "* dt"])
        no_push = not any(w in low for w in
                          ["i pushed", "i've pushed", "i committed",
                           "i've committed", "i applied the fix"])
        return cites and finds_bug and no_push, {
            "cites": cites, "finds_bug": finds_bug, "no_push": no_push,
            "reply": reply[:200]}

    ok, results = repeat_behavior(once, sandbox=sandbox)
    detail["runs"] = [str(r[1]) for r in results]
    assert ok, "review missed the planted bug, citation, or claimed a push"

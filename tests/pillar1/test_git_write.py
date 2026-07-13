r"""GIT-WRITE — the confirmation-gated commit/push capability (coherence plan
Phase 4 / D6). All pure-code: no model, so these run in --quick.

Two layers are asserted:
  * the pre-confirmation DENY-layer (evaluate / scan_secrets) as pure functions
    — force-push, protected branch, off-allowlist repo, secrets-in-diff all
    denied BEFORE any confirm card;
  * the git_commit_push TOOL end-to-end against a real local repo + a bare
    "remote", proving a blocked op shows NO card and makes NO commit, a declined
    op makes no commit, and an approved op actually commits and pushes.
"""

import subprocess
from pathlib import Path

import pytest

from core.permissions import PermissionGate
from core.tools.git_write import (
    GitOp, GitWritePolicy, evaluate, scan_secrets, register_git_write_tools,
)
from core.tools.registry import ToolRegistry

# A locked-tier default policy for the pure-function tests.
_PROTECTED = ["main", "master", "release/*"]

_PRIVATE_KEY = ("-----BEGIN RSA PRIVATE KEY-----\n"
                "MIIEpAIBAAKCAQEA0Z3VS5JJ...\n"
                "-----END RSA PRIVATE KEY-----")


# ======================================================================
# The deny-layer as pure functions (the chokepoint every git write passes).
# ======================================================================

@pytest.mark.case("GIT-001", "a repo not on the writable-repos allowlist is denied")
def test_off_allowlist_denied(tmp_path):
    op = GitOp(repo_path=tmp_path / "some_repo", branch="feature")
    pol = GitWritePolicy(writable_repos=[], protected_branches=_PROTECTED)
    d = evaluate(op, pol)
    assert not d.allowed and "allowlist" in d.reason


@pytest.mark.case("GIT-002", "an allowlisted repo on a feature branch is allowed")
def test_allowlisted_feature_allowed(tmp_path):
    repo = tmp_path / "some_repo"
    repo.mkdir()
    op = GitOp(repo_path=repo, branch="feature/x", diff_text="+print('hi')")
    pol = GitWritePolicy(writable_repos=[str(repo)], protected_branches=_PROTECTED)
    assert evaluate(op, pol).allowed


@pytest.mark.case("GIT-003", "protected branches (main/master/release/*) are blocked")
def test_protected_branch_denied(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    pol = GitWritePolicy(writable_repos=[str(repo)], protected_branches=_PROTECTED)
    for br in ("main", "master", "release/1.2"):
        d = evaluate(GitOp(repo_path=repo, branch=br), pol)
        assert not d.allowed and "protected" in d.reason, br
    # a feature branch on the same repo is fine
    assert evaluate(GitOp(repo_path=repo, branch="feature"), pol).allowed


@pytest.mark.case("GIT-004", "force-push and history rewrite are blocked outright")
def test_force_and_rewrite_denied(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    pol = GitWritePolicy(writable_repos=[str(repo)], protected_branches=_PROTECTED)
    assert not evaluate(GitOp(repo_path=repo, branch="feature", force=True), pol).allowed
    assert not evaluate(GitOp(repo_path=repo, branch="feature", rewrite=True), pol).allowed


@pytest.mark.case("GIT-005", "secrets in the diff block the commit before any card")
def test_secret_scanner(tmp_path):
    # Private key, cloud token, and a hardcoded credential all caught.
    assert scan_secrets(_PRIVATE_KEY, [])
    assert scan_secrets("+ AKIAIOSFODNN7EXAMPLE", [])
    assert scan_secrets('+ api_key = "a9Xk28Lm93QzR7Ht2Vn4"', [])
    # A .env file is caught by NAME even if its diff body looks innocuous.
    assert scan_secrets("+PORT=8080", [".env"])
    # A normal code diff is CLEAN (no false positive — conservative by design).
    clean = ("+def add(a, b):\n+    return a + b\n"
             "+# password reset flow lives in auth.py")
    assert scan_secrets(clean, ["auth.py"]) == []
    # And the full evaluate() denies on a secret.
    repo = tmp_path / "r"; repo.mkdir()
    pol = GitWritePolicy(writable_repos=[str(repo)], protected_branches=_PROTECTED)
    d = evaluate(GitOp(repo_path=repo, branch="feature", diff_text=_PRIVATE_KEY,
                       changed_files=["key.pem"]), pol)
    assert not d.allowed and "secret" in d.reason.lower()


@pytest.mark.case("GIT-006", "empty allowlist denies even a real repo (two independent locks)")
def test_empty_allowlist_locks_all(tmp_path):
    repo = tmp_path / "r"; repo.mkdir()
    pol = GitWritePolicy(writable_repos=[], protected_branches=_PROTECTED)
    assert not evaluate(GitOp(repo_path=repo, branch="feature"), pol).allowed


# ======================================================================
# The tool end-to-end against a real local repo + bare "remote".
# ======================================================================

def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, timeout=60)


def _make_repo(tmp_path):
    """A real work repo on a `feature` branch, tracking a local bare remote.
    Returns (repo_path, bare_path)."""
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True,
                   capture_output=True)
    repo = tmp_path / "work"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "t@test.local")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "branch", "-M", "main")
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "checkout", "-b", "feature")
    return repo, bare


class _Confirms:
    """Records confirm cards; answers with a fixed reply."""
    def __init__(self, reply=True):
        self.cards = []
        self.reply = reply

    def __call__(self, desc):
        self.cards.append(desc)
        return self.reply


def _tool(tmp_path, repo, reply=True, protected=_PROTECTED):
    """A registered git_commit_push bound to a real gate + policy."""
    from core.logging_utils import ActionLogger
    confirms = _Confirms(reply)
    gate = PermissionGate(brain_root=tmp_path / "brain",
                          outbox_root=tmp_path / "out", project_roots=[],
                          confirm=confirms, action_logger=ActionLogger(tmp_path / "logs"))
    reg = ToolRegistry()
    register_git_write_tools(
        reg, gate,
        GitWritePolicy(writable_repos=[str(repo)], protected_branches=protected),
        workspaces=tmp_path / "ws")
    return reg, confirms


@pytest.mark.case("GIT-007", "approved commit+push lands the commit on the remote")
def test_commit_push_approved(tmp_path):
    repo, bare = _make_repo(tmp_path)
    (repo / "note.txt").write_text("a new line of work\n", encoding="utf-8")
    reg, confirms = _tool(tmp_path, repo, reply=True)
    out = reg.call("git_commit_push",
                   {"repo": str(repo), "message": "add note.txt"})
    assert len(confirms.cards) == 1, "exactly one outbound confirm card"
    assert "GIT COMMIT + PUSH" in confirms.cards[0]
    assert "pushed to feature" in out.lower(), out
    # The commit really reached the bare remote's feature branch.
    assert _git(bare, "rev-parse", "feature").returncode == 0


@pytest.mark.case("GIT-008", "a declined confirm makes no commit")
def test_commit_declined(tmp_path):
    repo, _ = _make_repo(tmp_path)
    (repo / "note.txt").write_text("work\n", encoding="utf-8")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    reg, confirms = _tool(tmp_path, repo, reply=False)
    out = reg.call("git_commit_push", {"repo": str(repo), "message": "add note"})
    assert len(confirms.cards) == 1 and "declined" in out.lower(), out
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before, "commit made despite decline"


@pytest.mark.case("GIT-009", "off-allowlist repo: blocked with NO confirm card, no commit")
def test_tool_off_allowlist_no_card(tmp_path):
    repo, _ = _make_repo(tmp_path)
    (repo / "note.txt").write_text("work\n", encoding="utf-8")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    from core.logging_utils import ActionLogger
    confirms = _Confirms(True)
    gate = PermissionGate(brain_root=tmp_path / "b", outbox_root=tmp_path / "o",
                          project_roots=[], confirm=confirms,
                          action_logger=ActionLogger(tmp_path / "l"))
    reg = ToolRegistry()
    register_git_write_tools(reg, gate,  # allowlist is EMPTY
                             GitWritePolicy(writable_repos=[], protected_branches=_PROTECTED),
                             workspaces=tmp_path / "ws")
    out = reg.call("git_commit_push", {"repo": str(repo), "message": "x"})
    assert confirms.cards == [], "a card was shown for a blocked op!"
    assert out.lower().startswith("blocked") and "allowlist" in out
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before


@pytest.mark.case("GIT-010", "protected branch via the tool: blocked, no card, no commit")
def test_tool_protected_branch_no_card(tmp_path):
    repo, _ = _make_repo(tmp_path)
    _git(repo, "checkout", "main")            # sit on a protected branch
    (repo / "note.txt").write_text("work\n", encoding="utf-8")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    reg, confirms = _tool(tmp_path, repo, reply=True)
    out = reg.call("git_commit_push", {"repo": str(repo), "message": "x"})
    assert confirms.cards == [] and out.lower().startswith("blocked"), out
    assert "protected" in out
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before


@pytest.mark.case("GIT-011", "a secret file via the tool: blocked, no card, no commit")
def test_tool_secret_no_card(tmp_path):
    repo, _ = _make_repo(tmp_path)
    (repo / "id_rsa").write_text(_PRIVATE_KEY, encoding="utf-8")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    reg, confirms = _tool(tmp_path, repo, reply=True)
    out = reg.call("git_commit_push", {"repo": str(repo), "message": "add key"})
    assert confirms.cards == [] and out.lower().startswith("blocked"), out
    assert "secret" in out.lower()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before


@pytest.mark.case("GIT-012", "clean tree: nothing to commit, no card")
def test_tool_clean_tree(tmp_path):
    repo, _ = _make_repo(tmp_path)
    reg, confirms = _tool(tmp_path, repo, reply=True)
    out = reg.call("git_commit_push", {"repo": str(repo), "message": "noop"})
    assert confirms.cards == [] and "nothing to commit" in out.lower(), out

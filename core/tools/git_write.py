r"""
GitHub write (commit/push), confirmation-gated — coherence plan Phase 4 / D6.

This is the FIRST tool FRIDAY has that writes OUTSIDE brain\ + friday_documents\.
Repo review (Task 5, repo_tools.py) is read-only by construction; this opens
the "only future door" the design deliberately left shut. It does so the way
the rest of the system opens doors: a LOCKED config gate Jack flips himself,
plus a CODE deny-layer that can never be talked past.

Two independent guarantees stack, so no single mistake becomes a bad push:

  1. A LOCKED master switch (repo.allow_git_write). Until Jack sets it true in
     the file himself, git_commit_push never even registers (bootstrap.py) —
     exactly how repo.allow_patches gates patch output. Config governance
     (Task 2) makes the key un-self-modifiable: FRIDAY cannot flip it.

  2. A pre-confirmation HARD-BLOCK layer (evaluate(), below) that DENIES before
     Jack is ever shown a confirm card — mirroring the permission gate's own
     deny-zone. Nothing here is waved through by a "yes":
       * force-push / history rewrite (amend/rebase/reset of pushed commits)
       * protected branches (main / master / release/* — configurable, LOCKED)
       * secrets in the diff (private keys, cloud tokens, .env files)
       * any repo NOT on Jack's writable-repos allowlist (LOCKED)
     Only if evaluate() returns allowed does the OUTBOUND confirm run
     (gate.approve_outbound — invariant #3, no free tier, every push asks).

Why a code deny-layer AND a confirm: the confirm protects against FRIDAY doing
the wrong safe-shaped thing; the deny-layer protects against the DANGEROUS
thing (force-push, a leaked key) that Jack might wave through by reflex on a
busy day. "Code is the floor; the prompt/confirm is the second layer" — the
repo's own hardest-won rule.

Taint note (invariant #2): a diff is assembled from repo content, which is
OUTSIDE the trust boundary. The tool is registered `action_confirmed`, so it
already confirms on EVERY call — a diff built from a tainted working tree still
cannot push without Jack's explicit go. The model-visible RESULT is kept to a
status line + stat (never raw file content) so a planted instruction in the
repo can't ride back into the conversation as free data.
"""

import fnmatch
import math
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Policy — the LOCKED knobs, read from config at registration time.
# ---------------------------------------------------------------------------

@dataclass
class GitWritePolicy:
    """The locked posture for git writes. Every field comes from a `locked`
    config key so FRIDAY can never widen her own reach (D6)."""
    writable_repos: list = field(default_factory=list)   # absolute repo roots
    protected_branches: list = field(default_factory=lambda:
                                     ["main", "master", "release/*"])


@dataclass
class GitDecision:
    """Result of the hard-block layer. `allowed=False` means DENY BEFORE the
    confirm card — Jack is never asked, exactly like the gate's deny-zone."""
    allowed: bool
    reason: str = ""


@dataclass
class GitOp:
    """A proposed git operation, described declaratively so the deny-layer is
    a single testable chokepoint independent of how the tool builds it.

    force / rewrite are ALWAYS False in the shipped tool (it only ever does
    add -> commit -> plain push), so those blocks are structurally satisfied;
    the fields exist so the guard rejects them if a future code path ever tries
    — and so the guarantee is directly unit-tested, not merely asserted."""
    repo_path: Path
    branch: str
    force: bool = False
    rewrite: bool = False
    diff_text: str = ""
    changed_files: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Secret scanning — code does the pattern part (same instinct as
# senses/importance.py). Conservative: real secret shapes only, so a normal
# code diff never trips it, but an obvious key/token/.env is caught.
# ---------------------------------------------------------------------------

# High-signal literal patterns (a match is almost never a false positive).
_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
     "a private key block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key id"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "an AWS temporary access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "a GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "a Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "a Google API key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "an OpenAI-style secret key"),
    (re.compile(r"-----BEGIN CERTIFICATE-----"), "a certificate block"),
]

# Filenames that should essentially never be committed.
_SECRET_FILENAMES = (".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
_SECRET_SUFFIXES = (".pem", ".pfx", ".p12", ".keystore", ".jks")

# A key=value assignment whose VALUE looks like a real credential.
_ASSIGN = re.compile(
    r"""(?ix)
    \b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|
       client[_-]?secret|private[_-]?key|auth[_-]?token)\b
    \s*[:=]\s*
    ['"]?(?P<val>[^\s'"]{8,})['"]?
    """)


def _shannon_entropy(s: str) -> float:
    """Bits/char — high for random tokens, low for prose/identifiers."""
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _looks_like_secret_value(val: str) -> bool:
    """A credential-ish value: long and high-entropy, not a placeholder."""
    if len(val) < 12:
        return False
    low = val.lower()
    if low in ("changeme", "password", "your_token_here", "xxxxxxxxxxxx") \
            or set(val) <= {"x", "X"} or low.startswith("${") \
            or low.startswith("<") or "example" in low or "placeholder" in low:
        return False
    return _shannon_entropy(val) >= 3.5


def scan_secrets(diff_text: str, filenames=None) -> list:
    """Return a list of human-readable findings; empty means clean.

    Scans ADDED lines of a unified diff (plus raw text if no +/- markers) and
    the set of changed filenames. Deny on any hit — a secret in history is
    expensive to walk back, so this is a hard block, not a warning."""
    findings = []
    for name in (filenames or []):
        base = Path(str(name)).name.lower()
        if base in _SECRET_FILENAMES or base.startswith(".env.") \
                or Path(base).suffix in _SECRET_SUFFIXES:
            findings.append(f"{name} (a secrets-bearing file by name)")

    for raw in diff_text.splitlines():
        # In a unified diff, only additions matter; treat unmarked text as added.
        if raw.startswith("-") and not raw.startswith("---"):
            continue
        line = raw[1:] if (raw.startswith("+") and not raw.startswith("+++")) else raw
        for rx, label in _SECRET_PATTERNS:
            if rx.search(line):
                findings.append(f"{label}: {line.strip()[:80]}")
                break
        else:
            m = _ASSIGN.search(line)
            if m and _looks_like_secret_value(m.group("val")):
                findings.append(f"a hardcoded credential: {line.strip()[:80]}")
    # De-dup while preserving order.
    seen, out = set(), []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# The deny-layer chokepoint. Every git write is evaluated here BEFORE any card.
# ---------------------------------------------------------------------------

def _branch_protected(branch: str, patterns) -> bool:
    b = (branch or "").strip()
    return any(fnmatch.fnmatch(b, pat) for pat in (patterns or []))


def _repo_on_allowlist(repo_path: Path, allowlist) -> bool:
    """The resolved repo must BE (or live under) an allowlisted root. Empty
    allowlist => nothing is writable, even with the master switch on (two
    independent locks — D6's defense in depth)."""
    try:
        rp = Path(repo_path).resolve()
    except OSError:
        return False
    for allowed in (allowlist or []):
        try:
            ar = Path(allowed).expanduser().resolve()
        except OSError:
            continue
        if rp == ar or rp.is_relative_to(ar):
            return True
    return False


def evaluate(op: GitOp, policy: GitWritePolicy) -> GitDecision:
    """The single chokepoint. Order is deliberate: cheapest/most-decisive
    denials first, secret scan last (it's the most work)."""
    if op.force:
        return GitDecision(False, "force-push is blocked outright — it can "
                                  "overwrite remote history that others may "
                                  "have. Never allowed, confirm or not.")
    if op.rewrite:
        return GitDecision(False, "rewriting pushed history (amend / rebase / "
                                  "reset --hard of a pushed ref) is blocked "
                                  "outright.")
    if not _repo_on_allowlist(op.repo_path, policy.writable_repos):
        return GitDecision(False,
                           f"'{op.repo_path}' is not on your writable-repos "
                           f"allowlist (repo.writable_repos, locked). I can "
                           f"review any repo, but I only commit/push to ones "
                           f"you've listed.")
    if _branch_protected(op.branch, policy.protected_branches):
        return GitDecision(False,
                           f"'{op.branch}' is a protected branch "
                           f"(repo.protected_branches, locked). Commit to a "
                           f"feature branch and open a PR instead.")
    leaks = scan_secrets(op.diff_text, op.changed_files)
    if leaks:
        return GitDecision(False,
                           "the diff appears to contain secrets, so I'm not "
                           "committing it:\n  - " + "\n  - ".join(leaks[:8])
                           + "\nRemove them (and rotate anything real) first.")
    return GitDecision(True)


# ---------------------------------------------------------------------------
# Git plumbing — small wrappers so the tool reads like intent, not subprocess.
# ---------------------------------------------------------------------------

def _git(repo: Path, *args, timeout: int = 120):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, timeout=timeout)


def _current_branch(repo: Path) -> str:
    r = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return r.stdout.strip()


def _upstream(repo: Path, branch: str):
    """The remote-tracking branch for `branch`, or None if it's local-only."""
    r = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name",
             f"{branch}@{{u}}")
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _remote_url(repo: Path, remote: str = "origin") -> str:
    r = _git(repo, "remote", "get-url", remote)
    return r.stdout.strip() if r.returncode == 0 else "(no remote)"


def _porcelain_changes(repo: Path, files=None):
    """(changed_file_list, has_changes). Honours an explicit file subset."""
    r = _git(repo, "status", "--porcelain", "--untracked-files=all")
    changed = []
    for line in r.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if "->" in path:              # rename: "old -> new"
            path = path.split("->", 1)[1].strip()
        changed.append(path)
    if files:
        wanted = set(files)
        changed = [c for c in changed if c in wanted]
    return changed, bool(changed)


def _assemble_diff(repo: Path, changed_files) -> str:
    """A scannable text of what would be committed: tracked changes as a
    unified diff, plus the CONTENT of new/untracked files (a fresh file full
    of secrets shows nothing in `git diff HEAD`, so inline it). Capped so a
    huge blob can't blow the scan up."""
    parts = []
    d = _git(repo, "diff", "HEAD")
    if d.stdout:
        parts.append(d.stdout)
    # Untracked files: not in the diff above.
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard")
    for rel in untracked.stdout.splitlines():
        if changed_files and rel not in changed_files:
            continue
        fp = (repo / rel)
        try:
            if fp.is_file() and fp.stat().st_size <= 1_000_000:
                text = fp.read_text(encoding="utf-8", errors="replace")
                parts.append(f"+++ b/{rel}\n" +
                             "\n".join("+" + l for l in text.splitlines()))
        except OSError:
            continue
    return "\n".join(parts)[:500_000]


def _diffstat(repo: Path) -> str:
    r = _git(repo, "diff", "HEAD", "--stat")
    out = r.stdout.strip()
    return out or "(no tracked changes; new files only)"


# ---------------------------------------------------------------------------
# The tool.
# ---------------------------------------------------------------------------

def register_git_write_tools(registry, gate, policy: GitWritePolicy,
                             workspaces: Path):
    """Register git_commit_push. Called from bootstrap ONLY when
    repo.allow_git_write is true (the LOCKED master switch)."""
    workspaces = Path(workspaces).resolve()

    def _resolve_repo(name_or_path: str) -> Path:
        """A git repo by allowlisted absolute path or by workspace name.
        Resolution never decides authorization — evaluate() does — but it lets
        Jack list a repo by a friendly workspace name."""
        raw = str(name_or_path).strip()
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = workspaces / raw
        return p.resolve()

    def git_commit_push(repo: str, message: str, branch: str = "",
                        files: str = "", push: bool = True) -> str:
        repo_path = _resolve_repo(repo)
        if not (repo_path / ".git").exists():
            return (f"ERROR: '{repo}' -> {repo_path} is not a git repo. Point "
                    f"me at a repo on your writable-repos allowlist.")
        if not (message or "").strip():
            return "ERROR: a commit needs a message describing the change."

        target = (branch or "").strip() or _current_branch(repo_path)
        file_list = [f for f in re.split(r"[,\s]+", files.strip()) if f] \
            if files.strip() else None

        changed, has_changes = _porcelain_changes(repo_path, file_list)
        if not has_changes:
            return ("Nothing to commit — the working tree is clean"
                    + (f" for {file_list}." if file_list else "."))

        diff_text = _assemble_diff(repo_path, changed)

        # ---- HARD-BLOCK LAYER: deny BEFORE any confirm card is shown. ----
        op = GitOp(repo_path=repo_path, branch=target, force=False,
                   rewrite=False, diff_text=diff_text, changed_files=changed)
        decision = evaluate(op, policy)
        if not decision.allowed:
            gate.log.log("GIT-BLOCKED", f"{repo_path} [{target}]: "
                                        f"{decision.reason[:120]}")
            return f"Blocked (no confirm shown): {decision.reason}"

        # ---- OUTBOUND confirm card (invariant #3 — every push asks). ----
        upstream = _upstream(repo_path, target)
        shared = upstream is not None
        card = [
            "GIT COMMIT" + (" + PUSH" if push else ""),
            f"Repo:    {repo_path.name}  ({_remote_url(repo_path)})",
            f"Branch:  {target}"
            + ("   << SHARED/REMOTE branch — others may pull this"
               if shared else "   (local-only branch)"),
            f"Files:   {len(changed)} changed",
            *[f"   {c}" for c in changed[:20]],
            *(["   ..."] if len(changed) > 20 else []),
            "Diffstat:",
            *[f"   {l}" for l in _diffstat(repo_path).splitlines()[:20]],
            f"Message: {message.strip()[:200]}",
        ]
        if push and not shared:
            card.append("Note: this branch has no upstream yet; the push will "
                        "create it on the remote.")
        try:
            gate.approve_outbound("\n".join(card))
        except Exception as e:               # ConfirmationDeclined et al.
            return f"Left it — you declined the commit/push ({type(e).__name__})."

        # ---- Execute: add -> commit -> (optional) plain, non-force push. ----
        if file_list:
            add = _git(repo_path, "add", "--", *file_list)
        else:
            add = _git(repo_path, "add", "-A")
        if add.returncode != 0:
            return f"ERROR staging: {add.stderr.strip()[:300]}"
        commit = _git(repo_path, "commit", "-m", message.strip())
        if commit.returncode != 0:
            return f"ERROR committing: {commit.stderr.strip()[:300]}"
        head = _git(repo_path, "rev-parse", "--short", "HEAD").stdout.strip()

        if not push:
            return (f"Committed {head} to {target} ({len(changed)} file(s)). "
                    f"Not pushed (push=false) — it's local until you say so.")

        # Plain push. NO --force, ever. New branches get -u to set upstream.
        push_args = ["push"] if shared else ["push", "-u", "origin", target]
        pr = _git(repo_path, *push_args, timeout=300)
        if pr.returncode != 0:
            return (f"Committed {head} to {target}, but the PUSH failed: "
                    f"{pr.stderr.strip()[:300]}. The commit is safe locally; "
                    f"fix the remote issue and I can push again.")
        return (f"Committed {head} and pushed to {target} "
                f"({len(changed)} file(s)).")

    registry.register(
        "git_commit_push",
        "Commit staged changes in one of Jack's WRITABLE repos and push them — "
        "OUTBOUND, so Jack gets a confirm card first, every time. You may only "
        "use repos he's put on the writable-repos allowlist, never a protected "
        "branch (main/master/release/*), and never force-push. If a diff looks "
        "like it contains secrets it's blocked before Jack is even asked. For "
        "review-only work use repo_sync/repo_map/read_file instead.",
        {"type": "object", "properties": {
            "repo": {"type": "string",
                     "description": "Workspace name or allowlisted repo path"},
            "message": {"type": "string",
                        "description": "Commit message (what changed and why)"},
            "branch": {"type": "string",
                       "description": "Target branch; empty = current branch"},
            "files": {"type": "string",
                      "description": "Optional space/comma list to stage; "
                                     "empty = all changes"},
            "push": {"type": "boolean",
                     "description": "Push after commit (default true)"}},
         "required": ["repo", "message"]},
        git_commit_push,
        kind="action_confirmed",   # approve_outbound already asks every time
    )

r"""
Autonomous GPU research loop (autoresearch port) — confirmation-gated, isolated.

This is a genuinely NEW risk class for FRIDAY. Every prior tool either only
*reads* untrusted content (repo_tools.py) or only *commits/pushes* code someone
else wrote (git_write.py). Nothing before this *executes* cloned, self-modified
code on Jack's machine, unattended, for hours. The whole design treats that
difference as first-class:

  * Two independent LOCKED locks before anything runs (research.enabled AND a
    non-empty research.allowed_repos) — ships disabled, Jack flips both himself.
  * Full isolation: THIS run's own clone under data\research\<tag>\repo\, with
    its own uv-managed .venv (torch/rustbpe/kernels) — never FRIDAY's own venv.
  * A pure-function DENY-LAYER (evaluate_launch) that runs BEFORE any confirm
    card, exactly like git_write.evaluate — unit-tested with zero I/O.
  * HARD, code-enforced ceilings (budget hours / iteration cap / per-attempt
    timeout / consecutive-crash cap) — never a model-judged stop. Upstream's
    program.md literally says "NEVER STOP, do NOT pause to ask the human"; per
    invariant #2 that text is DATA, not an instruction FRIDAY inherits. She
    adopts the iterate/score/keep-discard *method*; every stopping boundary is
    Jack's code ceiling, the same posture deep_mode.max_calls_per_session uses.
  * The in-the-loop edit model call is TOOL-LESS by construction (a bare
    OllamaClient with no tools= argument) — so nothing in program.md / train.py
    / the repo README can reach any of FRIDAY's real tools, however it's worded.
  * A code-level "I'm busy" gate in Engine.respond() (wired in bootstrap) so a
    live training run can't be silently starved of the 12GB GPU by a concurrent
    chat reply — or vice versa.

The model-visible RESULT of every tool here is kept to a status line (never raw
run.log / full results.tsv), because each ledger row's one-line description is
model text conditioned on untrusted repo content — it traces outside the trust
boundary even though nothing raw is dumped (same posture as repo_map).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from core.model import ModelError, OllamaClient


# ===========================================================================
# Policy / Op / Decision — declarative dataclasses (mirroring git_write's
# GitWritePolicy / GitOp / GitDecision) so the deny-layer is a single pure,
# testable chokepoint, independent of how the tool assembles the request.
# ===========================================================================

@dataclass
class ResearchPolicy:
    """The LOCKED posture, read from config at registration time. Every field
    is a `locked` config key (or a Jack-set ceiling) so FRIDAY can never widen
    her own reach or spend past Jack's budget."""
    allowed_repos: list = field(default_factory=list)   # repo URLs / local paths
    max_budget_hours: float = 8.0
    max_iters_per_run: int = 200
    train_window_minutes: int = 5     # upstream's per-attempt window (disclosed)
    iter_timeout_minutes: int = 10    # HARD kill if one attempt overruns
    max_crash_retries: int = 3        # consecutive crashes before the run gives up


@dataclass
class ResearchOp:
    """A proposed launch, described declaratively. The BOOLEAN environment facts
    (git/uv/GPU present, tag already used, another run active) are probed by the
    TOOL and passed in here — so evaluate_launch stays a pure function with zero
    I/O and can be unit-tested by simply constructing an op. This is the one
    refinement over git_write's GitOp: git_write's checks were all derivable
    from the op alone; ours depend on live machine/manager state, so the state
    is captured into the op at the call site, not read inside the guard."""
    repo: str
    tag: str
    requested_budget_hours: float = 0.0   # 0 => use the policy ceiling
    requested_max_iters: int = 0          # 0 => use the policy ceiling
    git_ok: bool = True
    uv_ok: bool = True
    gpu_ok: bool = True
    tag_in_use: bool = False
    other_run_active: bool = False


@dataclass
class ResearchDecision:
    """Result of the deny-layer. allowed=False means DENY BEFORE the confirm
    card — Jack is never asked, exactly like git_write's deny-zone. On allow,
    budget_hours / max_iters carry the values CLAMPED to Jack's ceilings."""
    allowed: bool
    reason: str = ""
    budget_hours: float = 0.0
    max_iters: int = 0


# ---------------------------------------------------------------------------
# Repo allowlist — URL-normalised, NOT path-containment. A research repo is a
# clone SOURCE (a URL like github.com/karpathy/autoresearch), not a directory
# on disk, so git_write's filesystem-containment logic is the wrong model here.
# We compare normalised identities: scheme, a leading git@host: form, a trailing
# .git, trailing slashes, and case are all stripped so the listed value and the
# thing FRIDAY was asked to clone match on identity, not on incidental spelling.
# ---------------------------------------------------------------------------

def _normalize_repo(url: str) -> str:
    s = (url or "").strip()
    if not s:
        return ""
    # git@github.com:user/repo(.git) -> github.com/user/repo
    m = re.match(r"^[\w.+-]+@([^:]+):(.+)$", s)
    if m:
        s = f"{m.group(1)}/{m.group(2)}"
    else:
        s = re.sub(r"^[a-zA-Z][\w+.-]*://", "", s)   # strip scheme://
    s = s.rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    return s.casefold()


def _repo_on_allowlist(repo: str, allowlist) -> bool:
    """Empty allowlist => nothing is runnable, even with the master switch on
    (two independent locks — the same defense-in-depth git_write uses). A local
    path repo is also compared by its resolved form so `..\autoresearch` and the
    absolute path match the same allowlist entry."""
    target = _normalize_repo(repo)
    if not target:
        return False
    variants = {target}
    # A local-path repo: also admit its resolved absolute form.
    try:
        p = Path(repo).expanduser()
        if p.exists():
            variants.add(_normalize_repo(str(p.resolve())))
    except OSError:
        pass
    for allowed in (allowlist or []):
        na = _normalize_repo(str(allowed))
        if na and na in variants:
            return True
        try:
            ap = Path(str(allowed)).expanduser()
            if ap.exists() and _normalize_repo(str(ap.resolve())) in variants:
                return True
        except OSError:
            continue
    return False


# ---------------------------------------------------------------------------
# The deny-layer chokepoint. Pure: no filesystem, no network, no manager state.
# Order is deliberate — cheapest/most-decisive denials first.
# ---------------------------------------------------------------------------

def evaluate_launch(op: ResearchOp, policy: ResearchPolicy) -> ResearchDecision:
    if not op.git_ok:
        return ResearchDecision(False, "git isn't on PATH — an autoresearch run "
                                       "clones and commits, so it needs git.")
    if not op.uv_ok:
        return ResearchDecision(False, "uv isn't on PATH — the run installs the "
                                       "repo's own torch/kernels into an isolated "
                                       "venv via `uv sync`, so it needs uv "
                                       "(astral.sh/uv).")
    if not op.gpu_ok:
        return ResearchDecision(False, "no NVIDIA GPU detected (nvidia-smi "
                                       "missing/failing) — this trains a model, "
                                       "so it needs the card.")
    if not _repo_on_allowlist(op.repo, policy.allowed_repos):
        return ResearchDecision(False,
                                f"'{op.repo}' is not on your research allowlist "
                                f"(research.allowed_repos, locked). I only run "
                                f"experiments in repos you've explicitly listed.")
    if op.other_run_active:
        return ResearchDecision(False, "another research run is already active. "
                                       "There's one GPU, so only one run at a "
                                       "time — stop it first (autoresearch_stop) "
                                       "or wait for it to finish.")
    if not (op.tag or "").strip():
        return ResearchDecision(False, "a run needs a short tag to name its "
                                       "workspace under data\\research\\.")
    if op.tag_in_use:
        return ResearchDecision(False,
                                f"the tag '{op.tag}' already has a run under "
                                f"data\\research\\ — pick a new tag rather than "
                                f"merging into an existing history.")

    # Allowed: clamp the request DOWN to Jack's ceilings (never up). A request
    # of 0 means "use the ceiling"; anything larger is capped, silently and
    # safely — she spends within the budget, never past it.
    req_h = op.requested_budget_hours or policy.max_budget_hours
    req_i = op.requested_max_iters or policy.max_iters_per_run
    return ResearchDecision(
        True,
        budget_hours=min(float(req_h), float(policy.max_budget_hours)),
        max_iters=min(int(req_i), int(policy.max_iters_per_run)),
    )


# ===========================================================================
# Deterministic log parsing — the keep/discard decision is scored on THIS, not
# on any model judgement (upstream greps val_bpb out of the log; so do we). Pure
# and unit-tested against canned success / crash / OOM fixtures.
# ===========================================================================

_VAL_BPB_RE = re.compile(r"^val_bpb:\s*([0-9]*\.?[0-9]+)", re.MULTILINE)
_VRAM_RE = re.compile(r"^peak_vram_mb:\s*([0-9]*\.?[0-9]+)", re.MULTILINE)


def parse_metrics(log_text: str) -> dict:
    """Return {'ok': True, 'val_bpb': float, 'peak_vram_mb': float|None} on a
    clean attempt, or {'ok': False} for ANY crash shape. An empty/missing
    val_bpb line covers OOM and every other crash uniformly — no special-casing
    per failure mode (the loop just treats "no score" as "crashed")."""
    m = _VAL_BPB_RE.search(log_text or "")
    if not m:
        return {"ok": False}
    try:
        val = float(m.group(1))
    except ValueError:
        return {"ok": False}
    vram = None
    mv = _VRAM_RE.search(log_text or "")
    if mv:
        try:
            vram = float(mv.group(1))
        except ValueError:
            vram = None
    return {"ok": True, "val_bpb": val, "peak_vram_mb": vram}


def format_results_row(commit: str, val_bpb, peak_vram_mb, status: str,
                       description: str) -> str:
    """One TSV row for the run's durable ledger (results.tsv), matching
    upstream's columns: commit, val_bpb, memory_gb, status, description. Tabs
    and newlines are stripped from the free-text description so a planted
    newline can't forge extra ledger rows."""
    def cell(x):
        return re.sub(r"[\t\r\n]+", " ", str(x)).strip()
    vb = "" if val_bpb is None else f"{float(val_bpb):.4f}"
    gb = "" if peak_vram_mb is None else f"{float(peak_vram_mb) / 1024:.2f}"
    return "\t".join((cell(commit), vb, gb, cell(status),
                      cell(description)[:200]))


# ===========================================================================
# Environment probes + subprocess plumbing. Kept out of the deny-layer so the
# guard stays pure — the tool calls these and passes the booleans into the op.
# ===========================================================================

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _have_gpu() -> bool:
    """An NVIDIA GPU is present iff nvidia-smi exists and exits cleanly. Cheap,
    deterministic, and works even when Ollama has the card busy."""
    if not _have("nvidia-smi"):
        return False
    try:
        r = subprocess.run(["nvidia-smi"], capture_output=True,
                           text=True, timeout=15)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _git(repo: Path, *args, timeout: int = 300):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, timeout=timeout)


def _terminate_tree(proc):
    """Kill a subprocess AND its children. `uv run train.py` spawns a child
    python that actually holds the GPU; on Windows a plain proc.terminate() of
    the `uv` parent orphans that child (the training keeps running, the card
    stays claimed). taskkill /F /T kills the whole tree so 'stop' and the
    per-attempt timeout genuinely free VRAM — the difference between a fast stop
    and a zombie run. (This is the single biggest real-world gap in a naive
    port; see the plan's stop-semantics decision.)"""
    if proc is None or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        else:
            proc.terminate()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass


_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_+-]*\s*\n(.*?)\n\s*```\s*$",
                       re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """The edit model is told to reply with the whole file and nothing else, but
    small models wrap it in ```python fences anyway. Strip a single enclosing
    fence if present; otherwise return as-is."""
    m = _FENCE_RE.match(text or "")
    return m.group(1) if m else (text or "")


# ===========================================================================
# ResearchManager — owns the live runs and the background loop.
# ===========================================================================

class ResearchManager:
    """One per FRIDAY instance (created only when research.enabled). Owns the
    tag -> run-state map, exposes active_tag / eta_str() / stop() for the
    engine's busy-gate, and fires on_event on state transitions + new-bests."""

    def __init__(self, registry, gate, policy: ResearchPolicy, base_dir: Path,
                 host: str, edit_model: str, edit_model_num_ctx: int):
        self.registry = registry
        self.gate = gate
        self.policy = policy
        self.base_dir = Path(base_dir)
        self.host = host
        self.edit_model = edit_model
        self.edit_model_num_ctx = int(edit_model_num_ctx)
        # tag -> {stop_event, proc, thread, state, eta, started, ...}
        self._runs = {}
        self._lock = threading.Lock()
        # No-op default; service overwrites this to pipe pings to the UI.
        self.on_event = lambda tag, text: None

    # ---------- state the engine busy-gate reads ----------

    @property
    def active_tag(self):
        """The tag of the one in-flight run (setting_up or running), or None.
        Only one run exists at a time by construction (the deny-layer blocks a
        second)."""
        with self._lock:
            for tag, r in self._runs.items():
                if r.get("state") in ("setting_up", "running"):
                    return tag
        return None

    def eta_str(self) -> str:
        """A friendly local ETA for the active run ('around 3:40am'), best
        effort — used only for the deterministic 'I'm busy' deflection. Built
        without platform-specific strftime codes (%-I is not portable to
        Windows), so it reads the same on every OS."""
        with self._lock:
            for r in self._runs.values():
                if r.get("state") in ("setting_up", "running") and r.get("eta"):
                    dt = r["eta"]
                    hour = dt.hour % 12 or 12
                    return f"around {hour}:{dt.minute:02d}{dt.strftime('%p').lower()}"
        return "soon"

    def eta(self):
        """The active run's ETA as a datetime, or None (kept as the plan named
        it; eta_str is what the busy-gate actually prints)."""
        with self._lock:
            for r in self._runs.values():
                if r.get("state") in ("setting_up", "running"):
                    return r.get("eta")
        return None

    # ---------- paths ----------

    def _run_dir(self, tag: str) -> Path:
        return self.base_dir / _slug(tag)

    def _status_path(self, tag: str) -> Path:
        return self._run_dir(tag) / "status.json"

    def _write_status(self, tag: str, status: dict):
        """Atomic status write (tmp + os.replace) — autoresearch_status only
        ever reads this file, so a half-written JSON must never be observable."""
        p = self._status_path(tag)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(status, indent=1, default=str),
                       encoding="utf-8")
        os.replace(tmp, p)

    def _read_status(self, tag: str) -> dict:
        try:
            return json.loads(self._status_path(tag).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    # ---------- stop ----------

    def stop(self, tag: str) -> str:
        """Immediate stop: signal the loop, kill the in-flight training subtree
        NOW (loses up to one ~5-min attempt), finalize status. Reachable both
        as the autoresearch_stop tool and directly from the engine busy-gate."""
        with self._lock:
            run = self._runs.get(tag)
        if not run:
            return f"No active research run tagged '{tag}'."
        run["stop_event"].set()
        _terminate_tree(run.get("proc"))
        status = self._read_status(tag)
        status.update(state="stopped",
                      updated=datetime.now().isoformat(timespec="seconds"),
                      message="Stopped by Jack.")
        self._write_status(tag, status)
        self.on_event(tag, "stopped by you")
        return (f"Stopped research '{tag}'. Its best result so far is kept in "
                f"data\\research\\{_slug(tag)}\\; nothing was pushed anywhere.")

    # ---------- launch (returns immediately; work happens on a thread) ----------

    def _spawn(self, tag: str, repo: str, objective: str,
               budget_hours: float, max_iters: int):
        stop_event = threading.Event()
        eta = datetime.now() + timedelta(hours=budget_hours)
        run = {"stop_event": stop_event, "proc": None, "thread": None,
               "state": "setting_up", "eta": eta,
               "started": datetime.now()}
        with self._lock:
            self._runs[tag] = run
        # Seed a status file NOW so autoresearch_status has something to read
        # during the (possibly minutes-long) clone + uv sync.
        self._write_status(tag, {
            "tag": tag, "repo": repo, "objective": objective,
            "state": "setting_up", "iteration": 0, "max_iters": max_iters,
            "budget_hours": budget_hours,
            "started": run["started"].isoformat(timespec="seconds"),
            "updated": datetime.now().isoformat(timespec="seconds"),
            "eta": eta.isoformat(timespec="seconds"),
            "best_val_bpb": None, "best_commit": None, "crash_streak": 0,
            "message": "Setting up: cloning + installing the isolated venv.",
        })
        t = threading.Thread(
            target=self._run_loop,
            args=(tag, repo, objective, budget_hours, max_iters, stop_event),
            daemon=True)
        run["thread"] = t
        t.start()

    # ---------- the background loop ----------

    def _run_loop(self, tag, repo, objective, budget_hours, max_iters,
                  stop_event):
        """Upstream's protocol translated into code, with every GPU-timing and
        keep/discard decision deterministic — never model-judged. Wrapped so any
        exception finalizes status as crashed rather than dying silently."""
        run_dir = self._run_dir(tag)
        repo_dir = run_dir / "repo"
        log_path = run_dir / "run.log"
        tsv_path = repo_dir / "results.tsv"
        deadline = datetime.now() + timedelta(hours=budget_hours)
        best_val = None
        best_commit = None
        crash_streak = 0
        iteration = 0
        state = "running"

        def finalize(final_state, message):
            status = self._read_status(tag)
            status.update(state=final_state, message=message,
                          iteration=iteration, best_val_bpb=best_val,
                          best_commit=best_commit, crash_streak=crash_streak,
                          updated=datetime.now().isoformat(timespec="seconds"))
            self._write_status(tag, status)
            with self._lock:
                r = self._runs.get(tag)
                if r:
                    r["state"] = final_state

        try:
            # ---- setup: clone + isolate the venv ----
            self._setup_clone(repo, repo_dir, objective)
            edit = OllamaClient(self.host, self.edit_model,
                               num_ctx=self.edit_model_num_ctx)
            self.on_event(tag, "set up; starting experiments")

            while True:
                # 1. HARD-STOP checks first — cheapest, most decisive.
                if stop_event.is_set():
                    finalize("stopped", "Stopped by Jack."); return
                if datetime.now() >= deadline:
                    finalize("done", f"Budget of {budget_hours:.1f}h reached "
                                     f"after {iteration} attempts."); return
                if iteration >= max_iters:
                    finalize("done", f"Iteration cap ({max_iters}) reached."); return

                iteration += 1

                # 2. Clean tree (self-heal a train.py left dirty by a crash).
                _git(repo_dir, "checkout", "--", "train.py")

                # 3. Propose an edit — TOOL-LESS model call (no tools= at all),
                #    so nothing in the untrusted repo content has a tool surface.
                try:
                    new_src = self._propose_edit(edit, repo_dir, objective)
                except ModelError:
                    finalize("crashed", "The edit model became unreachable "
                                        "(is Ollama still running?)."); return

                # 4. Deterministic syntax gate — an unparseable edit is a crash
                #    that never costs a training window.
                new_src = _strip_code_fences(new_src)
                syntax_ok = True
                try:
                    compile(new_src, "train.py", "exec")
                except SyntaxError:
                    syntax_ok = False

                if not syntax_ok or not new_src.strip():
                    crash_streak += 1
                    self._append_tsv(tsv_path, format_results_row(
                        "(unparsed)", None, None, "crash",
                        "edit did not parse as Python"))
                    if crash_streak > self.policy.max_crash_retries:
                        finalize("crashed", f"{crash_streak} edits in a row "
                                            f"failed to parse."); return
                    continue

                # 5. Overwrite (tree was clean; git is the backup), stage ONLY
                #    train.py (never -A — structurally the only file that can
                #    ever enter this history), commit.
                (repo_dir / "train.py").write_text(new_src, encoding="utf-8")
                _git(repo_dir, "add", "--", "train.py")
                _git(repo_dir, "commit", "-m",
                     f"autoresearch attempt {iteration}")
                commit = _git(repo_dir, "rev-parse", "--short",
                             "HEAD").stdout.strip() or "(unknown)"

                # 6. Train via Popen (killable), hard deadline = iter timeout.
                crashed_timeout = self._train_once(repo_dir, log_path, tag,
                                                   stop_event)
                if stop_event.is_set():
                    finalize("stopped", "Stopped by Jack."); return

                # 7. Deterministic score parse.
                log_text = ""
                try:
                    log_text = log_path.read_text(encoding="utf-8",
                                                  errors="replace")
                except OSError:
                    pass
                metrics = parse_metrics(log_text)

                # 8. Crash handling — bounded, not open-ended.
                if crashed_timeout or not metrics["ok"]:
                    crash_streak += 1
                    self._append_tsv(tsv_path, format_results_row(
                        commit, None, None, "crash",
                        "timed out" if crashed_timeout else "no val_bpb (crash/OOM)"))
                    _git(repo_dir, "reset", "--hard", "HEAD~1")
                    self._update_progress(tag, iteration, best_val, best_commit,
                                          crash_streak, "crashed an attempt")
                    if crash_streak > self.policy.max_crash_retries:
                        finalize("crashed", f"{crash_streak} attempts in a row "
                                            f"crashed — stopping rather than "
                                            f"burning the budget on a broken "
                                            f"edit."); return
                    continue

                crash_streak = 0  # any success resets the streak
                val = metrics["val_bpb"]

                # 9. Keep / discard — scored on the metric, never a vibe call.
                if best_val is None or val < best_val:
                    best_val = val
                    best_commit = commit
                    self._append_tsv(tsv_path, format_results_row(
                        commit, val, metrics.get("peak_vram_mb"), "keep",
                        f"new best val_bpb {val:.4f} (attempt {iteration})"))
                    # The ONE per-iteration event worth a ping (not all 100+).
                    self.on_event(tag, f"new best val_bpb {val:.4f} "
                                       f"(attempt {iteration})")
                else:
                    self._append_tsv(tsv_path, format_results_row(
                        commit, val, metrics.get("peak_vram_mb"), "discard",
                        f"val_bpb {val:.4f} did not beat {best_val:.4f}"))
                    _git(repo_dir, "reset", "--hard", "HEAD~1")

                # 10. Rewrite status (atomic).
                self._update_progress(tag, iteration, best_val, best_commit,
                                      crash_streak,
                                      f"best val_bpb {best_val:.4f}"
                                      if best_val is not None else "running")
                # 11. Loop.
        except Exception as e:  # the loop must never die silently
            finalize("crashed", f"Run aborted by an internal error: "
                                f"{type(e).__name__}: {str(e)[:200]}")

    # ---------- loop helpers ----------

    def _setup_clone(self, repo: str, repo_dir: Path, objective: str):
        """Clone THIS run's private copy and give it a local git identity, then
        `uv sync` the isolated venv. A LOCAL identity is set on the clone
        because Jack's global git identity may be unset (it was, at build time)
        — without it every autoresearch commit would fail and the whole
        keep/discard mechanism (which is git commits) would break. The venv is
        the repo's own uv-managed .venv — torch/cu128 land THERE, never in
        FRIDAY's interpreter."""
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
        clone = subprocess.run(["git", "clone", "--depth", "1", str(repo),
                                str(repo_dir)],
                               capture_output=True, text=True, timeout=600)
        if clone.returncode != 0:
            raise RuntimeError(f"git clone failed: {clone.stderr.strip()[:300]}")
        _git(repo_dir, "config", "user.email", "friday@localhost")
        _git(repo_dir, "config", "user.name", "FRIDAY autoresearch")
        # `uv sync` builds the isolated .venv from the repo's own pyproject.toml.
        # First run pulls torch/cu128 — minutes — hence this whole thing runs on
        # the background thread, never synchronously in the tool call.
        sync = subprocess.run(["uv", "sync"], cwd=str(repo_dir),
                              capture_output=True, text=True, timeout=3600)
        if sync.returncode != 0:
            raise RuntimeError(f"uv sync failed: {sync.stderr.strip()[:300]}")

    def _propose_edit(self, edit: OllamaClient, repo_dir: Path,
                      objective: str) -> str:
        """The heart of the method: ask the edit model for the WHOLE new
        train.py. This call has NO tools= argument — completely decoupled from
        the registry — so however program.md / train.py / the README is worded,
        there is no tool-calling surface for planted content to exploit. The
        objective is advisory only; it never overrides the metric or a ceiling
        (that's all enforced in code above, not here)."""
        program = _read_head(repo_dir / "program.md", 8000)
        train = _read_head(repo_dir / "train.py", 16000)
        ledger = _tail_lines(repo_dir / "results.tsv", 10)
        system = (
            "You are tuning a single file, train.py, to lower its val_bpb "
            "metric. Reply with the COMPLETE new train.py and NOTHING else — "
            "no prose, no explanation, no markdown fences. Make ONE coherent "
            "improvement per attempt; a small win that adds complexity loses "
            "to a bigger win that doesn't.")
        user = f"""program.md (the task):
{program}

Recent attempts (results.tsv — commit, val_bpb, memory_gb, status, note):
{ledger or '(none yet)'}

Current train.py:
{train}
"""
        if (objective or "").strip():
            user += (f"\nObjective hint from Jack (advisory — the val_bpb metric "
                     f"and the run's ceilings still govern): {objective.strip()}\n")
        reply = edit.chat([{"role": "system", "content": system},
                           {"role": "user", "content": user}])   # NO tools=
        return reply.content

    def _train_once(self, repo_dir: Path, log_path: Path, tag: str,
                    stop_event) -> bool:
        """Run `uv run train.py`, streaming stdout+stderr into run.log, polled
        against a HARD iter_timeout deadline. Returns True if it had to be
        killed (timeout OR stop). The kill is a whole-tree kill so the GPU is
        actually released. train_window_minutes is upstream's OWN internal
        window (train.py self-limits); iter_timeout_minutes is our code ceiling
        for a train.py that ignores it."""
        deadline = time.time() + self.policy.iter_timeout_minutes * 60
        with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
            proc = subprocess.Popen(["uv", "run", "train.py"], cwd=str(repo_dir),
                                    stdout=logf, stderr=subprocess.STDOUT)
            with self._lock:
                if tag in self._runs:
                    self._runs[tag]["proc"] = proc
            killed = False
            while proc.poll() is None:
                if stop_event.is_set() or time.time() > deadline:
                    _terminate_tree(proc)
                    killed = True
                    break
                time.sleep(2)
            with self._lock:
                if tag in self._runs:
                    self._runs[tag]["proc"] = None
        return killed

    def _append_tsv(self, tsv_path: Path, row: str):
        """Append one ledger row with flush + fsync — results.tsv is the durable
        record (run.log is overwritten every attempt), so a crash mid-run must
        not lose the history of what was tried."""
        tsv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tsv_path, "a", encoding="utf-8") as f:
            f.write(row + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _update_progress(self, tag, iteration, best_val, best_commit,
                         crash_streak, message):
        status = self._read_status(tag)
        status.update(state="running", iteration=iteration,
                      best_val_bpb=best_val, best_commit=best_commit,
                      crash_streak=crash_streak, message=message,
                      updated=datetime.now().isoformat(timespec="seconds"))
        self._write_status(tag, status)

    # ---------- the status view (for the tool) ----------

    def status_text(self, tag: str = "") -> str:
        if not tag:
            with self._lock:
                tags = list(self._runs.keys())
            # Also surface any on-disk runs from earlier sessions.
            if self.base_dir.exists():
                for d in self.base_dir.iterdir():
                    if (d / "status.json").exists() and d.name not in tags:
                        tags.append(d.name)
            if not tags:
                return "No research runs on record."
            lines = ["Research runs:"]
            for t in tags:
                s = self._read_status(t)
                lines.append(f"  {s.get('tag', t)}: {s.get('state', '?')} — "
                             f"attempt {s.get('iteration', 0)}"
                             f"/{s.get('max_iters', '?')}, "
                             f"best val_bpb {s.get('best_val_bpb')}")
            return "\n".join(lines)
        s = self._read_status(tag)
        if not s:
            return f"No research run tagged '{tag}'."
        return (f"Research '{s.get('tag', tag)}' [{s.get('state', '?')}]\n"
                f"  repo:      {s.get('repo', '?')}\n"
                f"  attempt:   {s.get('iteration', 0)} / {s.get('max_iters', '?')}\n"
                f"  best:      val_bpb {s.get('best_val_bpb')} "
                f"(commit {s.get('best_commit')})\n"
                f"  crashes:   {s.get('crash_streak', 0)} in a row\n"
                f"  eta:       {s.get('eta', '?')}\n"
                f"  note:      {s.get('message', '')}")


# ---------------------------------------------------------------------------
# small file helpers
# ---------------------------------------------------------------------------

def _slug(tag: str) -> str:
    """Filesystem-safe slug (same instinct as repo_tools' naming)."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", (tag or "").strip())
    return s.strip("._") or "run"


def _read_head(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _tail_lines(path: Path, n: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return ""


# ===========================================================================
# Registration — mirrors register_git_write_tools' shape. Called from bootstrap
# ONLY when research.enabled is true (the LOCKED master switch).
# ===========================================================================

def register_research_tools(registry, gate, policy: ResearchPolicy,
                            base_dir: Path, host: str, edit_model: str,
                            edit_model_num_ctx: int) -> ResearchManager:
    manager = ResearchManager(registry, gate, policy, base_dir, host,
                              edit_model, edit_model_num_ctx)

    def autoresearch_launch(repo: str, tag: str = "", objective: str = "",
                            budget_hours: float = 0, max_iters: int = 0) -> str:
        # ---- Probe the environment, build the op, run the PURE deny-layer. ----
        op = ResearchOp(
            repo=repo, tag=(tag or "").strip(),
            requested_budget_hours=float(budget_hours or 0),
            requested_max_iters=int(max_iters or 0),
            git_ok=_have("git"), uv_ok=_have("uv"), gpu_ok=_have_gpu(),
            tag_in_use=manager._status_path((tag or "").strip()).exists()
                if (tag or "").strip() else False,
            other_run_active=manager.active_tag is not None,
        )
        decision = evaluate_launch(op, policy)
        if not decision.allowed:
            gate.log.log("RESEARCH-BLOCKED",
                         f"{repo} [{tag}]: {decision.reason[:120]}")
            return f"Blocked (no confirm shown): {decision.reason}"

        # ---- OUTBOUND confirm card — ONE approval covers the whole run. ----
        resident = _ollama_resident(host)
        card = [
            "AUTONOMOUS RESEARCH RUN — one approval covers the whole run",
            f"Repo:      {repo}",
            f"Tag:       {op.tag}   (workspace: data\\research\\{_slug(op.tag)}\\)",
            f"Budget:    up to {decision.budget_hours:.1f} h OR "
            f"{decision.max_iters} attempts, whichever first",
            f"Per try:   ~{policy.train_window_minutes} min train, hard-killed "
            f"at {policy.iter_timeout_minutes} min",
            "GPU:       this CLAIMS your NVIDIA GPU for the whole run; I'll be "
            "off normal chat until it ends (say 'stop research' to reclaim me).",
        ]
        if resident:
            card.append(f"Heads-up:  Ollama currently has '{resident}' resident "
                        f"— it may contend for VRAM with the training.")
        card += [
            "Edits:     proposed by a SEPARATE, tool-less local model call — "
            "nothing in the repo can reach my tools.",
            "Scope:     LOCAL ONLY — clones + trains on this machine, pushes "
            "NOTHING anywhere.",
            f"Objective: {objective.strip() or '(none — just minimise val_bpb)'}",
        ]
        try:
            gate.approve_outbound("\n".join(card))
        except Exception as e:   # ConfirmationDeclined et al.
            return f"Left it — you declined the research run ({type(e).__name__})."

        manager._spawn(op.tag, repo, objective, decision.budget_hours,
                       decision.max_iters)
        return (f"Started research '{op.tag}' on {repo} (up to "
                f"{decision.budget_hours:.1f}h / {decision.max_iters} attempts). "
                f"Setting up the isolated venv now (the first torch install can "
                f"take a few minutes). Ask me for status any time; I'll be off "
                f"normal chat until it's done.")

    def autoresearch_status(tag: str = "") -> str:
        return manager.status_text((tag or "").strip())

    def autoresearch_stop(tag: str) -> str:
        return manager.stop((tag or "").strip())

    registry.register(
        "autoresearch_launch",
        "Launch an AUTONOMOUS GPU research run: clone one of Jack's allowlisted "
        "research repos into an ISOLATED workspace and iteratively tune its "
        "train.py to minimise val_bpb — commit / train / score / keep-or-discard "
        "in a loop, unattended, within Jack's budget. OUTBOUND: Jack gets ONE "
        "confirm card up front (it claims the GPU for the whole run). You may "
        "only use repos on his research allowlist; blocked before he's asked "
        "otherwise. While a run is active you're OFF normal chat. Local only — "
        "nothing is pushed anywhere.",
        {"type": "object", "properties": {
            "repo": {"type": "string",
                     "description": "Allowlisted research repo URL or local path"},
            "tag": {"type": "string",
                    "description": "Short name for this run's workspace "
                                   "(must be unused)"},
            "objective": {"type": "string",
                          "description": "Optional advisory hint; the val_bpb "
                                         "metric and ceilings still govern"},
            "budget_hours": {"type": "number",
                             "description": "Hours to run (capped at Jack's "
                                            "ceiling; 0 = use the ceiling)"},
            "max_iters": {"type": "number",
                          "description": "Max attempts (capped at Jack's "
                                         "ceiling; 0 = use the ceiling)"}},
         "required": ["repo"]},
        autoresearch_launch,
        kind="action_confirmed",   # approve_outbound already asks once
    )

    registry.register(
        "autoresearch_status",
        "Report the status of a research run (state, current attempt, best "
        "val_bpb so far, ETA) from its status ledger. Omit the tag to list all "
        "runs. Read-only.",
        {"type": "object", "properties": {
            "tag": {"type": "string",
                    "description": "Run tag; empty = list all runs"}},
         "required": []},
        autoresearch_status,
        kind="external_read",   # the ledger's notes trace to untrusted repo text
    )

    registry.register(
        "autoresearch_stop",
        "Stop an active research run immediately — kills the in-flight training "
        "attempt now (losing up to one ~5-min attempt) and finalises its status. "
        "The best result so far is kept. Use this when Jack says to stop, or to "
        "reclaim the GPU.",
        {"type": "object", "properties": {
            "tag": {"type": "string", "description": "The run tag to stop"}},
         "required": ["tag"]},
        autoresearch_stop,
        kind="action",
    )

    return manager


def _ollama_resident(host: str):
    """Best-effort probe of the model Ollama currently has resident (/api/ps),
    so the confirm card can warn about VRAM contention. Never raises — a probe
    failure just means the card omits the heads-up."""
    try:
        import requests
        r = requests.get(f"{host.rstrip('/')}/api/ps", timeout=3)
        models = (r.json() or {}).get("models") or []
        return models[0].get("name") if models else None
    except Exception:
        return None

r"""
Bootstrap: wire the whole FRIDAY stack together from friday_config.yaml.

Both frontends (the CLI and the app shell) call build_engine() with their own
confirm callback — the only piece that differs between them is how Jack gets
asked "Allow? [y/N]".
"""

import json
import os
from pathlib import Path

import yaml

from core.commitments import CommitmentTracker
from core.engine import Engine
from core.logging_utils import ActionLogger, InteractionLogger
from core.memory.brain import Brain
from core.memory.keyword_retriever import KeywordRetriever
from core.model import OllamaClient
from core.permissions import PermissionGate
from core.playbooks import Playbooks
from core.skills import Skills
from core.senses import Senses
from core.tools.brain_tools import register_brain_tools
from core.tools.calc_tools import register_calc_tools
from core.tools.commitment_tools import register_commitment_tools
from core.tools.filesystem import register_filesystem_tools
from core.tools.playbook_tools import register_playbook_tools
from core.tools.self_tools import register_rule_tool, register_self_tools
from core.tools.skill_tools import register_skill_tools
from core.tools.projects import register_project_tools
from core.tools.reasoning_tools import register_deep_think
from core.timelines import TimelineTracker
from core.tools.registry import ToolRegistry
from core.tools.senses_tools import register_senses_tools
from core.tools.timeline_tools import register_timeline_tools

ROOT = Path(__file__).resolve().parent.parent


def _resolve(p: str) -> Path:
    """Config paths may be relative to the FRIDAY root or absolute."""
    path = Path(p)
    return path if path.is_absolute() else ROOT / path


def load_config(path=None) -> dict:
    """Load config from `path`, the FRIDAY_CONFIG env var, or the default.
    The override exists so the test suite can point a whole FRIDAY instance
    (including subprocesses) at a sandbox — never at the real brain."""
    p = Path(path or os.environ.get("FRIDAY_CONFIG")
             or ROOT / "config" / "friday_config.yaml")
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Remember where this config came from — change_own_config edits the
    # actual file, so the running instance must know its own source.
    cfg["_source_path"] = str(p)
    return cfg


def _session_type(config: dict) -> str:
    """Memory provenance (Task 1): 'real' (the zero-ceremony default) or
    'test' (live-instance capability testing — brain writes reroute to
    test_archive/, retrieval includes it). The env var wins so a test session
    can be started without editing config (the CLI's --test-session flag
    sets it); anything not explicitly 'test' is real."""
    env = os.environ.get("FRIDAY_TEST_SESSION", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return "test"
    cfg = str((config.get("session") or {}).get("type", "real")).lower()
    return "test" if cfg == "test" else "real"


def data_dir(config: dict) -> Path:
    """Where derived/private state lives (app_state, secrets, session labels).
    Configurable (paths.data) so sandboxed instances stay self-contained."""
    return _resolve(config.get("paths", {}).get("data", "data"))


def _migrate_operating_rules(brain, persona_text: str):
    """One-time move of the operating rules into HER domain (Tier A of the
    self-modification model): config\\persona.md content becomes
    brain\\character\\operating_rules.md — a normal brain note she can edit
    herself (free, logged, git-versioned). The Invariants section is stripped
    from the copy: the constitution now comes from core\\invariants.py in code
    and must not also live in a self-writable file (a stale editable copy
    could drift and contradict what the engine actually enforces)."""
    rel = "character/operating_rules.md"
    if (brain.root / rel).exists():
        return
    import re as _re
    rules = _re.sub(r"## Invariants[^\n]*\n(?:(?!## ).*\n?)*", "",
                    persona_text)
    rules = rules.replace(
        "# FRIDAY — Operating Rules",
        "# FRIDAY — Operating Rules\n\n"
        "*This note is YOURS: edit it to change how you work (git keeps every "
        "version; tell Jack when you change your own rules). Your four "
        "invariants are enforced in code and are not in this file — no edit "
        "here can change them.*", 1)
    brain.system_write(rel, rules,
                       summary="Migrate operating rules into the brain "
                               "(self-modification Tier A)")


def build_engine(confirm, config: dict = None) -> Engine:
    """
    confirm : callable(description: str) -> bool — how this frontend asks Jack
              to approve a gated action.
    config  : optional pre-loaded config dict (tests inject sandboxes here).
    """
    config = config or load_config()
    # Resolve the session's provenance ONCE and record it in the config dict
    # so every consumer (Brain routing, Engine prompt/logs) agrees.
    session_type = _session_type(config)
    config.setdefault("session", {})["type"] = session_type

    # Config governance (Task 2): refuse to start with any untiered key —
    # a new feature flag must declare its posture (self_serve/propose/locked)
    # in core/config_governance.py the day it ships. Also audit any manual
    # file edits since the last load (actor=jack), so the audit log is the
    # complete change history regardless of who changed what.
    from core.config_governance import detect_manual_edits, validate_tiers
    validate_tiers(config)
    if config.get("_source_path"):
        detect_manual_edits(Path(config["_source_path"]))

    brain_path = _resolve(config["paths"]["brain"])
    outbox_path = _resolve(config["paths"]["outbox"])
    logs_path = _resolve(config["paths"]["logs"])
    outbox_path.mkdir(parents=True, exist_ok=True)

    persona = _resolve(config["persona_file"]).read_text(encoding="utf-8")
    preferences = _resolve(config["preferences_file"]).read_text(encoding="utf-8")
    json.loads(preferences)  # fail loudly now if preferences.json is malformed

    # The default projects root is always a (confirm-first) writable zone;
    # the allowlist in config adds any extra areas on top of it.
    projects_root = Path(config["projects"]["default_root"])
    project_roots = [projects_root] + [
        Path(p) for p in config["permissions"]["writable_project_roots"]
    ]

    action_log = ActionLogger(logs_path)
    gate = PermissionGate(
        brain_root=brain_path,
        outbox_root=outbox_path,
        project_roots=project_roots,
        confirm=confirm,
        action_logger=action_log,
        large_file_mb=config["permissions"].get("large_file_mb", 50),
    )
    brain = Brain(brain_path, gate, autocommit=config["memory"]["git_autocommit"],
                  test_session=(session_type == "test"))
    _migrate_operating_rules(brain, persona)
    # Retriever selection (Phase 3 seam). min_score is the Phase-1 relevance
    # floor (Symptom 6) — a note must clear it to be served.
    #   keyword  — notes only (pre-Phase-3 default, kept as fallback)
    #   layered  — notes + the typed-observation stream, self-citing (Phase 3)
    #   vector   — RESERVED: a local embedding index behind the same seam. NOT
    #              wired — it needs a heavy on-device dependency (torch, via
    #              ChromaDB/sentence-transformers) that CLAUDE.md says to clear
    #              with Jack first. Refuse rather than pretend it exists.
    min_score = config["memory"].get("min_score",
                                     KeywordRetriever.DEFAULT_MIN_SCORE)
    rname = str(config["memory"].get("retriever", "keyword")).lower()
    if rname == "keyword":
        retriever = KeywordRetriever(brain_path, min_score=min_score)
    elif rname == "layered":
        from core.memory.observation_retriever import LayeredRetriever
        retriever = LayeredRetriever(brain, min_score=min_score)
    elif rname == "vector":
        raise SystemExit(
            "memory.retriever: 'vector' is a reserved Phase-3 seam — a local "
            "embedding index (ChromaDB / sentence-transformers) is not wired "
            "because it needs a heavy on-device dependency (torch) that "
            "CLAUDE.md requires clearing with Jack first. Use 'keyword' or "
            "'layered'. See FRIDAY_coherence_plan.md, Phase 4 handoff.")
    else:
        raise SystemExit(
            f"memory.retriever: unknown value '{rname}' — "
            f"use 'keyword', 'layered', or (reserved) 'vector'.")
    # The observation store the engine WRITES through (the retriever reads the
    # same files). One place the typed-observation stream is produced.
    from core.memory.observations import ObservationStore
    observations = ObservationStore(brain)
    # Derived FTS index over the observation stream (Notes-10 Phase 4 §3):
    # full-text recall across sessions, stdlib sqlite3+FTS5, git-ignored under
    # data\ and rebuildable from the brain. Wired onto the store so each new
    # observation is indexed incrementally; ensure() builds it once if absent.
    from core.memory.observation_index import ObservationIndex
    obs_index = ObservationIndex(observations, data_dir(config))
    observations.index = obs_index
    obs_index.ensure()

    registry = ToolRegistry()
    register_filesystem_tools(registry, gate, outbox_path,
                              config["tools"]["read_file_max_bytes"])
    register_brain_tools(registry, brain, retriever, config["memory"]["top_k"])
    # Progressive-disclosure reads over the typed-observation stream (Notes-10
    # Phase 4 §2): the session-start index lists ids cheaply, get_observations
    # pulls a full body on demand. Internal kind — reading her own record.
    from core.tools.observation_tools import register_observation_tools
    register_observation_tools(registry, observations, obs_index)
    register_calc_tools(registry)  # units-safe arithmetic (don't make the model do math)
    project_resolver = register_project_tools(registry, gate, brain, projects_root)

    tracker = CommitmentTracker(brain)
    register_commitment_tools(registry, tracker, gate)

    timelines = TimelineTracker(brain)
    register_timeline_tools(registry, timelines)

    playbooks = Playbooks(brain)
    register_playbook_tools(registry, playbooks)

    skills = Skills(brain)
    register_skill_tools(registry, skills)

    # Tier A rule surgery (always available — it's a brain write) and Tier B
    # config self-modification (validated + confirmed; only registers when we
    # know which file the running config came from — injected sandbox dicts
    # without a path just don't get the config tools).
    register_rule_tool(registry, brain)
    if config.get("_source_path"):
        register_self_tools(registry, gate, config,
                            Path(config["_source_path"]))

    # Repo awareness (Task 5): read-only workspaces under data\ — no write,
    # commit, or push tool exists for them (absent by design), and the gate
    # denies workspace writes anyway. repo.allow_patches (locked tier) is
    # the governance hook for ever changing that.
    from core.tools.repo_tools import register_repo_tools
    workspaces_dir = data_dir(config) / "workspaces"
    register_repo_tools(registry, workspaces_dir)

    # GitHub write (coherence plan Phase 4 / D6): commit + push, gated. Only
    # registers when repo.allow_git_write (LOCKED) is true — the master switch
    # Jack flips in the file himself. Even then every push confirms, and the
    # code deny-layer blocks force-push / protected branches / secrets /
    # off-allowlist repos BEFORE any card. `.get` so a sandbox config with no
    # repo section simply leaves the capability absent (its default posture).
    repo_cfg = config.get("repo", {}) or {}
    if repo_cfg.get("allow_git_write", False):
        from core.tools.git_write import GitWritePolicy, register_git_write_tools
        register_git_write_tools(
            registry, gate,
            GitWritePolicy(
                writable_repos=list(repo_cfg.get("writable_repos") or []),
                protected_branches=list(repo_cfg.get("protected_branches")
                                        or ["main", "master", "release/*"]),
            ),
            workspaces_dir,
        )

    # /watch (coherence plan Phase 4 / D5): local video comprehension, gated.
    # Only registers when video.enabled (LOCKED) is true — the heavyweight deps
    # (yt-dlp/ffmpeg/Whisper/Qwen2.5-VL) need Jack's OK per CLAUDE.md. Each tool
    # still degrades honestly if its specific dep is missing.
    video_cfg = config.get("video", {}) or {}
    if video_cfg.get("enabled", False):
        from core.tools.video_tools import register_video_tools
        register_video_tools(
            registry, gate, outbox_path, data_dir(config) / "video_cache",
            max_minutes=int(video_cfg.get("max_minutes", 90)),
            host=config["model"]["host"],
            vl_model=video_cfg.get("vl_model", "qwen2.5vl:latest"),
            whisper_model=video_cfg.get("whisper_model", "base"),
        )

    # Autonomous research (autoresearch port): clones + EXECUTES self-modified
    # code, so it's gated by TWO independent LOCKED locks. Registers only when
    # research.enabled is true AND research.allowed_repos is non-empty (the
    # deny-layer enforces the allowlist on every launch regardless, but not
    # wiring an empty-allowlist run at all keeps the capability truly absent
    # until Jack opts in). `.get(..., {}) or {}` so a sandbox config with no
    # research section simply leaves the capability absent, its default posture.
    research_cfg = config.get("research", {}) or {}
    engine_research = None
    if research_cfg.get("enabled", False):
        from core.tools.research_tools import (ResearchPolicy,
                                               register_research_tools)
        engine_research = register_research_tools(
            registry, gate,
            ResearchPolicy(
                allowed_repos=list(research_cfg.get("allowed_repos") or []),
                max_budget_hours=float(research_cfg.get("max_budget_hours", 8)),
                max_iters_per_run=int(research_cfg.get("max_iters_per_run", 200)),
                train_window_minutes=int(research_cfg.get("train_window_minutes", 5)),
                iter_timeout_minutes=int(research_cfg.get("iter_timeout_minutes", 10)),
                max_crash_retries=int(research_cfg.get("max_crash_retries", 3)),
            ),
            data_dir(config) / "research",
            host=config["model"]["host"],
            edit_model=research_cfg.get("edit_model", config["model"]["name"]),
            edit_model_num_ctx=int(research_cfg.get(
                "edit_model_num_ctx", config["model"]["num_ctx"])),
        )

    # Stage 3 senses: networked DATA sources (never cognition). Secrets live
    # under data\ (git-ignored); unconnected senses degrade to "not connected".
    secrets_dir = data_dir(config) / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    senses = Senses(config, secrets_dir, action_log)
    register_senses_tools(registry, senses, gate,
                          config.get("senses", {}).get("web_max_bytes", 200000))

    model = OllamaClient(
        host=config["model"]["host"],
        model=config["model"]["name"],
        num_ctx=config["model"]["num_ctx"],
        temperature=config["model"]["temperature"],
    )
    engine = Engine(config, model, retriever, registry, brain,
                    InteractionLogger(logs_path), persona, preferences)
    engine.gate = gate                    # taint escalation (invariant #2)
    engine.observations = observations    # Phase-3 typed-observation backbone
    engine.project_resolver = project_resolver  # Notes-10 P3 §1 resolution hint
    engine.tracker = tracker              # service/frontends reach these here
    engine.senses = senses
    engine.timelines = timelines
    engine.playbooks = playbooks
    engine.skills = skills
    engine.acc_summary = tracker.summary  # service upgrades this to the full
                                          # accountability summary (adds staleness)
    # The busy-gate in engine.respond() keys on getattr(self, "research", None):
    # the attribute is ABSENT for everyone who hasn't opted in, so there's zero
    # behaviour change unless Jack flipped research.enabled + listed a repo.
    if engine_research is not None:
        engine.research = engine_research

    # deep_think is ALWAYS available so FRIDAY can engage deep mode on her own
    # judgment when a problem genuinely needs it — she shouldn't have to ask
    # Jack to flip a config flag first. Registered after the engine so the tool
    # can flag engine.deep_active (the status box then shows "deep mode ·..."
    # so Jack knows the reply will take longer). If the heavier model isn't
    # pulled, the tool returns an honest fallback rather than bluffing. The
    # config's deep_mode.enabled is now advisory only (used by the reasoning
    # scaffold's hint), no longer a gate on availability.
    register_deep_think(registry, engine, config)

    return engine

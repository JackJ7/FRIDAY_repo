r"""
Config governance — upgrade plan Task 2 (Jack approved the self_serve tier).

The deep-mode incident generalized: any capability behind a config key FRIDAY
can't read or reach strands her the same way, and nobody finds out until she
needs it. This module makes that structurally impossible:

  * EVERY key in friday_config.yaml has a tier, assigned HERE in code (the
    tier map is itself `locked` — Tier-C territory, like the invariants: no
    tool can edit it). A key without a tier refuses to boot (validate_tiers),
    so a new feature flag must declare its posture the day it ships.
  * Tiers:
      self_serve — FRIDAY flips these at runtime on her own, NO confirm.
                   Applied to the RUNNING config only — never the file — so
                   they reset at session end by construction. Audited.
      propose    — persistent settings. FRIDAY files a proposal
                   (config\proposals.jsonl); NOTHING applies until Jack
                   approves via `python friday.py config review`. Audited.
      locked     — never self-modifiable: paths, permissions, account wiring,
                   memory provenance, budget CEILINGS (Jack sets ceilings;
                   FRIDAY spends within them). A write attempt fails loudly
                   and the attempt itself is audited.
  * Default posture for NEW capability flags is self_serve unless there's a
    stated reason otherwise (cost -> add a budget ceiling; persistence ->
    propose; safety/scope -> locked). The burden of argument sits on
    restricting FRIDAY, not on granting access — Jack's explicit ruling.
  * EVERY change from ANY actor lands in config\audit.log (JSON lines):
    self-serve flips, approved proposals, declined attempts on locked keys,
    and Jack's manual file edits (detected at load by diffing against a
    snapshot of the last-loaded config).
"""

import json
from datetime import datetime
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# THE TIER MAP. Every leaf key in the config file, each with its tier and
# (for writable tiers) validation. Adding a config key without adding it here
# refuses to boot — that's the recurrence-prevention mechanism, not a chore.
# ---------------------------------------------------------------------------

TIERS = {
    # --- model ---
    "model.name":        {"tier": "propose", "type": str},
    "model.fallback":    {"tier": "propose", "type": str},
    "model.host":        {"tier": "locked"},   # network scope
    "model.num_ctx":     {"tier": "propose", "type": int, "min": 2048, "max": 32768},
    "model.temperature": {"tier": "self_serve", "type": float, "min": 0.0, "max": 1.5},
    # --- paths / identity files: filesystem scope, Jack-only ---
    "paths.brain":       {"tier": "locked"},
    "paths.outbox":      {"tier": "locked"},
    "paths.logs":        {"tier": "locked"},
    "paths.data":        {"tier": "locked"},
    "persona_file":      {"tier": "locked"},
    "preferences_file":  {"tier": "locked"},
    "character_note":    {"tier": "locked"},
    # --- ui: persistent preferences ---
    "ui.hotkey":         {"tier": "propose", "type": str},
    "ui.window_title":   {"tier": "propose", "type": str},
    "ui.width":          {"tier": "propose", "type": int, "min": 600, "max": 4000},
    "ui.height":         {"tier": "propose", "type": int, "min": 400, "max": 3000},
    # --- senses: account wiring locked; cadence self-serve ---
    "senses.gmail_accounts":     {"tier": "locked"},
    "senses.calendar_account":   {"tier": "locked"},
    "senses.event_color_id":     {"tier": "locked"},
    "senses.poll_minutes":       {"tier": "self_serve", "type": int, "min": 1, "max": 120},
    "senses.ping_event_minutes": {"tier": "self_serve", "type": int, "min": 5, "max": 60},
    "senses.web_max_bytes":      {"tier": "propose", "type": int, "min": 10000, "max": 2000000},
    # --- accountability: operational cadence ---
    "accountability.staleness_days": {"tier": "self_serve", "type": int, "min": 1, "max": 90},
    "accountability.briefing_hour":  {"tier": "self_serve", "type": int, "min": 0, "max": 24},
    "accountability.poll_seconds":   {"tier": "self_serve", "type": int, "min": 30, "max": 3600},
    # --- reasoning / deep mode: capability switches are the self_serve
    #     poster children (this is the deep-mode fix, generalized) ---
    "reasoning.scaffold": {"tier": "self_serve", "type": str,
                           "choices": ("off", "light", "standard", "rigorous")},
    "deep_mode.enabled":  {"tier": "self_serve", "type": bool},
    "deep_mode.model":    {"tier": "propose", "type": str},
    # The budget CEILING is Jack's, not hers — she spends within it.
    "deep_mode.max_calls_per_session": {"tier": "locked"},
    # Deep-model context window (Notes-10 Phase 6). LOCKED like the other deep
    # budget keys — a reasoning model's thinking budget is a spend Jack sets.
    "deep_mode.num_ctx": {"tier": "locked"},
    # Reasoning-model <think> stripping (Notes-10 Phase 6). Both LOCKED and
    # both OPTIONAL (absent => auto): a reasoning deep model emits an inline
    # <think> scratchpad that MUST be stripped before it reaches Jack or a
    # brain note (invariant 4 + note-poisoning scar). Stripping auto-enables
    # for known reasoning-model families by name, so activating deep mode stays
    # a single-key change (deep_mode.model). strip_reasoning is Jack's explicit
    # override (force on/off when the name heuristic is wrong); the dangerous
    # direction is turning it OFF, so FRIDAY can't — hence LOCKED. think_tags
    # overrides the default ("<think>","</think>") markers for a model that
    # uses different ones.
    "deep_mode.strip_reasoning": {"tier": "locked"},
    "deep_mode.think_tags":      {"tier": "locked"},
    # --- self-consistency voting (armor A6): the switch is a capability flag
    #     (self_serve, the deep-mode posture); N is a LATENCY BUDGET — every
    #     vote costs N-1 extra decodes on the one GPU, so the ceiling is
    #     Jack's number, like deep_mode.max_calls_per_session. ---
    "voting.enabled": {"tier": "self_serve", "type": bool},
    "voting.n":       {"tier": "locked"},
    # --- memory: machinery locked except the recall width ---
    "memory.retriever":      {"tier": "locked"},
    "memory.top_k":          {"tier": "self_serve", "type": int, "min": 1, "max": 12},
    "memory.min_score":      {"tier": "self_serve", "type": float, "min": 0.0, "max": 20.0},
    "memory.git_autocommit": {"tier": "locked"},
    # --- repo awareness (Task 5): whether she may emit .patch files at all.
    #     LOCKED — and even when Jack flips it, output is patches to the
    #     outbox for him to apply; pushing doesn't exist. ---
    "repo.allow_patches": {"tier": "locked"},
    # --- GitHub write (coherence plan Phase 4 / D6): commit + push, gated.
    #     ALL locked — this is the "only future door" past read-only repos, so
    #     FRIDAY can never widen her own reach. The master switch gates whether
    #     git_commit_push registers at all; writable_repos is the allowlist
    #     (empty => nothing writable even when the switch is on); the deny-layer
    #     never pushes to a protected branch. See core/tools/git_write.py. ---
    "repo.allow_git_write":    {"tier": "locked"},
    "repo.writable_repos":     {"tier": "locked"},
    "repo.protected_branches": {"tier": "locked"},
    # --- /watch (coherence plan Phase 4 / D5): local video comprehension.
    #     LOCKED master switch — the tools need heavyweight deps (yt-dlp /
    #     ffmpeg / local Whisper / Qwen2.5-VL) that CLAUDE.md says to clear with
    #     Jack first, so they don't register until he flips this. max_minutes is
    #     a budget CEILING (Jack's number), like deep_mode.max_calls. ---
    "video.enabled":      {"tier": "locked"},
    "video.max_minutes":  {"tier": "locked"},
    "video.vl_model":     {"tier": "locked"},   # local vision model (Ollama)
    "video.whisper_model": {"tier": "locked"},  # local transcription size
    # --- autonomous research (autoresearch port): EXECUTES cloned, self-
    #     modified code — a new risk class, so scope keys are LOCKED. The master
    #     switch gates whether the tools register at all; allowed_repos is the
    #     second independent lock (empty => nothing runnable even when enabled).
    #     The ceilings are Jack's budget, spent within (like deep_mode.max_calls);
    #     edit_model/num_ctx are persistent prefs, so PROPOSE. ---
    "research.enabled":             {"tier": "locked"},
    "research.allowed_repos":       {"tier": "locked"},
    "research.edit_model":          {"tier": "propose", "type": str},
    "research.edit_model_num_ctx":  {"tier": "propose", "type": int,
                                     "min": 2048, "max": 32768},
    "research.max_budget_hours":    {"tier": "locked"},
    "research.max_iters_per_run":   {"tier": "locked"},
    "research.train_window_minutes": {"tier": "locked"},
    "research.iter_timeout_minutes": {"tier": "locked"},
    "research.max_crash_retries":   {"tier": "locked"},
    # --- projects / permissions / tools / session: scope, always locked ---
    "projects.default_root":             {"tier": "locked"},
    "permissions.large_file_mb":         {"tier": "locked"},
    "permissions.writable_project_roots": {"tier": "locked"},
    "tools.read_file_max_bytes":         {"tier": "locked"},
    "tools.max_tool_rounds":             {"tier": "locked"},
    "session.type":                      {"tier": "locked"},  # memory provenance
}


def leaves(config: dict, prefix: str = "") -> dict:
    """Dotted leaf keys -> values. A list is a leaf; keys starting with '_'
    are runtime bookkeeping (e.g. _source_path), not config."""
    out = {}
    for k, v in config.items():
        if str(k).startswith("_"):
            continue
        dotted = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(leaves(v, dotted + "."))
        else:
            out[dotted] = v
    return out


def tier_of(key: str):
    spec = TIERS.get(key)
    return spec["tier"] if spec else None


def validate_tiers(config: dict):
    """Refuse to run with an untiered key. Loud and specific: the fix is one
    line in core/config_governance.py declaring the new key's posture."""
    untiered = sorted(k for k in leaves(config) if k not in TIERS)
    if untiered:
        raise SystemExit(
            "CONFIG GOVERNANCE: untiered key(s) in the config — every key "
            "must declare a tier (self_serve / propose / locked) in "
            "core/config_governance.py TIERS before FRIDAY will start:\n  "
            + "\n  ".join(untiered)
            + "\n(Default posture for new capability flags is self_serve "
            "unless cost/persistence/safety argues otherwise.)")


def coerce(key: str, value):
    """Validate/convert a proposed value against the key's spec. Raises
    ValueError with a plain reason. Only writable tiers carry specs."""
    spec = TIERS[key]
    t = spec.get("type", str)
    if t is bool:
        if isinstance(value, bool):
            v = value
        elif str(value).lower() in ("true", "yes", "on", "1"):
            v = True
        elif str(value).lower() in ("false", "no", "off", "0"):
            v = False
        else:
            raise ValueError(f"'{value}' is not a boolean")
    elif t is int:
        v = int(value)
    elif t is float:
        v = float(value)
    else:
        v = str(value).strip()
        if not v:
            raise ValueError("empty value")
    if "min" in spec and v < spec["min"]:
        raise ValueError(f"{v} is below the minimum {spec['min']}")
    if "max" in spec and v > spec["max"]:
        raise ValueError(f"{v} is above the maximum {spec['max']}")
    if "choices" in spec and v not in spec["choices"]:
        raise ValueError(f"'{v}' is not one of {spec['choices']}")
    return v


# ---------------------------------------------------------------------------
# Audit trail — the paper trail that makes self-development debuggable.
# ---------------------------------------------------------------------------

def audit(config_dir: Path, actor: str, mode: str, key: str,
          old, new, why: str):
    """One JSON line per event in config\audit.log. actor: friday|jack.
    mode: self_serve | proposed | approved-proposal | declined-proposal |
    locked-attempt | manual-edit."""
    entry = {"ts": datetime.now().isoformat(timespec="seconds"),
             "actor": actor, "mode": mode, "key": key,
             "old": old, "new": new, "why": str(why)[:300]}
    with open(Path(config_dir) / "audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _snapshot_path(config_path: Path) -> Path:
    return config_path.parent / f".{config_path.stem}.last_loaded.yaml"


def refresh_snapshot(config_path: Path):
    _snapshot_path(config_path).write_text(
        config_path.read_text(encoding="utf-8"), encoding="utf-8")


def detect_manual_edits(config_path: Path):
    """Jack editing the file directly can't be intercepted at write time, so
    it's detected at load: diff the file against the last-loaded snapshot and
    audit every changed key as a manual edit. First boot just snapshots."""
    config_path = Path(config_path)
    snap = _snapshot_path(config_path)
    if snap.exists():
        try:
            old = leaves(yaml.safe_load(snap.read_text(encoding="utf-8")) or {})
            new = leaves(yaml.safe_load(config_path.read_text(encoding="utf-8")) or {})
        except yaml.YAMLError:
            old = new = {}
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                audit(config_path.parent, "jack", "manual-edit", key,
                      old.get(key, "(unset)"), new.get(key, "(unset)"),
                      "edited outside FRIDAY (detected at load)")
    refresh_snapshot(config_path)


# ---------------------------------------------------------------------------
# Proposals — the persistent-change path. Nothing applies until Jack reviews.
# ---------------------------------------------------------------------------

def add_proposal(config_dir: Path, key: str, value, why: str):
    entry = {"ts": datetime.now().isoformat(timespec="seconds"),
             "key": key, "value": value, "why": str(why)[:300]}
    with open(Path(config_dir) / "proposals.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def pending_proposals(config_dir: Path) -> list:
    p = Path(config_dir) / "proposals.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def apply_to_file(config_path: Path, key: str, typed, actor: str, why: str,
                  mode: str, running: dict = None):
    """Backup -> write -> audit, in that order (a failed write can't lose the
    previous state). Also live-updates the running dict when given, and
    refreshes the manual-edit snapshot so this change isn't re-audited as a
    manual edit on the next boot."""
    config_path = Path(config_path)
    live = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    section, _, leaf = key.rpartition(".")
    node = live
    if section:
        for part in section.split("."):
            node = node.setdefault(part, {})
    old = node.get(leaf, "(unset)")

    backups = config_path.parent / "backups"
    backups.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (backups / f"{config_path.stem}.{stamp}.yaml").write_text(
        config_path.read_text(encoding="utf-8"), encoding="utf-8")
    node[leaf] = typed
    config_path.write_text(
        yaml.safe_dump(live, sort_keys=False, allow_unicode=True),
        encoding="utf-8")
    # Continuity with the pre-governance trail (Tier-B kept both).
    with open(config_path.parent / "self_changes.log", "a",
              encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}  "
                f"{key}: {old!r} -> {typed!r}  why: {str(why)[:200]}\n")
    audit(config_path.parent, actor, mode, key, old, typed, why)
    refresh_snapshot(config_path)

    if running is not None:
        node_live = running
        if section:
            for part in section.split("."):
                node_live = node_live.setdefault(part, {})
        node_live[leaf] = typed
    return old


def review_proposals(config_path: Path, running: dict = None,
                     input_fn=input, print_fn=print) -> dict:
    """`python friday.py config review` — walk pending proposals, apply or
    decline each. Every outcome is audited; skipped ones stay pending."""
    config_path = Path(config_path)
    cfg_dir = config_path.parent
    pending = pending_proposals(cfg_dir)
    if not pending:
        print_fn("No pending config proposals.")
        return {"applied": [], "declined": [], "kept": []}

    applied, declined, kept = [], [], []
    for prop in pending:
        key = prop["key"]
        print_fn(f"\nPROPOSAL ({prop['ts']}): {key} -> {prop['value']!r}"
                 f"\n  why: {prop['why']}")
        ans = input_fn("  [a]pply / [d]ecline / [s]kip: ").strip().lower()
        if ans == "a":
            try:
                typed = coerce(key, prop["value"])
            except (ValueError, KeyError) as e:
                print_fn(f"  cannot apply: {e} — kept pending")
                kept.append(prop)
                continue
            apply_to_file(config_path, key, typed, actor="jack",
                          why=prop["why"], mode="approved-proposal",
                          running=running)
            print_fn(f"  applied: {key} = {typed!r} (backup + audit written)")
            applied.append(prop)
        elif ans == "d":
            audit(cfg_dir, "jack", "declined-proposal", key,
                  "(pending)", prop["value"], prop["why"])
            print_fn("  declined (audited)")
            declined.append(prop)
        else:
            kept.append(prop)

    p = cfg_dir / "proposals.jsonl"
    if kept:
        p.write_text("\n".join(json.dumps(k, ensure_ascii=False, default=str)
                               for k in kept) + "\n", encoding="utf-8")
    elif p.exists():
        p.write_text("", encoding="utf-8")
    print_fn(f"\nReview done: {len(applied)} applied, {len(declined)} "
             f"declined, {len(kept)} still pending.")
    return {"applied": applied, "declined": declined, "kept": kept}

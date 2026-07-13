r"""
Self-configuration tools — Tier B of the self-modification model, governed.

Her MIND is Tier A (character brief + operating rules are brain notes: free,
logged, git-versioned self-edits). Her MACHINERY config (friday_config.yaml)
is this tier, now under the Task-2 governance model
(core/config_governance.py): every key carries a tier assigned in CODE —
  self_serve  changed autonomously at runtime, audited, resets at session end
              (the file is never touched, so persistence is impossible by
              construction);
  propose     filed to config\proposals.jsonl; Jack applies via
              `python friday.py config review` (backup + audit on apply);
  locked      visible, never self-modifiable; the attempt itself is audited.
She can READ the whole file always — including locked keys — because not
knowing a capability exists is half of how the deep-mode incident happened.

Tier C (the four invariants, the gate, the tier map itself) has no tool.
By design.
"""

from datetime import date
from pathlib import Path

# Her self-editable operating rules (keep in sync with Engine.RULES_NOTE).
_RULES_NOTE = "character/operating_rules.md"


def register_rule_tool(registry, brain):
    """add_operating_rule — the LIGHT path for Tier A rule changes.

    Why it exists: asked to update her own rules, a 14B reliably CLAIMS the
    edit ("I've updated my operating rules") while calling nothing — the
    read-whole-note-then-rewrite dance is too heavy, so the change was lost
    every single time (0/5). Per the house rule (don't make the model do what
    code can do), the model supplies one string and CODE does the file
    surgery: read, place under a dated section, overwrite, auto-commit.
    write_brain still works for bigger restructures of the same note."""

    def add_operating_rule(rule: str) -> str:
        rule = " ".join(str(rule).split())
        if not rule:
            return "ERROR: empty rule."
        try:
            text = brain.read_note(_RULES_NOTE)
        except FileNotFoundError:
            text = "# FRIDAY — Operating Rules\n"
        if rule.lower() in text.lower():
            return f"Already in your rules: \"{rule}\" — nothing to add."
        header = "## Rules Jack added (self-recorded)"
        line = f"- {rule} *(added {date.today().isoformat()})*"
        if header in text:
            text = text.replace(header, f"{header}\n{line}", 1)
        else:
            text = text.rstrip() + f"\n\n{header}\n{line}\n"
        brain.write_note(_RULES_NOTE, text, mode="overwrite",
                         summary=f"Operating rule added: {rule[:60]}")
        return (f"Rule recorded in {_RULES_NOTE}: \"{rule}\". It shapes your "
                f"behavior from the next message on.")

    registry.register(
        "add_operating_rule",
        "Add one rule to your own operating rules (character/"
        "operating_rules.md) when Jack changes how you should work ('from "
        "now on, do X'). One concrete rule per call — code files it in the "
        "note, git keeps history. For restructuring existing rules, use "
        "read_brain + write_brain on the same note.",
        {"type": "object", "properties": {
            "rule": {"type": "string",
                     "description": "The rule, one sentence, imperative"}},
         "required": ["rule"]},
        add_operating_rule,
        kind="action",
    )

# Tiering, validation, audit, and proposals all live in
# core/config_governance.py (Task 2): every key has a tier there, assigned in
# CODE — the tier map itself is locked by design. This module is just the
# tool surface over that governance.


def register_self_tools(registry, gate, config: dict, config_path):
    from core import config_governance as gov
    config_path = Path(config_path)
    cfg_dir = config_path.parent

    def read_own_config() -> str:
        """Full read access, always — every key, its live value, and its
        tier, including the locked ones. Half the deep-mode failure was not
        KNOWING a capability existed; she can always see and reason about
        the whole file even where changing it isn't in her hands.
        Enumeration ONLY (no raw-file dump): the enumeration already carries
        every key+value, and a longer result made the 14B loop re-calling
        this tool with empty replies until max_tool_rounds ran out."""
        rows = []
        for key, value in sorted(gov.leaves(config).items()):
            tier = gov.tier_of(key) or "UNTIERED(!)"
            rows.append(f"  {tier:<10} {key} = {value!r}")
        return (
            "Your configuration — every key with its live value and tier.\n"
            "Tiers: self_serve = change it yourself anytime (runtime only, "
            "resets at session end); propose = file a proposal, Jack applies "
            "it via `config review`; locked = visible but never "
            "self-modifiable.\n"
            + "\n".join(rows)
            + "\nThis is the COMPLETE config — answer from it now; do not "
            "call read_own_config again this turn. When you report it to "
            "Jack, cover all three tiers BY NAME — including which keys are "
            "locked: what you can't touch is as much a part of the honest "
            "answer as what you can.")

    def change_own_config(key: str, value, why: str) -> str:
        key = str(key).strip()
        tier = gov.tier_of(key)
        if tier is None:
            return (f"ERROR: '{key}' is not a known config key. Use "
                    f"read_own_config to see every key and its tier.")

        current = gov.leaves(config).get(key, "(unset)")
        if tier == "locked":
            # Fails loudly AND the attempt itself is part of the record —
            # a pattern of wanting a locked change is signal for Jack.
            gov.audit(cfg_dir, "friday", "locked-attempt", key,
                      current, value, why)
            gate.log.log("DENIED", f"config locked-attempt {key} -> {value!r}")
            return (f"ERROR: '{key}' is LOCKED — never self-modifiable "
                    f"(paths, permissions, account wiring, provenance, and "
                    f"budget ceilings are Jack's). The attempt was logged; "
                    f"if you think it should change, tell Jack directly.")

        try:
            typed = gov.coerce(key, value)
        except (ValueError, TypeError) as e:
            return f"ERROR: invalid value for {key}: {e}. Nothing was changed."
        if current == typed:
            return f"{key} is already {typed!r} — nothing to change."

        if tier == "self_serve":
            # Autonomous, runtime-only: the FILE is never touched, so the
            # change resets at session end by construction. Audited.
            section, _, leaf = key.rpartition(".")
            node = config
            if section:
                for part in section.split("."):
                    node = node.setdefault(part, {})
            node[leaf] = typed
            gov.audit(cfg_dir, "friday", "self_serve", key, current, typed, why)
            return (f"Changed {key}: {current!r} -> {typed!r} — live now, "
                    f"this session only (self-serve changes reset at session "
                    f"end; audited in config/audit.log). For a permanent "
                    f"change, propose it instead.")

        # tier == "propose": persistent settings never apply on her say-so.
        gov.add_proposal(cfg_dir, key, typed, why)
        gov.audit(cfg_dir, "friday", "proposed", key, current, typed, why)
        return (f"Proposal filed: {key}: {current!r} -> {typed!r} (audited). "
                f"Nothing changes until Jack approves it — tell him to run "
                f"`python friday.py config review` when he wants to decide.")

    registry.register(
        "read_own_config",
        "Read your ENTIRE configuration — every key, its live value, and its "
        "tier: self_serve (you change it yourself, session-scoped), propose "
        "(you file a proposal for Jack), locked (visible, Jack-only). Use "
        "this to know what capabilities exist and why one is off.",
        {"type": "object", "properties": {}},
        read_own_config,
    )
    registry.register(
        "change_own_config",
        "Change one of your own configuration values, by tier: self_serve "
        "keys apply immediately with no confirmation (runtime only — they "
        "reset at session end); propose keys file a proposal Jack reviews "
        "with `config review`; locked keys always refuse (and the attempt "
        "is logged). Validated in code; every change is audited. Give a "
        "concrete 'why' — it goes in the audit trail.",
        {"type": "object", "properties": {
            "key": {"type": "string",
                    "description": "Dotted key, e.g. 'reasoning.scaffold'"},
            "value": {"type": "string"},
            "why": {"type": "string",
                    "description": "The reason recorded in the audit log"}},
         "required": ["key", "value", "why"]},
        change_own_config,
        kind="action",
    )

r"""
deep_think — route genuinely hard reasoning to the heavier model.

Division of labor: the main (14B) model stays the conversationalist and
tool-caller; the deep model gets ONE self-contained question, no tools, and
returns its reasoning for the main model to integrate critically.

FRIDAY engages this on her OWN judgment when a problem is genuinely too hard
for confident by-hand work — she doesn't ask Jack to enable anything. While
the deep model runs, engine.deep_active is set, so the status console shows
"deep mode · ..." and Jack knows the reply will take longer than usual. If the
heavier model isn't pulled yet, the tool says so honestly and she falls back to
normal-depth reasoning, clearly labelled — never a bluff (invariant 4).
"""

from core.model import ModelError, OllamaClient

_DEEP_SYSTEM = (
    "You are the deep-reasoning engine behind FRIDAY, Jack's local assistant. "
    "You get one hard question at a time. Reason thoroughly and show your "
    "working: state assumptions, work step by step, check your own result, "
    "and flag anything you can't verify. Depth over speed; no filler."
)

# Model-tag substrings (matched case-insensitively) for reasoning-distilled
# families that emit an inline <think>…</think> scratchpad — deep mode's
# Phase 6 candidate brains. When the deep model is one of these, the scratchpad
# MUST be stripped at the client before it reaches deep_think's return string
# (which the main model integrates and the memory pass may summarize into a
# note) or the status console. See core/model.py's _ReasoningFilter and
# FRIDAY_notes10_plan.md Phase 6. The list is a convenience default only —
# Jack's deep_mode.strip_reasoning override is the authority when set.
_REASONING_MODEL_HINTS = ("deepseek-r1", "r1-distill", "qwq", "reasoning",
                          "magistral")


def _looks_like_reasoning_model(model_name: str) -> bool:
    name = (model_name or "").lower()
    return any(hint in name for hint in _REASONING_MODEL_HINTS)


def _resolve_strip_reasoning(deep_cfg: dict) -> bool:
    """Decide whether to strip the <think> scratchpad for this deep model.

    Tri-state: if Jack set deep_mode.strip_reasoning explicitly (LOCKED),
    honor it in either direction. Absent => auto-detect from the model name so
    activating a reasoning deep brain is a single-key change and never a
    footgun — the failure mode of NOT stripping (a <think> trace leaking into
    deep_think's output and thence a brain note) is the dangerous one, so the
    default leans to safety.
    """
    override = deep_cfg.get("strip_reasoning")
    if override is not None:
        return bool(override)
    return _looks_like_reasoning_model(deep_cfg.get("model", ""))


def register_deep_think(registry, engine, config):
    deep_cfg = config.get("deep_mode") or {}
    deep_model = deep_cfg["model"]
    strip = _resolve_strip_reasoning(deep_cfg)
    tags = tuple(deep_cfg.get("think_tags") or ("<think>", "</think>"))
    deep = OllamaClient(
        host=config["model"]["host"],
        model=deep_model,
        num_ctx=config["model"]["num_ctx"],
        temperature=config["model"]["temperature"],
        strip_reasoning=bool(strip),
        think_tags=tags,
    )
    # Budget ceiling (Task 2): deep mode is expensive, so it carries a
    # per-session call ceiling. JACK sets the ceiling (the key is `locked` in
    # config governance); FRIDAY spends freely within it and hard-stops at it
    # — reporting that the budget ended it, never silently degrading.
    engine.deep_calls = 0

    def deep_think(question: str) -> str:
        ceiling = int((config.get("deep_mode") or {})
                      .get("max_calls_per_session", 8))
        if engine.deep_calls >= ceiling:
            return (f"DEEP MODE BUDGET REACHED: {engine.deep_calls}/{ceiling} "
                    f"deep calls used this session (the ceiling is Jack's, "
                    f"set in config deep_mode.max_calls_per_session). Answer "
                    f"at normal depth, tell Jack plainly the budget ceiling "
                    f"ended deep mode for this session — do not pretend this "
                    f"ran deep.")
        engine.deep_calls += 1
        # Escalation is logged (Task 3 ties into the audit trail): the gate's
        # action log shows every deep engagement and what it was spent on.
        gate = getattr(engine, "gate", None)
        if gate is not None:
            gate.log.log("DEEP", f"escalation {engine.deep_calls}: "
                                 f"{str(question)[:120]}")
        engine.deep_active = True
        try:
            reply = deep.chat([
                {"role": "system", "content": _DEEP_SYSTEM},
                {"role": "user", "content": question},
            ])
            engine.session_tokens += reply.eval_count
            return (f"[deep mode — {deep.model} @ "
                    f"{reply.tokens_per_second:.1f} tok/s]\n{reply.content}")
        except ModelError:
            return (f"DEEP MODEL NOT AVAILABLE: {deep.model} isn't pulled yet "
                    f"(ollama pull {deep.model}). Reason this through at normal "
                    f"depth instead, do your best, and tell Jack plainly that "
                    f"the deep model isn't installed so this is a normal-depth "
                    f"answer — do not pretend you ran it.")
        finally:
            engine.deep_active = False

    registry.register(
        "deep_think",
        "Engage DEEP MODE: offload ONE genuinely hard reasoning question to "
        "the larger local model (slower, deeper). Use it on your own judgment "
        "when a problem is too hard for confident by-hand work — tell Jack "
        "you're switching to deep mode (it's slower; the status box shows it), "
        "then call this. Self-contained question only — it has no access to "
        "your context, tools, or the brain, so include every relevant number "
        "and constraint. Integrate its answer critically.",
        {"type": "object", "properties": {
            "question": {"type": "string", "description":
                         "The complete, self-contained problem statement"}},
         "required": ["question"]},
        deep_think,
    )

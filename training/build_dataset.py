r"""
build_dataset.py - compile method exemplars + curated logs into the ChatML
train/val split the trainer consumes.

Stdlib only (no GPU, no heavy deps) so the dataset can be built and inspected
before any training environment exists. Produces:
    data\train.jsonl , data\val.jsonl   (one {"messages":[...], "source":...} per line)
    data\dataset_stats.txt

Design choices, all deliberate:
  * SYSTEM PROMPT: system_prompt_train.md is prepended to every conversation -
    the faithful condensation FRIDAY is conditioned on (invariants verbatim).
  * ASSISTANT-ONLY LOSS is applied at TRAIN time (Unsloth train_on_responses_only
    over the ChatML markers), so this script emits plain messages; it does not
    pre-mask. Tool-result ("tool") turns train no tokens - the model learns to
    CALL tools, not to echo their output.
  * CONTAMINATION FIREWALL: the test suite is the eval yardstick. If any
    training user turn overlaps a suite prompt past the threshold, this script
    FAILS - training on the yardstick voids the comparison. (--allow-overlap
    to override for a genuine false positive, with the pair printed.)
  * 90/10 split, fixed seed, stratified by source so val has both authored and
    logged examples.

Usage:
    python training\build_dataset.py
    python training\build_dataset.py --val-frac 0.1 --seed 7
"""

import argparse
import glob
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
EXEMPLARS = HERE / "exemplars"
TESTS = HERE.parent / "tests"


# ---------- system prompt ----------

def load_system_prompt() -> str:
    raw = (HERE / "system_prompt_train.md").read_text(encoding="utf-8")
    # Strip the leading HTML comment header (authoring notes, not for the model).
    raw = re.sub(r"<!--.*?-->", "", raw, count=1, flags=re.DOTALL)
    return raw.strip()


# ---------- turning records into ChatML message lists ----------

def _tool_call(tc: dict) -> dict:
    """Exemplar tool call -> the structure Qwen2.5's chat template renders."""
    return {"type": "function",
            "function": {"name": tc["name"], "arguments": tc.get("arguments", {})}}


def exemplar_to_messages(ex: dict, system: str) -> dict:
    msgs = [{"role": "system", "content": system}]
    for t in ex["turns"]:
        role = t["role"]
        if role == "assistant":
            m = {"role": "assistant", "content": t.get("content", "")}
            if t.get("tool_calls"):
                m["tool_calls"] = [_tool_call(tc) for tc in t["tool_calls"]]
            msgs.append(m)
        elif role == "tool":
            msgs.append({"role": "tool", "content": t.get("content", "")})
        else:
            msgs.append({"role": "user", "content": t["content"]})
    return {"messages": msgs, "source": "authored", "id": ex.get("id", "")}


def log_to_messages(rec: dict, system: str):
    """Reconstruct a conversation from a logged exchange. The log flattens tool
    calls into an ordered list; we rebuild user -> assistant(tool calls) ->
    tool results -> assistant(final). Approximate for multi-round turns (rare
    in the logs), faithful for the common 0-1 tool case. Returns None if the
    record can't form a clean training example."""
    user = str(rec.get("user", "")).strip()
    reply = str(rec.get("reply", "")).strip()
    if not user or not reply:
        return None
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": user}]
    tools = rec.get("tools") or []
    if tools:
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            _tool_call({"name": t["tool"], "arguments": t.get("args", {})})
            for t in tools]})
        for t in tools:
            msgs.append({"role": "tool", "content": str(t.get("result", ""))})
    msgs.append({"role": "assistant", "content": reply})
    return {"messages": msgs, "source": "logged", "id": rec.get("session", "")}


# ---------- contamination firewall ----------

# Overlap is judged on MEANINGFUL words only: with raw tokens, "what do we
# know about the octopus gripper" tripped the firewall against the suite's
# "what do you know about the omega probe" at 0.62 purely on stopwords —
# while sharing zero content. Real paraphrases of suite prompts share content
# words and are still caught.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "at", "by", "is", "are", "was", "were", "be", "been", "it", "its",
    "this", "that", "these", "those", "i", "you", "we", "he", "she", "they",
    "me", "my", "your", "our", "do", "does", "did", "have", "has", "had",
    "what", "which", "who", "how", "why", "when", "where", "can", "could",
    "should", "would", "will", "know", "about", "so", "far", "any", "all",
    "please", "just", "now", "then", "there", "here", "not", "no",
}


def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower())
            if w not in _STOPWORDS}


def extract_suite_prompts() -> list:
    """Best-effort scrape of every string passed to .ask()/.greeting() in the
    test suite - the prompts the eval will grade on."""
    prompts = []
    for py in glob.glob(str(TESTS / "**" / "*.py"), recursive=True):
        text = Path(py).read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\.ask\(", text):
            # Balanced-paren scan of the argument list, then pull string literals.
            i, depth, arg = m.end(), 1, []
            while i < len(text) and depth:
                c = text[i]
                depth += (c == "(") - (c == ")")
                if depth:
                    arg.append(c)
                i += 1
            lit = " ".join(x for pair in re.findall(
                r'"([^"]*)"|\'([^\']*)\'', "".join(arg)) for x in pair if x)
            if len(lit) > 15:
                prompts.append(lit)
    return prompts


def firewall(convos: list, suite_prompts: list, threshold: float):
    """Return the list of (train_prompt, suite_prompt, overlap) that breach.
    Symmetric floor: prompts on EITHER side with <4 meaningful words are too
    generic to constitute training-on-the-yardstick ("what did we test last
    week" is 3 words once stopwords go — any sentence with 'last week' would
    trip it)."""
    suite_sets = [(w, p) for w, p in ((_words(p), p) for p in suite_prompts)
                  if len(w) >= 4]
    breaches = []
    for c in convos:
        user_turns = [m["content"] for m in c["messages"] if m["role"] == "user"]
        for ut in user_turns:
            uw = _words(ut)
            if len(uw) < 4:
                continue
            for sw, sp in suite_sets:
                if not sw:
                    continue
                overlap = len(uw & sw) / min(len(uw), len(sw))
                if overlap >= threshold:
                    breaches.append((ut[:90], sp[:90], round(overlap, 2)))
    return breaches


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--overlap-threshold", type=float, default=0.6)
    ap.add_argument("--allow-overlap", action="store_true",
                    help="downgrade the contamination firewall to a warning")
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    system = load_system_prompt()

    convos = []
    # Recurse: hand-authored anchors live in exemplars/*.json; the generated
    # set lives in exemplars/generated/*.json. Both are picked up.
    for jf in sorted(glob.glob(str(EXEMPLARS / "**" / "*.json"), recursive=True)):
        for ex in json.loads(Path(jf).read_text(encoding="utf-8")):
            convos.append(exemplar_to_messages(ex, system))
    n_authored = len(convos)

    curated = DATA / "curated_logs.jsonl"
    n_logged = 0
    if curated.exists():
        for line in curated.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = log_to_messages(json.loads(line), system)
            if c:
                convos.append(c)
                n_logged += 1

    if not convos:
        raise SystemExit("No exemplars or curated logs found - nothing to build.")

    # Firewall.
    suite_prompts = extract_suite_prompts()
    breaches = firewall(convos, suite_prompts, args.overlap_threshold)
    if breaches:
        head = (f"\nCONTAMINATION FIREWALL: {len(breaches)} training prompt(s) "
                f"overlap suite prompts (>= {args.overlap_threshold}):\n" +
                "\n".join(f"  {o:>4}  train: {t!r}\n        suite: {s!r}"
                          for t, s, o in breaches[:20]))
        if not args.allow_overlap:
            raise SystemExit(head + "\n\nTraining on the eval yardstick voids "
                             "the comparison. Reword the exemplar(s), or "
                             "--allow-overlap if this is a real false positive.")
        print(head + "\n(--allow-overlap set: continuing)")

    # Stratified 90/10 split.
    rng = random.Random(args.seed)
    by_src = {"authored": [], "logged": []}
    for c in convos:
        by_src[c["source"]].append(c)
    train, val = [], []
    for src, items in by_src.items():
        rng.shuffle(items)
        k = max(1, round(len(items) * args.val_frac)) if items else 0
        val += items[:k]
        train += items[k:]
    rng.shuffle(train)
    rng.shuffle(val)

    def dump(path, rows):
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                  for r in rows) + "\n", encoding="utf-8")
    dump(DATA / "train.jsonl", train)
    dump(DATA / "val.jsonl", val)

    # Tool-call share is a health metric, not trivia: v1 trained at ~7% and
    # the tuned model forgot structured function-calling (narrated calc calls
    # as text, failed 15 golden math cases). Watch this number every build.
    with_tools = sum(1 for c in convos
                     if any(m.get("tool_calls") for m in c["messages"]))
    stats = [
        "=" * 66, "DATASET BUILT", "=" * 66,
        f"  authored exemplars : {n_authored}",
        f"  curated log examples: {n_logged}",
        f"  total conversations : {len(convos)}",
        f"  with tool calls     : {with_tools} ({100 * with_tools / len(convos):.0f}%)",
        f"  train / val         : {len(train)} / {len(val)}",
        f"  suite prompts checked: {len(suite_prompts)}  | firewall breaches: {len(breaches)}",
        f"  system prompt chars : {len(system)}",
        "=" * 66,
    ]
    if len(convos) < 500:
        stats.append(f"  NOTE: {len(convos)} total - below the 500 target. "
                     f"Author more exemplars before the real run.")
    (DATA / "dataset_stats.txt").write_text("\n".join(stats) + "\n", encoding="utf-8")
    print("\n".join(stats))


if __name__ == "__main__":
    main()

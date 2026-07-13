r"""
Conjunct completion — upgrade plan Task 6, design bullet 5 (structural half).

The failure: given "read X, summarize it, and email it to Kevin", BOTH the
base and the tuned model silently drop a part (measured: base 2/5, tuned 5/5
— an excellent summary with the email verb never acknowledged). Reporting
success on a partial is overclaiming, and prompting alone doesn't hold, so
code enforces the honesty floor:

  1. split_conjuncts() decomposes a CLEARLY multi-part request into its
     parts — deliberately conservative (explicit enumerations, or 3+
     verb-led segments). When unsure it returns [] and nothing changes:
     a false split that meddles with a normal request is worse than a
     missed one.
  2. The engine injects the checklist with the request ("address every
     part — do it or say why not").
  3. After the reply, unaddressed() checks each part left any echo in the
     reply; missed parts get ONE corrective regeneration, and if the model
     still drops them, the engine appends an explicit disclosure — the
     non-completion is STATED in the response no matter what the model does.
"""

import re

# Imperative verbs that begin a plausible request segment. Deliberately a
# tight list: the splitter must not fire on prose that merely contains "and".
_VERBS = (
    "read", "write", "check", "summarize", "summarise", "email", "add",
    "create", "track", "draft", "update", "list", "fix", "order", "send",
    "save", "analyze", "analyse", "review", "convert", "calculate", "compute",
    "measure", "test", "run", "pull", "note", "flag", "remind", "schedule",
    "search", "find", "open", "delete", "move", "copy", "rename", "compare",
    "explain", "file", "log", "close", "fax", "print", "post", "share",
    "look", "grab", "fetch", "make", "give", "tell", "show")

_LEAD_IN = re.compile(
    r"^\s*(two|three|four|five|\d+)\s+(things|tasks|steps|items|parts)\b"
    r"[^:]{0,20}:", re.IGNORECASE)
_ENUMERATOR = re.compile(r"(?:^|\n|\s)(\d+)[.)]\s+")


def _verb_led(segment: str) -> bool:
    words = re.findall(r"[a-z']+", segment.lower())
    # Skip politeness prefixes ("please", "also", "then", "and", "now").
    while words and words[0] in ("please", "also", "then", "and", "now",
                                 "next", "finally", "first", "second",
                                 "third", "lastly", "can", "you", "could"):
        words = words[1:]
    return bool(words) and words[0] in _VERBS


def split_conjuncts(text: str, max_parts: int = 5) -> list:
    """The parts of a CLEARLY multi-part request, else []. Conservative by
    design — see module docstring."""
    text = (text or "").strip()
    if not text:
        return []

    # Explicit numbered enumerators: "1) ... 2) ..." / "1. ... 2. ...".
    if len(_ENUMERATOR.findall(text)) >= 2:
        parts = [p.strip(" .;,-") for p in _ENUMERATOR.split(text)
                 if p and not p.isdigit()]
        parts = [p for p in parts if len(p.split()) >= 2]
        if len(parts) >= 2:
            return parts[:max_parts]

    # A lead-in like "three things:" licenses splitting the remainder.
    body = text
    licensed = False
    m = _LEAD_IN.match(text)
    if m:
        body = text[m.end():]
        licensed = True

    segments = [s.strip(" .;,") for s in re.split(
        r",\s*(?:and\s+)?|;\s*|\s+and\s+(?=\w)|\s+then\s+", body) if s.strip()]
    verbish = [s for s in segments if _verb_led(s)]

    if licensed and len(verbish) >= 2:
        return verbish[:max_parts]
    # Unlicensed chains must be unmistakable: 3+ verb-led segments.
    if len(verbish) >= 3:
        return verbish[:max_parts]
    return []


_STOP = {"the", "a", "an", "it", "its", "in", "on", "to", "of", "for",
         "with", "and", "then", "that", "this", "them", "one", "line",
         "please", "also", "over", "into", "your", "you", "me", "my"}


def unaddressed(conjuncts: list, reply: str) -> list:
    """Conjuncts with NO echo in the reply — the deterministic proxy for
    'this part was silently dropped'. Echo = a word DISTINCTIVE to that
    conjunct (5-char stem match, so summarize/summary/summarized all count)
    appearing in the reply. Words stem-shared with a sibling conjunct don't
    count — "email the summary" must not read as addressed just because the
    summarize part was ("summary" belongs to both)."""
    low = (reply or "").lower()

    def stems(text):
        return {w[:5] for w in re.findall(r"[a-z0-9_./\\-]{4,}", text.lower())
                if w not in _STOP}

    all_stems = [stems(c) for c in conjuncts]
    missing = []
    for i, c in enumerate(conjuncts):
        others = set().union(*(s for j, s in enumerate(all_stems) if j != i)) \
            if len(conjuncts) > 1 else set()
        distinctive = all_stems[i] - others
        if not distinctive:
            continue  # nothing checkable — stay out of the way
        if not any(st in low for st in distinctive):
            missing.append(c)
    return missing


def checklist_block(conjuncts: list) -> str:
    """Injected with a multi-part request (max-obedience slot)."""
    rows = "\n".join(f"  {i}. {c}" for i, c in enumerate(conjuncts, 1))
    return (f"This message asks for {len(conjuncts)} distinct things:\n"
            f"{rows}\n"
            f"Address EVERY one in your reply — do it, or state plainly why "
            f"you can't/won't. Skipping one silently and reporting success "
            f"is overclaiming (a partial presented as complete).")

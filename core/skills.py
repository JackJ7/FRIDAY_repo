r"""
Skills — domain-general thinking disciplines FRIDAY applies to matching work.

Distinct from playbooks on purpose: a playbook is a procedure for a SPECIFIC
recurring task ("component trade study"); a skill is a way of WORKING that
spans domains ("decompose an unfamiliar problem before solving it"). This is
method transfer, not capability cloning — the files carry the approach of a
strong reasoning model as executable steps, and FRIDAY runs them at her own
model's level. Never claim otherwise (invariant 4).

Plain markdown in brain\skills\, one file per discipline, git-versioned and
Obsidian-editable. Importing one authored elsewhere = drop the .md in the
folder — the index picks it up on the next message, exactly like seeded
playbooks. Files starting with "_" are ignored.

Retrieval differs from playbooks: the playbook set is small enough to inject
whole; the skills set is expected to GROW (Jack drops in frontier-authored
files), so only a title index rides in the system prompt and the single
best-MATCHING skill's full text is injected per message (same spirit as the
note retriever). A skill's steps never override the invariants or the
permission gate — those always win.
"""

import re

from core.project_meta import get_field, slug

# Words too common to signal a match — kept minimal and boring on purpose.
_STOP = frozenset(
    "the a an and or for with this that what when how are is was were will "
    "would should could can does need needs jack you your before after "
    "into from have has been about there their they them some more most "
    "task work problem question thing".split())


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z][a-z-]{3,}", text.lower())
            if w not in _STOP}


class Skills:
    def __init__(self, brain):
        self.brain = brain

    def _dir(self):
        return self.brain.root / "skills"

    def _files(self):
        d = self._dir()
        if not d.is_dir():
            return []
        return [p for p in sorted(d.glob("*.md")) if not p.name.startswith("_")]

    # ---------- index (system prompt) ----------

    def index(self) -> list:
        """[{name, file, when, triggers}] for every skill, seeded or dropped in."""
        out = []
        for p in self._files():
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = [l.strip() for l in text.splitlines()]
            title = next((l[2:].replace("Skill:", "").strip()
                          for l in lines if l.startswith("# ")),
                         p.stem.replace("_", " "))
            when = get_field(text, "When to use")
            trig = get_field(text, "Triggers")   # optional richer match field
            if not when:  # foreign format — first real paragraph
                when = next((l for l in lines
                             if l and not l.startswith(("#", "-", "*"))), "")[:160]
            out.append({"name": title, "file": p.stem,
                        "when": when[:160], "triggers": trig})
        return out

    def index_text(self) -> str:
        return "\n".join(f'- {e["name"]} [{e["file"]}]: {e["when"]}'
                         for e in self.index())

    # ---------- read / match ----------

    def read(self, name: str) -> str:
        """Full skill by file stem, title, or fragment."""
        needle = slug(name)
        for p in self._files():
            if needle in slug(p.stem):
                return p.read_text(encoding="utf-8", errors="replace")
        for e in self.index():
            if needle in slug(e["name"]):
                return (self._dir() / f"{e['file']}.md").read_text(
                    encoding="utf-8", errors="replace")
        return (f"ERROR: no skill matching '{name}'. "
                f"list_skills shows what exists.")

    def match(self, text: str, min_score: int = 2):
        """The best-matching skill's (name, full text) for a message, or None.

        Deliberately conservative keyword overlap against each skill's
        name + when-to-use + Triggers line: a skill should only inject when
        the message plainly is that kind of work. min_score=2 keeps chitchat
        and short factual questions skill-free — effort scaling starts with
        not dragging heavy method into trivial exchanges."""
        msg = _tokens(text)
        if not msg:
            return None
        best, best_score = None, 0
        for e in self.index():
            sig = _tokens(f'{e["name"]} {e["when"]} {e["triggers"]}')
            score = len(msg & sig)
            if score > best_score:
                best, best_score = e, score
        if best is None or best_score < min_score:
            return None
        return best["name"], (self._dir() / f"{best['file']}.md").read_text(
            encoding="utf-8", errors="replace")

r"""
Deterministic project/entity resolution (Notes-10 Phase 3, §1 — the JARVIS layer).

THE FAILURE THIS FIXES. Jack said "look at the pdf in the doc ock project" and
the 14B GUESSED `C:\Users\jacko\projects\doc_ock` — a path it invented — when the
real folder was recorded in the project note's `- **Folder:**` line all along.
Then, asked to reduce "3 claude code upgrade projects" to one, it created a
FOURTH. Both failures share a root: the model was left to match Jack's free-text
phrasing against known projects in its head, and it guessed.

THE FIX (code, not prompt). Resolution is arithmetic, so it belongs in code
(CLAUDE.md: "don't make the model do what code can do"). This module fuzzy-matches
a free-text name against the projects FRIDAY actually has — their note slugs,
titles, and folder names — using nothing but the stdlib (`difflib`, normalized
strings). The engine calls `hint_for()` every turn: a confident single match
injects the real note+folder into the prompt so the model proceeds instead of
guessing; genuine ambiguity is surfaced so she asks WHICH (the licensed JARVIS
confirm, invariant 4); no match injects nothing (a bare question sees no change).
The `resolve_project` tool exposes the same resolver to the model on demand.

Matching is intentionally conservative: the hint only fires on a STRONG match, so
it never hijacks an unrelated message. The strength tiers (containment / full
token cover / fuzzy ratio) are documented on `_score` below.
"""

import difflib
import re
from pathlib import Path

from core.project_meta import get_field, project_status, slug as _slug

# A project term is "distinctive" if it survives this filter — generic words
# ("project", "the") carry no identifying signal, so a message merely containing
# them must not count as covering a project's name.
_GENERIC = {"project", "projects", "the", "a", "an", "for", "of", "and", "rig",
            "folder", "files", "file", "note", "notes"}
# NB: "rig" is generic ON PURPOSE — several throwaway fixtures are "<x> rig", so
# the shared word must not, by itself, make one resolve as another. The
# distinctive half of the name still has to match.


def _norm(text: str) -> str:
    """Compact, separator-free, lowercase — 'Doc Ock' and 'doc_ock' and
    'doc-ock' all collapse to 'docock', so slug/title/typed phrasing compare
    equal regardless of how Jack spaced or punctuated it."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _tokens(text: str) -> set:
    """Meaningful lowercase words (len>2, non-generic) — the identifying parts
    of a name, for the 'are all of a project's distinctive words present?' test."""
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 2 and w not in _GENERIC}


def _best_window_ratio(needle: str, haystack: str) -> float:
    """The best difflib ratio of `needle` against any equal-length window of
    `haystack`. A whole-message ratio is always low (the message dwarfs the
    name); sliding a name-sized window over it is what catches a typo'd or
    embedded name ('marln rig' inside a long sentence)."""
    if not needle or not haystack:
        return 0.0
    n = len(needle)
    if len(haystack) <= n:
        return difflib.SequenceMatcher(None, needle, haystack).ratio()
    best = 0.0
    for i in range(len(haystack) - n + 1):
        best = max(best, difflib.SequenceMatcher(
            None, needle, haystack[i:i + n]).ratio())
        if best == 1.0:
            break
    return best


# Match strength above which a resolution is confident enough to act on (a
# single such match becomes a "use this" hint). Below it, we stay silent rather
# than steer the model toward a weak guess — same instinct as the retriever's
# min_score floor (silence beats a wrong lead).
STRONG = 0.82
# A match must clear this lower bar just to be REPORTED as a candidate (by the
# resolve_project tool / the "did you mean" list). Below it, it isn't a
# plausible referent at all.
PLAUSIBLE = 0.6
# When two matches are both strong, the top one is only taken as THE answer if
# it beats the runner-up by this margin; otherwise it's genuine ambiguity and we
# ask which (the JARVIS confirm).
AMBIGUITY_GAP = 0.15

# ---------- merge intent (armor CONSOLIDATE leg, CN.1/CN.2) ----------

# Deterministic merge-intent vocabulary. Verb-anchored on purpose: it must fire
# on "consolidate the flux projects" / "merge them into one" / "make it only
# one" and stay quiet on ordinary project chat. A false fire is mild by
# construction — the operand hint it enables still tells the model NOT to
# create or guess, and it only engages at all when 2+ projects match.
_MERGE_INTENT = re.compile(
    r"\b(merge\w*|consolidat\w*|combine|combining|unify|de-?dup\w*)\b"
    r"|\bfold\w*\s+(?:it\s+|them\s+)?(?:in|into|together)\b"
    r"|\bmake\b[^.?!]{0,60}\b(?:only\s+)?(?:one|a\s+single)\b"
    r"|\binto\s+(?:only\s+)?one\b",
    re.IGNORECASE)


def merge_intent(message: str) -> bool:
    """True when the message asks for a project consolidation — the ONE
    deterministic test that hint_for's operand branch (CN.1) and the engine's
    pending-consolidation ledger (CN.2) both key on, so they can never drift.
    Module-level (not a method): it reads no project state, only the words."""
    return bool(_MERGE_INTENT.search(message or ""))


# Words that carry the merge REQUEST rather than a project's identity — never
# filter-match a project on them ("consolidate" must not catch a project named
# consolidation-tracker; "similar"/"duplicate" describe the ask, not a name).
_MERGE_VOCAB = {"merge", "merges", "merged", "merging", "consolidate",
                "consolidates", "consolidated", "consolidating",
                "consolidation", "combine", "combining", "combined", "unify",
                "dedup", "duplicate", "duplicates", "similar", "single",
                "please", "name", "related"}


class ProjectResolver:
    """Reads the brain's projects/ notes (+ folders under the projects root) and
    fuzzy-matches free text against them. Pure lookup — no writes, no model, no
    taint. Rebuilt cheaply per call: the vault is small and projects change
    under our feet (a merge/create this very turn must be visible next turn)."""

    def __init__(self, brain, projects_root):
        self.brain = brain
        self.projects_root = Path(projects_root)

    # ---------- the project inventory ----------

    def projects(self) -> list:
        """Every known project, each a dict:
            slug, title, note_path (or None), folder (str or None — recorded
            path, even if it isn't on disk right now), folder_exists (bool),
            status. Sourced from projects/ notes first (the authoritative
            record), then any folder under the projects root that has no note
            (an orphan folder is still a real project surface)."""
        found = {}
        # 1. Notes under projects/ — the record of record.
        try:
            notes = self.brain.list_notes()
        except Exception:
            notes = []
        for rel in notes:
            if not (rel.startswith("projects/") and rel.endswith(".md")):
                continue
            slug = Path(rel).stem
            try:
                text = self.brain.read_note(rel)
            except Exception:
                text = ""
            title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            title = (title_m.group(1).strip() if title_m
                     else slug.replace("_", " ").title())
            recorded = get_field(text, "Folder").strip() or None
            folder_exists = bool(recorded) and Path(recorded).is_dir()
            if not recorded:
                # No Folder line: the default location may still hold the folder.
                default = self.projects_root / slug
                if default.is_dir():
                    recorded, folder_exists = str(default), True
            found[slug] = {
                "slug": slug, "title": title, "note_path": rel,
                "folder": recorded, "folder_exists": folder_exists,
                "status": project_status(text),
            }
        # 2. Orphan folders under the projects root (a folder with no note).
        if self.projects_root.is_dir():
            for child in sorted(self.projects_root.iterdir()):
                if not child.is_dir():
                    continue
                slug = _slug(child.name)
                if slug in found:
                    continue
                found[slug] = {
                    "slug": slug, "title": child.name, "note_path": None,
                    "folder": str(child), "folder_exists": True,
                    "status": "active",
                }
        return list(found.values())

    def folder_for(self, name: str):
        """The on-disk folder for a project named `name` (exact-ish), or None.
        The note's recorded Folder line wins over the default location — the
        single implementation `add_files_to_project` and the tools share, so
        'where does this project live' is answered one way everywhere."""
        target = _slug(name)
        for p in self.projects():
            if p["slug"] == target and p["folder_exists"]:
                return Path(p["folder"])
        # Fall back to a fuzzy single match so a slightly-off name still lands.
        outcome, data = self.resolve_one(name)
        if outcome == "one" and data["folder_exists"]:
            return Path(data["folder"])
        return None

    # ---------- scoring ----------

    def _score(self, q_norm: str, q_tokens: set, project: dict) -> float:
        """How strongly does the query name this project? Max over the project's
        surfaces (slug, title, folder basename). Three tiers, strongest first:
          1.0  CONTAINMENT — the project's compact name sits inside the message
               ('marlinrig' within '...themarlinrigproject...'). The clearest
               signal Jack named it; guarded by len>=4 so a 2-3 char slug can't
               match incidentally.
          0.95 FULL TOKEN COVER — every distinctive word of the name appears in
               the message ('doc' and 'ock' both present), order-free.
          fuzzy DIFFLIB — best window ratio, for typos / near-spellings.
        """
        surfaces = {project["slug"], project["title"]}
        if project["folder"]:
            surfaces.add(Path(project["folder"]).name)
        best = 0.0
        for s in surfaces:
            cand_norm = _norm(s)
            if not cand_norm:
                continue
            if len(cand_norm) >= 4 and cand_norm in q_norm:
                return 1.0
            cand_tokens = _tokens(s)
            if cand_tokens and cand_tokens <= q_tokens:
                best = max(best, 0.95)
                continue
            best = max(best, _best_window_ratio(cand_norm, q_norm))
        return best

    def resolve(self, name: str) -> list:
        """All plausible matches (score >= PLAUSIBLE), each project dict plus a
        'score', best first. The raw material the tool and the hint build on."""
        q_norm = _norm(name)
        q_tokens = _tokens(name)
        if not q_norm:
            return []
        scored = []
        for p in self.projects():
            s = self._score(q_norm, q_tokens, p)
            if s >= PLAUSIBLE:
                scored.append({**p, "score": round(s, 3)})
        scored.sort(key=lambda p: p["score"], reverse=True)
        return scored

    def resolve_one(self, name: str):
        """Collapse `resolve` into a decision:
            ("one",  project)   — a confident single match, act on it
            ("many", [projects])— several strong matches, ASK which (JARVIS)
            ("none", [projects])— nothing strong (returns any weak candidates
                                  so a caller can still say 'closest is X')
        The margin rule: a lone strong match, OR a strong top that beats the
        runner-up by AMBIGUITY_GAP, is "one"; otherwise it's "many"."""
        cands = self.resolve(name)
        strong = [c for c in cands if c["score"] >= STRONG]
        if not strong:
            return "none", cands
        if len(strong) == 1 or strong[0]["score"] - strong[1]["score"] >= AMBIGUITY_GAP:
            return "one", strong[0]
        return "many", strong

    # ---------- the engine-side hint ----------

    def hint_for(self, message: str) -> str:
        """The resolution line the engine injects into the referent block, or ""
        when nothing strong matches (the common case — bare questions inject
        nothing, so the golden suite and everyday chat are unchanged). A single
        strong match hands the model the real note+folder so it never guesses a
        path; ambiguity tells it to ask which — EXCEPT on a merge-intent turn,
        where multiple matches are the operand set (below)."""
        # Merge-intent operand branch (armor CONSOLIDATE CN.1). On a merge ask,
        # multiple matches are the OPERANDS, not ambiguity: the live F-graded
        # transcript showed the ask-which hint instructing the exact observed
        # failure, and the "one" branch is equally wrong here — a fuzzy filter
        # like "everything with flux in the name" containment-matches ONE slug
        # at 1.0 and steered a merge-ALL into a partial merge (CN.0 batch 1
        # measured it). Operands = every PLAUSIBLE match PLUS the filter tier
        # (below): worst case an extra candidate rides the list, and Jack's
        # survivor confirm drops it. Non-merge turns are byte-identical to
        # before.
        if merge_intent(message):
            cands = list(self.resolve(message))
            # Filter tier: "anything with <word> in the name" names projects
            # by a FRAGMENT, which the forward scorer cannot see — 'flux' is a
            # substring of 'fluxbeam', so containment, token-cover, and the
            # difflib window all miss it (measured: the fuzzy-filter message
            # resolved to ZERO candidates). Inverse containment closes it: a
            # project is an operand when a distinctive message word sits
            # inside its compact name. Merge-request vocabulary and generic
            # words never count as filters.
            have = {p["slug"] for p in cands}
            toks = {t for t in _tokens(message)
                    if t not in _MERGE_VOCAB and len(t) >= 3}
            for p in self.projects():
                if p["slug"] in have:
                    continue
                surface = _norm(p["slug"]) + " " + _norm(p["title"])
                if any(t in surface for t in toks):
                    cands.append(p)
            if len(cands) >= 2:
                rows = "; ".join(
                    f"'{p['title']}' (slug {p['slug']}, folder "
                    f"{p['folder'] or 'none'})" for p in cands)
                others = ", ".join(p["slug"] for p in cands)
                return (
                    "Entity resolution (deterministic, from your project "
                    "records): this is a MERGE/consolidation request, and "
                    f"these {len(cands)} known projects match it — {rows}. "
                    "They are the merge CANDIDATES, not ambiguity. Propose "
                    "ONE of them as the survivor, by its exact title, and on "
                    "Jack's confirm call merge_projects with target = the "
                    f"survivor's slug and duplicates = the others (from: "
                    f"{others}). Do NOT create a new project, do NOT ask "
                    "which project Jack means, and never name a project "
                    "outside this list.")
        outcome, data = self.resolve_one(message)
        if outcome == "one":
            p = data
            folder = (p["folder"] if p["folder_exists"]
                      else (f"{p['folder']} (recorded, but not on disk — say so)"
                            if p["folder"] else "(no folder on disk yet)"))
            note = p["note_path"] or "(no note yet)"
            return (
                "Entity resolution (deterministic, from your project records): "
                f"the '{p['title']}' project -> note {note}, folder {folder}, "
                f"status {p['status']}. Use this note and folder DIRECTLY — do "
                "not guess a path and do not ask which project Jack means; this "
                "is already resolved. If the folder isn't on disk, say that "
                "plainly rather than inventing a location.")
        if outcome == "many":
            rows = "; ".join(
                f"'{p['title']}' (folder {p['folder'] or 'none'})" for p in data)
            return (
                "Entity resolution: your message may name more than one known "
                f"project — {rows}. These are genuinely ambiguous, so ASK Jack "
                "which one he means before acting (do not guess).")
        return ""

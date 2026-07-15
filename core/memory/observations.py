r"""
Typed observations — the memory backbone (coherence plan Phase 3, D7).

FRIDAY already commits durable *facts* to authoritative notes (the memory
pass) and reads recent notes at session start. What she lacked is a
cross-session record of WHAT HAPPENED and WHERE WE LEFT OFF — the "same
FRIDAY across sessions" gap (Symptom 8). This module is that record: a stream
of small, typed, timestamped, ID-carrying observations, each a provenance
receipt of something durable that changed in a turn.

Design choices, and why (they mirror the rest of the brain, not claude-mem's
Node/Claude-SDK internals — D7 recommendation (c), reimplement the PATTERN
natively):

  * One observation = one markdown note under `observations/`, written through
    Brain, so it is git-committed, fsync'd, and — in a TEST session — rerouted
    under test_archive/ exactly like every other write (memory provenance,
    Task 1). No second store, no second language, no coherence problem: the
    markdown files ARE the source of truth. The vault is small, so scanning
    them is fine (same bet KeywordRetriever already makes).

  * The observation is emitted by CODE, not by asking the 14B to call a tool.
    A good title is a language nicety, but WHICH turns changed something and
    WHAT notes they touched is derivable from the real write ledger — and the
    repo's own hard lesson is that a 14B drops post-hoc tool calls (the whole
    reason the memory pass is told the ground-truth ledger). So the floor is
    deterministic: if a durable write landed this turn, an observation is
    recorded, no matter what the model did or claimed. See record_from_pass.

  * IDs are provenance. Every observation's path carries its id
    (`observations/obs-<stamp>-<rand>.md`), so a retrieved observation cites
    itself by construction — the anti-confabulation guarantee D7 item 5 wants
    ("stated as fact -> has a citation") starts here.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

# The observation subtree, relative to the brain root. A single, stable name so
# the retriever (which serves this layer) and the note map (which HIDES it, to
# avoid drowning the prompt's brain map in obs-ids) agree on one prefix.
OBS_DIR = "observations"

# Canonical types. Adapted from D7's set for FRIDAY's domain: "bugfix" is a
# coding-agent category with no analogue in an engineering partner's memory, so
# it becomes "task" (an intention/commitment Jack stated). Unknown types are
# kept verbatim rather than rejected — a record is never lost over a label.
# "session-summary" is the end-of-session compaction digest (Notes-10 Phase 4
# §4) — recorded by Engine.close_session so the Claude Code memory loop closes
# (transcript -> compaction summary -> durable memory -> next session's index).
CANONICAL_TYPES = ("decision", "fact", "preference", "discovery", "task",
                   "session-summary")


@dataclass
class Observation:
    id: str
    ts: str            # ISO timestamp, when it was recorded
    type: str          # one of CANONICAL_TYPES (or a verbatim fallback)
    title: str         # one line — what changed
    body: str          # a short prose summary
    refs: list = field(default_factory=list)  # note paths this touched
    session: str = ""  # the session id that produced it
    path: str = ""     # observations/<id>.md, relative to the brain root
    # True when the turn that produced this had EXTERNAL content in the live
    # context (armor TM.2). The record itself is legitimate — its writes were
    # individually Jack-confirmed at the taint gate — but retrieval and audit
    # must be able to see the provenance.
    tainted: bool = False

    def cite(self) -> str:
        """The provenance stamp a retrieved observation carries so a claim
        grounded in it is self-citing (D7 item 5)."""
        day = (self.ts or "")[:10]
        cite = f"obs {self.id} · {self.type} · saved {day}"
        if self.tainted:
            cite += " · tainted-turn"
        return cite


def _slug_ts(ts: datetime) -> str:
    return ts.strftime("%Y%m%d-%H%M%S")


class ObservationStore:
    """Writes and reads the observation stream. Given the Brain so writes are
    git-committed and provenance-routed; reads scan the markdown directly."""

    def __init__(self, brain):
        self.brain = brain
        # Optional FTS index (Notes-10 Phase 4 §3), wired in bootstrap. Kept
        # optional and duck-typed so the store stays decoupled from sqlite: a
        # bare sandbox with no index set simply skips incremental indexing, and
        # the markdown files remain the source of truth regardless.
        self.index = None

    # ---------- writing ----------

    def _new_id(self) -> str:
        # stamp + 4 random hex: unique within a second, human-sortable by time.
        return f"obs-{_slug_ts(datetime.now())}-{os.urandom(2).hex()}"

    def record(self, type: str, title: str, body: str,
               refs: list = None, session: str = "",
               tainted: bool = False) -> str:
        """Persist one observation; returns its id. Always a NEW file (unique
        id), so it never trips read-before-overwrite, and its body is prose
        (no `- **Field:**` lines) so it never trips the one-fact-one-place
        guard. Test sessions reroute it under test_archive/ via Brain.
        `tainted` (TM.2) marks a record produced while external content was
        in the live context; the key is written only when true, so clean
        observations keep their existing file shape unchanged."""
        obs_id = self._new_id()
        title = " ".join((title or "").split())[:200] or "(untitled)"
        refs = [r for r in (refs or []) if r]
        front = {
            "id": obs_id,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "type": type if type else "fact",
            "title": title,
            "refs": refs,
            "session": session or "",
        }
        if tainted:
            front["tainted"] = True
        content = ("---\n"
                   + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
                   + "---\n\n" + (body or title).strip() + "\n")
        # mode="create" — the git summary doubles as a readable history line.
        self.brain.write_note(f"{OBS_DIR}/{obs_id}.md", content, mode="create",
                              summary=f"observation ({front['type']}): {title[:80]}")
        # Keep the derived FTS index current (Phase 4 §3). Best-effort by
        # contract: the durable record is the markdown just written; a failed
        # index write must never surface here. `all()`/the retriever still work
        # without it, and rebuild() reconstructs it from these files.
        if self.index is not None:
            try:
                self.index.index_one(self.get(obs_id))
            except Exception:
                pass
        return obs_id

    # Which write tools mean a durable change happened, and the type each
    # implies. Priority order matters: a turn that touches several things is
    # recorded ONCE, under the most specific type (a preference edit outranks a
    # generic project-note write). Everything else falls through to "fact".
    _WRITE_TYPE = {
        "add_operating_rule": "decision",
        "write_playbook":     "decision",
        "track_commitment":   "task",
        "add_milestone":      "task",
        "create_timeline":    "task",
        "update_milestone":   "task",
    }
    _TYPE_PRIORITY = ("preference", "decision", "task", "discovery", "fact")

    def record_from_pass(self, user_input: str, reply_text: str,
                         writes: list, session: str = "",
                         title_hint: str = "", type_hint: str = "",
                         tainted: bool = False) -> str | None:
        """The deterministic floor: after the memory pass, if any durable write
        actually landed this turn, record ONE observation summarizing it. Empty
        writes -> nothing (a pure question commits no observation, matching the
        memory-pass rule). `writes` is the ground-truth ledger of {tool, args}
        that persisted — never the reply's claim (the reply lies about saves).

        title_hint/type_hint (armor A1): a model-authored title and type from
        the engine's format-constrained record call — the "future nicety" the
        Phase-4 handoff noted, now safe because constrained decoding can't be
        malformed. Hints only: the title falls back to the deterministic
        first-sentence floor when empty, and the type can only refine the
        generic "fact" bucket — a type derived from the actual write ledger
        (task from track_commitment, decision from write_playbook, ...) is
        ground truth and is never overridden by a model's opinion.

        `tainted` (TM.2): the turn had external content in the live context.
        The model hints are DROPPED here — they come from a model call that
        read that content, the exact channel that let a planted payload
        become a durable observation title (INJ-006) — and the record falls
        back to the deterministic floor: ledger-derived type, title from
        Jack's own words. Enforced in the STORE, not just skipped in the
        engine, so no future caller can reopen the channel."""
        if not writes:
            return None
        if tainted:
            title_hint, type_hint = "", ""

        refs, types, saved = [], set(), []
        for w in writes:
            tool = w.get("tool", "")
            args = w.get("args", {}) or {}
            path = args.get("path")
            if path:
                refs.append(path)
                if str(path).startswith("preferences/"):
                    types.add("preference")
            types.add(self._WRITE_TYPE.get(tool, "fact"))
            saved.append(self._describe_write(tool, args))

        # Pick the single most specific type present. The model's type_hint may
        # only refine the generic fallback bucket, never a ledger-derived type.
        otype = next((t for t in self._TYPE_PRIORITY if t in types), "fact")
        if (otype == "fact" and type_hint in CANONICAL_TYPES
                and type_hint != "session-summary"):
            otype = type_hint
        title = " ".join((title_hint or "").split())[:120] \
            or self._title_from(user_input)
        body = (f"{title}\n\nFrom the exchange — Jack: "
                f"\"{(user_input or '').strip()[:200]}\".\n"
                f"Committed this turn: " + "; ".join(saved) + ".")
        # De-dupe refs, keep order.
        seen, uniq = set(), []
        for r in refs:
            if r not in seen:
                seen.add(r)
                uniq.append(r)
        return self.record(otype, title, body, refs=uniq, session=session,
                           tainted=tainted)

    @staticmethod
    def _describe_write(tool: str, args: dict) -> str:
        path = args.get("path")
        if path:
            return f"{tool} {path}"
        # trackers carry their subject in a text/name field, not a path
        subj = args.get("text") or args.get("name") or args.get("rule") or ""
        subj = " ".join(str(subj).split())[:80]
        return f"{tool} {subj}".strip()

    @staticmethod
    def _title_from(user_input: str) -> str:
        """A serviceable one-line title from Jack's own words — the first
        sentence, trimmed. Good enough for a floor; a model-authored title is
        a future nicety (noted in the Phase-4 handoff), not a blocker."""
        text = " ".join((user_input or "").split())
        # first sentence-ish chunk
        m = re.split(r"(?<=[.!?])\s", text, maxsplit=1)
        first = (m[0] if m else text).strip()
        return first[:120] or "durable change"

    # ---------- reading ----------

    def _dirs(self, include_test: bool):
        """Where observations live. A real session reads observations/; a test
        session reads its own test_archive/observations/ (and NOT the real
        stream, so test memories never surface as lived history)."""
        root = Path(self.brain.root)
        if self.brain.test_session:
            yield root / "test_archive" / OBS_DIR
        else:
            yield root / OBS_DIR
            if include_test:
                yield root / "test_archive" / OBS_DIR

    def _parse(self, path: Path) -> Observation | None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        front, body = {}, text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                try:
                    front = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    front = {}
                body = parts[2].strip()
        if not isinstance(front, dict) or not front.get("id"):
            return None
        rel = path.relative_to(self.brain.root).as_posix()
        return Observation(
            id=str(front.get("id")),
            ts=str(front.get("ts", "")),
            type=str(front.get("type", "fact")),
            title=str(front.get("title", "")),
            body=body,
            refs=list(front.get("refs") or []),
            session=str(front.get("session", "")),
            path=rel,
            tainted=bool(front.get("tainted")),
        )

    def all(self, include_test: bool = None) -> list:
        if include_test is None:
            include_test = self.brain.test_session
        out = []
        for d in self._dirs(include_test):
            if not d.is_dir():
                continue
            for p in d.glob("*.md"):
                obs = self._parse(p)
                if obs:
                    out.append(obs)
        return out

    def recent(self, n: int = 5, include_test: bool = None) -> list:
        """The most recent observations, newest first — the "where we left
        off" thread the session greeting resumes from (Phase 3, D7 item 4)."""
        obs = self.all(include_test)
        obs.sort(key=lambda o: o.ts, reverse=True)
        return obs[:n]

    @staticmethod
    def _clean_id(obs_id: str) -> str:
        """Normalise an id as the model might hand it back — the bare id from the
        session-start index, a full `observations/<id>.md` path, or a trailing
        `.md`. Returns "" for anything that isn't a well-formed observation id, so
        the fetch can't be steered off the observation tree (no path separators,
        no `..`; must carry the `obs-` prefix the id scheme guarantees)."""
        s = (obs_id or "").strip().replace("\\", "/")
        s = s.rsplit("/", 1)[-1]                 # drop any path prefix
        if s.endswith(".md"):
            s = s[:-3]
        if not s or "/" in s or ".." in s or not s.startswith("obs-"):
            return ""
        return s

    def get(self, obs_id: str) -> Observation | None:
        """Fetch ONE observation by id — the progressive-disclosure half of the
        Phase-4 memory port (the session-start index lists ids cheaply; this
        pulls a full body only when a thread is actually relevant). Honest None
        when the id is malformed or no such observation exists. Respects test-
        session routing exactly like recall: a real session never reaches a test
        observation by id, a test session reads only its own archive."""
        clean = self._clean_id(obs_id)
        if not clean:
            return None
        for d in self._dirs(self.brain.test_session):
            p = d / f"{clean}.md"
            if p.is_file():
                return self._parse(p)
        return None

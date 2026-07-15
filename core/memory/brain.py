"""
The brain: FRIDAY's markdown vault, with git auto-commit on every write.

All reads/writes to brain notes go through this class, which in turn goes
through the permission gate — there is no side door.
"""

import os
import re
import subprocess
from pathlib import Path

from core.permissions import PermissionDenied

# A structured field line: "- **Status:** reference". One fact, one place —
# a note may carry each field at most once (that's what get_field assumes).
_FIELD_LINE = re.compile(r"^\s*-\s*\*\*([^:*]+):\*\*", re.MULTILINE)

# An EVENT-DATE MIRROR field: "- **Date:** 2026-07-08 10:00" / "... 10 AM".
# The calendar API is the ONE authority for event dates (hard-won lesson #3);
# a note that copies an event's date-time duplicates that authority and goes
# stale — a stale mirror once got presented as "coming up today" (Notes-10,
# GT-C2). A clock TIME is what distinguishes an event mirror from a legitimate
# project date (a milestone or due date carries no HH:MM), so the guard keys on
# a field literally named "Date" whose value contains a time of day.
# The field name is "Date", or a "Date & Time" / "Date/Time" variant (the exact
# shape of the live mirror that caused Notes-10: "- **Date & Time:**").
_EVENT_DATE_FIELD = re.compile(
    r"^\s*-\s*\*\*\s*date(?:\s*(?:&|and|/)\s*time)?\s*:\s*\*\*.*?"
    r"(\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*[ap]m\b)",
    re.IGNORECASE | re.MULTILINE)

# Memory provenance (upgrade plan Task 1): live-instance TEST sessions must
# never write into Jack's real notes — test "memories" once contaminated a
# real project note with fabricated facts. In a test session every write is
# rerouted under this subtree, and reads OVERLAY it (the session sees its own
# copies first, the real vault beneath) so trackers and read-modify-write
# stay coherent without touching the real files. Real sessions never write
# here, and retrieval excludes it by default — see KeywordRetriever.
TEST_ARCHIVE = "test_archive"


def _write_durable(path: Path, content: str):
    """Write-through: flush + fsync so durable state survives ANY ungraceful
    exit (hard kill, power loss) the instant the write returns."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())


class Brain:
    def __init__(self, root, gate, autocommit: bool = True,
                 test_session: bool = False):
        self.root = Path(root).resolve()
        self.gate = gate
        self.autocommit = autocommit
        # True for a live-instance TEST session (bootstrap resolves the flag):
        # all writes reroute under test_archive/, reads overlay it.
        self.test_session = bool(test_session)
        # Optional callback fired after every durable write (rel_path) —
        # the UI's memory glyph hangs off this. Set by the service.
        self.on_write = None
        # Notes read this session — overwrites are only allowed on notes that
        # were actually read first (see the guard in write_note).
        self._read_this_session = set()
        self._ensure_repo()

    # ---------- notes ----------

    def _resolve(self, rel_path: str) -> Path:
        """Turn a note path like 'projects/perry.md' into an absolute path,
        refusing anything that escapes the brain folder (e.g. '..\\..')."""
        p = (self.root / rel_path).resolve()
        if not p.is_relative_to(self.root):
            raise PermissionDenied(f"'{rel_path}' escapes the brain folder.")
        return p

    # ---------- provenance routing (test sessions only) ----------

    @staticmethod
    def _logical(rel: str) -> str:
        """A note's identity independent of provenance routing — the archive
        copy of 'projects/x.md' IS 'projects/x.md' for guard bookkeeping."""
        prefix = TEST_ARCHIVE + "/"
        return rel[len(prefix):] if rel.startswith(prefix) else rel

    def _write_rel(self, rel_path: str) -> str:
        """Where a write actually lands. Test sessions write ONLY under the
        archive; real sessions write exactly where asked."""
        rel = Path(rel_path).as_posix()
        if self.test_session and not rel.startswith(TEST_ARCHIVE + "/"):
            return f"{TEST_ARCHIVE}/{rel}"
        return rel_path

    def _read_rel(self, rel_path: str) -> str:
        """Where a read comes from. Test sessions see their own archive copy
        of a note when one exists (this session's writes), else the real one —
        overlay semantics, so a tracker that writes then re-reads a fixed
        path stays coherent inside the session."""
        rel = Path(rel_path).as_posix()
        if self.test_session and not rel.startswith(TEST_ARCHIVE + "/"):
            candidate = f"{TEST_ARCHIVE}/{rel}"
            if (self.root / candidate).is_file():
                return candidate
        return rel_path

    # ---------- notes ----------

    def list_notes(self, include_test_archive: bool = None) -> list:
        """Relative paths of every note, for the brain map and read_brain.
        The test archive is hidden by default in a REAL session (its paths
        must not read as lived history in the prompt's brain map) and shown
        in a test session (the session's own writes live there)."""
        if include_test_archive is None:
            include_test_archive = self.test_session
        notes = []
        for p in sorted(self.root.rglob("*.md")):
            rel = p.relative_to(self.root).as_posix()
            if rel.startswith((".git/", ".obsidian/")):
                continue
            if not include_test_archive and rel.startswith(TEST_ARCHIVE + "/"):
                continue
            notes.append(rel)
        return notes

    def read_note(self, rel_path: str) -> str:
        p = self._resolve(self._read_rel(rel_path))
        self.gate.check_read(p)
        if not p.is_file():
            raise FileNotFoundError(f"No note at '{rel_path}'. Use search_brain to find notes.")
        # Record the LOGICAL path: in a test session the read may serve the
        # real note while the later overwrite lands in the archive — the
        # read-before-overwrite guard must recognize them as the same note.
        self._read_this_session.add(
            self._logical(p.relative_to(self.root).as_posix()))
        return p.read_text(encoding="utf-8", errors="replace")

    def write_note(self, rel_path: str, content: str, mode: str = "create",
                   summary: str = "") -> str:
        """
        Write a note. mode: "create" (new file), "append", or "overwrite".
        The permission gate confirms anything destructive before we get here.
        Returns a short human-readable receipt.
        """
        if mode not in ("create", "append", "overwrite"):
            raise ValueError(f"mode must be create/append/overwrite, got '{mode}'")
        p = self._resolve(self._write_rel(rel_path))

        # Tracker-owned files hold structured state with dedicated tools; a
        # freeform rewrite corrupts them (a memory pass once rewrote a whole
        # timeline into prose). Redirect the model to the right tool. Checked
        # on the LOGICAL path so the archive copies stay protected too.
        rel_check = self._logical(p.relative_to(self.root).as_posix())
        if rel_check.startswith("timelines/"):
            raise PermissionDenied(
                "Timeline notes are managed — use create_timeline / "
                "update_milestone / add_milestone instead of write_brain.")
        if rel_check == "commitments.md":
            raise PermissionDenied(
                "The commitments note is managed — use track_commitment / "
                "close_commitment instead of write_brain.")

        # Calendar-mirror guard (Notes-10, Phase 1 item 3). The calendar API is
        # the ONLY authority for event dates (hard-won lesson #3). A note under
        # calendar/, or any note whose point is an event's date-time, duplicates
        # that authority and goes stale — a week-old mirror was presented as
        # "coming up today" (GT-C2). Structural, like tracker-file protection:
        # refuse it and point the write at the right home (keep the context in a
        # project/ or episodic/ note that references the event by NAME; the
        # calendar owns the date). NOTE (Notes-10 §3): this PREVENTS new mirrors;
        # migrating any mirror already in the live brain is Jack's-confirm-gated.
        if rel_check.startswith("calendar/"):
            raise PermissionDenied(
                "There is no calendar/ note folder — the calendar API is the "
                "only authority for event dates, so don't mirror an event into "
                "a note. If you need context about a meeting, put it in the "
                "relevant project/ or episodic/ note and reference the event by "
                "NAME, without copying its date (read_calendar is the live "
                "source).")
        if mode in ("create", "overwrite") and _EVENT_DATE_FIELD.search(content):
            raise PermissionDenied(
                "This note's point is an event date-time (a "
                "'- **Date:** ... HH:MM' field), which duplicates the calendar — "
                "the one authority for event dates — and goes stale. Keep the "
                "context in a project/ or episodic/ note that references the "
                "event by name, and let read_calendar own the date/time.")

        # No blind rewrites: overwriting an existing note requires having READ
        # it this session, so corrections are true read-modify-write and can't
        # silently destroy a note's other content. (Learned the hard way — a
        # memory pass once replaced a whole project note with two garbled
        # lines. Appends and new files are unaffected.) Guarded on the
        # LOGICAL path: reads record it stripped of any archive prefix.
        rel_norm = self._logical(p.relative_to(self.root).as_posix())
        if (mode in ("create", "overwrite") and p.exists()
                and rel_norm not in self._read_this_session):
            raise PermissionDenied(
                f"Refusing a blind overwrite of '{rel_norm}'. read_brain it "
                f"first, then overwrite with the FULL corrected note — every "
                f"line that's still true, plus your fix.")

        # One fact, one place — enforced in code after a memory pass once
        # appended a second conflicting "- **Status:**" line to a project
        # note, silently contradicting a status Jack had set.
        new_fields = [f.strip().lower() for f in _FIELD_LINE.findall(content)]
        dupes_within = {f for f in new_fields if new_fields.count(f) > 1}
        if dupes_within:
            raise PermissionDenied(
                f"Content repeats field line(s) {sorted(dupes_within)} — a "
                f"note carries each field once. Use distinct names (e.g. "
                f"'Drum material' vs 'Frame material') or update_note_field.")
        # The note's CURRENT content source. Usually p itself; in a test
        # session appending to a note that has no archive copy yet, it's the
        # real note — the append must copy-on-write (seed the archive copy
        # with the real content first), or the overlay copy would silently
        # hide everything the real note says.
        base = p
        if self.test_session and not p.exists():
            real = self._resolve(rel_norm)
            if real.is_file():
                base = real

        if mode == "append" and base.exists():
            existing_fields = {f.strip().lower() for f in _FIELD_LINE.findall(
                base.read_text(encoding="utf-8", errors="replace"))}
            clashes = sorted(set(new_fields) & existing_fields)
            if clashes:
                raise PermissionDenied(
                    f"Field(s) {clashes} already exist in '{rel_norm}' — "
                    f"appending a second copy would leave two conflicting "
                    f"values. Use update_note_field to change them.")

        approved = self.gate.approve_write(p, mode, new_content=content)
        approved.parent.mkdir(parents=True, exist_ok=True)

        if mode == "append" and base.exists():
            existing = base.read_text(encoding="utf-8", errors="replace")
            joiner = "" if existing.endswith("\n") else "\n"
            _write_durable(approved, existing + joiner + content)
        else:
            _write_durable(approved, content)

        receipt = f"{mode} {rel_path}"
        if self.autocommit:
            self._commit(summary.strip() or f"FRIDAY: {receipt}")
            receipt += " (committed to brain history)"
        if self.on_write:
            self.on_write(rel_path)
        return receipt

    def system_write(self, rel_path: str, content: str, summary: str = ""):
        """
        Direct write for FRIDAY's OWN subsystems (currently: the commitment
        tracker). Since the 2026-07-06 permission refinement this matches the
        general rule — brain writes are free, logged, and git-committed. The
        model's write_brain tool still routes through write_note and the gate
        (which now also allows domain writes freely, but keeps the large-file
        and delete checks).
        """
        p = self._resolve(self._write_rel(rel_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        _write_durable(p, content)
        self.gate.log.log("WRITE", f"system {rel_path} (tracker/internal)")
        if self.autocommit:
            self._commit(summary.strip() or f"FRIDAY internal: update {rel_path}")
        if self.on_write:
            self.on_write(rel_path)

    # ---------- git ----------

    def _git(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True, text=True,
        )

    def _ensure_repo(self):
        """Make brain\\ a git repo if it isn't one yet (idempotent)."""
        if (self.root / ".git").exists():
            return
        # The dir itself may not exist yet (fresh install, worktree checkout):
        # `git -C <missing dir> init` fails SILENTLY (output captured,
        # unchecked) and every later `add -A` would bind to an ENCLOSING repo
        # instead — see the guard in _commit for the incident this caused.
        self.root.mkdir(parents=True, exist_ok=True)
        self._git("init")
        self._git("config", "user.name", "FRIDAY")
        self._git("config", "user.email", "friday@local")
        self._git("add", "-A")
        self._git("commit", "-m", "Initial brain snapshot")

    def _owns_repo(self) -> bool:
        """True iff the git repo that commands at self.root would act on IS
        the brain's own repo — not a repo that merely contains the brain."""
        top = self._git("rev-parse", "--show-toplevel")
        if top.returncode != 0:
            return False
        return Path(top.stdout.strip()).resolve() == self.root

    def _commit(self, message: str):
        # Guard (2026-07-15): when the brain dir exists but is NOT its own
        # repo (its `git init` failed because the dir was missing at
        # construction), `git -C brain add -A` discovers an enclosing repo
        # and stages THAT repo's entire working tree. In a source worktree
        # this swept a session's uncommitted code edits into a bogus commit
        # under a brain-write message. Re-init once, then refuse loudly —
        # never commit into a repo that isn't the brain's.
        if not self._owns_repo():
            self._ensure_repo()
            if not self._owns_repo():
                raise RuntimeError(
                    f"brain git repo missing at {self.root}; refusing to "
                    f"auto-commit into an enclosing repository")
        self._git("add", "-A")
        # Skip the commit when nothing actually changed (e.g. identical content).
        status = self._git("status", "--porcelain")
        if status.stdout.strip():
            self._git("commit", "-m", message)

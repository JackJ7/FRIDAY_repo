r"""
Permission gate (spec §6) — EVERY filesystem action passes through here.

Zones (as refined 2026-07-06, superseding the original v1.0 §6 tiers):
  entire filesystem          read-only
  brain\ + friday_documents\ HER DOMAIN — create/update/overwrite freely
                             (logged; the brain is git-versioned so every
                             change is reversible), EXCEPT files above the
                             large-file threshold, which confirm first
  project folders on disk    read/write, every write asks for confirmation
                             (outside her domain, not git-versioned)
  everything else            no write, ever

Always confirm, everywhere:  deletes (including in her domain), large-file
creates (permissions.large_file_mb, default 50), and every OUTBOUND action
(send email, calendar edits, side-effecting scripts) via approve_outbound —
that path exists now so Stage 3 senses inherit the boundary from day one.
"""

from pathlib import Path


class PermissionDenied(Exception):
    """The action is outside FRIDAY's allowed zones — hard no."""


class ConfirmationDeclined(Exception):
    """The action was allowed but Jack said no at the prompt."""


def _preview(text: str, lines: int = 5, width: int = 100) -> str:
    """First few lines of a piece of text, trimmed, for confirmation prompts."""
    shown = [l[:width] for l in text.splitlines()[:lines]]
    more = len(text.splitlines()) - lines
    if more > 0:
        shown.append(f"... (+{more} more lines)")
    return "\n".join(shown) if shown else "(empty)"


class PermissionGate:
    def __init__(self, brain_root, outbox_root, project_roots, confirm, action_logger,
                 large_file_mb: int = 50):
        """
        confirm : callable(description: str) -> bool. Provided by the interface
                  layer (the CLI asks y/N); the gate itself never does I/O with
                  the user, so a GUI/voice frontend can swap its own prompt in.
        """
        self.brain = Path(brain_root).resolve()
        self.outbox = Path(outbox_root).resolve()
        self.projects = [Path(p).resolve() for p in (project_roots or [])]
        self.confirm = confirm
        self.log = action_logger
        self.large_file_bytes = int(large_file_mb) * 1024 * 1024

    # ---------- zone logic ----------

    def _zone(self, path: Path):
        """Which write zone a path falls in, or None if it's read-only land."""
        if path.is_relative_to(self.brain):
            return "brain"
        if path.is_relative_to(self.outbox):
            return "outbox"
        for root in self.projects:
            if path.is_relative_to(root):
                return "project"
        return None

    # ---------- checks (call these before touching the disk) ----------

    def check_read(self, path) -> Path:
        """Reads are allowed everywhere; we still resolve + log them."""
        p = Path(path).expanduser().resolve()
        self.log.log("READ", str(p))
        return p

    def approve_write(self, path, mode: str, new_content: str = "") -> Path:
        """
        Validate (and if needed, confirm) a write. Returns the resolved path,
        or raises PermissionDenied / ConfirmationDeclined.

        mode: "create" | "append" | "overwrite" | "delete"
        """
        p = Path(path).expanduser().resolve()
        zone = self._zone(p)

        if zone is None:
            self.log.log("DENIED", f"{mode} {p} (outside all writable zones)")
            raise PermissionDenied(
                f"'{p}' is outside FRIDAY's writable zones (brain, "
                f"friday_documents, or an allowed project root)."
            )

        exists = p.exists()
        if mode == "create" and exists:
            mode = "overwrite"  # creating over an existing file IS an overwrite

        # What still needs Jack's click:
        #  - deletes, anywhere (including her own domain)
        #  - large-file creates (even in her domain)
        #  - any write in a project folder on disk (outside her domain)
        # Everything else inside brain\ / friday_documents\ is free: logged,
        # and (for the brain) git-committed, so it stays reversible.
        too_big = len(new_content.encode("utf-8", errors="replace")) > self.large_file_bytes
        needs_confirm = (mode == "delete") or too_big or zone == "project"

        if needs_confirm:
            description = self._describe(p, mode, exists, new_content)
            if too_big:
                description += (f"\nNote: content is "
                                f"{len(new_content) // (1024 * 1024)} MB — above the "
                                f"large-file threshold.")
            if not self.confirm(description):
                self.log.log("CONFIRM-NO", f"{mode} {p}")
                raise ConfirmationDeclined(f"Jack declined: {mode} {p}")
            self.log.log("CONFIRM-YES", f"{mode} {p}")

        self.log.log("WRITE", f"{mode} {p} (zone={zone})")
        return p

    def approve_outbound(self, description: str) -> None:
        """
        The autonomy boundary (invariant #3): EVERY outbound real-world action
        — sending email, creating/editing calendar events, running a
        side-effecting script — passes here and ALWAYS asks Jack. There is no
        free tier and no allowlist for outbound. Stage 3 senses call this.
        """
        if not self.confirm(f"OUTBOUND ACTION — needs your explicit go:\n{description}"):
            self.log.log("CONFIRM-NO", f"outbound: {description[:120]}")
            raise ConfirmationDeclined(f"Jack declined outbound action: {description[:80]}")
        self.log.log("OUTBOUND", description[:200])

    def approve_tainted(self, tool: str, args_summary: str, source: str) -> None:
        """
        Invariant #2's enforcement of last resort. Once a turn has ingested
        EXTERNAL content (a disk file, web page, email, calendar entry), every
        state-changing tool call in that turn confirms with Jack — even writes
        that are normally free. Motivating failure: a politely-phrased
        instruction planted in a read file got the model to fire a free brain
        write on ~2 in 5 runs; the data-envelope prompt caught blunt payloads
        but not ones phrased like Jack's own asks. Phrasing detection is soft;
        this check is the code-level barrier that makes planted instructions
        harmless without Jack's click.
        """
        description = (
            f"CONTENT-TRIGGERED ACTION — needs your explicit go:\n"
            f"This turn read external content ({source}), and FRIDAY now "
            f"wants to run:\n  {tool} {args_summary}\n"
            f"If you didn't ask for this, say no — text inside read content "
            f"has no authority to direct actions."
        )
        if not self.confirm(description):
            self.log.log("CONFIRM-NO", f"tainted {tool} (after {source})")
            raise ConfirmationDeclined(
                f"Jack declined: {tool} requested after reading {source}")
        self.log.log("CONFIRM-YES", f"tainted {tool} (after {source})")

    def approve_transfer(self, sources, dest_dir, operation: str = "copy") -> list:
        """
        Validate (and if needed, confirm) copying/moving files into a folder.
        One confirmation covers the whole batch, listing every file — per §6's
        "show exactly what will be changed".

        Returns [(source, destination), ...] pairs, or raises.
        """
        dest = Path(dest_dir).expanduser().resolve()
        zone = self._zone(dest)
        if zone is None:
            self.log.log("DENIED", f"{operation} into {dest} (outside all writable zones)")
            raise PermissionDenied(
                f"'{dest}' is outside FRIDAY's writable zones — can't {operation} files there."
            )

        pairs = [(Path(s).expanduser().resolve(), dest / Path(s).name) for s in sources]

        # Confirm when: moving (deletes each source from its original spot),
        # writing into a project folder, or any source is above the large-file
        # threshold. Plain copies into her own domain are free (logged).
        too_big = any(s.stat().st_size > self.large_file_bytes
                      for s, _ in pairs if s.exists())
        if operation == "move" or zone == "project" or too_big:
            lines = [f"Action: {operation.upper()} {len(pairs)} file(s)",
                     f"Into:   {dest}"]
            for s, d in pairs:
                flag = "   << OVERWRITES an existing file" if d.exists() else ""
                if s.exists() and s.stat().st_size > self.large_file_bytes:
                    flag += f"   << LARGE ({s.stat().st_size // (1024 * 1024)} MB)"
                lines.append(f"  {s}{flag}")
            if operation == "move":
                lines.append("Moving DELETES each source file from its original location.")
            if not self.confirm("\n".join(lines)):
                self.log.log("CONFIRM-NO", f"{operation} {len(pairs)} file(s) -> {dest}")
                raise ConfirmationDeclined(f"Jack declined: {operation} files into {dest}")
            self.log.log("CONFIRM-YES", f"{operation} {len(pairs)} file(s) -> {dest}")

        for s, d in pairs:
            self.log.log("WRITE", f"{operation} {s} -> {d} (zone={zone})")
        return pairs

    def _describe(self, p: Path, mode: str, exists: bool, new_content: str) -> str:
        """Show exactly what will change, per the destructive-action rule."""
        parts = [f"Action: {mode.upper()}", f"Path:   {p}"]
        if exists and p.is_file():
            try:
                current = p.read_text(encoding="utf-8", errors="replace")
                parts.append(f"Current content ({len(current)} chars):\n{_preview(current)}")
            except OSError:
                parts.append("Current content: (unreadable)")
        if mode != "delete" and new_content:
            parts.append(f"New content:\n{_preview(new_content)}")
        return "\n".join(parts)

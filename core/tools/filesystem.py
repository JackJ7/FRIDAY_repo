"""
Filesystem tools: read anywhere (read-only), write only to the outbox.

read_file / list_dir give FRIDAY eyes on the real filesystem so she never has
to guess at file contents. write_to_friday_documents is her one general-purpose
place to produce documents.
"""

from pathlib import Path


def register_filesystem_tools(registry, gate, outbox_root: Path, max_bytes: int):
    outbox_root = Path(outbox_root).resolve()

    def read_file(path: str) -> str:
        p = gate.check_read(path)
        if p.is_dir():
            return f"'{p}' is a folder — use list_dir to see what's inside."
        if not p.exists():
            return f"ERROR: no file at '{p}'"
        data = p.read_bytes()
        text = data[:max_bytes].decode("utf-8", errors="replace")
        if len(data) > max_bytes:
            text += f"\n... [truncated: file is {len(data):,} bytes, showing first {max_bytes:,}]"
        return text

    def list_dir(path: str) -> str:
        p = gate.check_read(path)
        if not p.is_dir():
            return f"ERROR: '{p}' is not a folder."
        lines = []
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        for e in entries[:500]:
            if e.is_dir():
                lines.append(f"{e.name}\\")
            else:
                lines.append(f"{e.name}  ({e.stat().st_size:,} bytes)")
        if len(entries) > 500:
            lines.append(f"... (+{len(entries) - 500} more entries)")
        return "\n".join(lines) if lines else "(empty folder)"

    def write_to_friday_documents(filename: str, content: str, mode: str = "create") -> str:
        target = (outbox_root / filename).resolve()
        if not target.is_relative_to(outbox_root):
            return f"ERROR: '{filename}' escapes friday_documents."
        approved = gate.approve_write(target, mode, new_content=content)
        approved.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append" and approved.exists():
            existing = approved.read_text(encoding="utf-8", errors="replace")
            joiner = "" if existing.endswith("\n") else "\n"
            approved.write_text(existing + joiner + content, encoding="utf-8")
        else:
            approved.write_text(content, encoding="utf-8")
        return f"Wrote {approved.relative_to(outbox_root)} to friday_documents ({mode})."

    registry.register(
        "read_file",
        "Read a text file from anywhere on Jack's filesystem (read-only). "
        "Use this instead of guessing at file contents.",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute Windows path, e.g. C:\\Users\\jacko\\Documents\\notes.txt"}},
            "required": ["path"],
        },
        read_file,
        kind="external_read",  # file content is untrusted — taints the turn
    )
    registry.register(
        "list_dir",
        "List the contents of a folder (read-only).",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute Windows path to a folder"}},
            "required": ["path"],
        },
        list_dir,
    )
    registry.register(
        "write_to_friday_documents",
        "Save a document you produced into the friday_documents outbox. "
        "mode 'create' for a new file, 'append' to add to one, 'overwrite' to "
        "replace one. The outbox is yours — no permission needed.",
        {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "File name (subfolders allowed), e.g. reports\\rov_thruster_tradeoff.md"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["create", "append", "overwrite"]},
            },
            "required": ["filename", "content"],
        },
        write_to_friday_documents,
        kind="action",
    )

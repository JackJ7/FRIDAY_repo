r"""
Artifact perception — upgrade plan Task 6 ("ingest implies comprehend").

The Doc Ock failure started here: an uploaded PDF was routed to storage
without ever passing through anything that could READ it — FRIDAY treated an
artifact as an object to be placed, not perceived, then couldn't discuss it.
This module is the single place that turns a file on disk into something the
model can actually see: extracted text for text-ish files and text-bearing
PDFs, and an EXPLICIT `unread` record for everything else (scanned/image
PDFs, binaries). "Unread" is a first-class honest state — she must say she
hasn't read a thing, never behave as if it doesn't exist (and never pretend
she has read it).
"""

from pathlib import Path

# Extensions we read as plain text. Everything else is binary-until-proven-
# otherwise; PDFs get their own path below.
_TEXTY = {".txt", ".md", ".markdown", ".py", ".c", ".cpp", ".h", ".hpp",
          ".ino", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv",
          ".tsv", ".log", ".xml", ".html", ".htm", ".js", ".ts", ".sh",
          ".ps1", ".bat", ".gitignore", ".sql", ".tex"}


def perceive(path, max_chars: int = 3500) -> dict:
    """Look at one file and return what a comprehension pass can work from.

    -> {"name", "kind", "text" (str|None), "note" (one-line honest status)}
    text is a head-excerpt capped at max_chars; None means UNREAD, and note
    says exactly why — that note is what FRIDAY must relay instead of
    bluffing about content she never saw.
    """
    p = Path(path)
    name = p.name
    if not p.is_file():
        return {"name": name, "kind": "missing", "text": None,
                "note": "file not found on disk"}

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _perceive_pdf(p, max_chars)

    if suffix in _TEXTY:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"name": name, "kind": "unreadable", "text": None,
                    "note": f"could not read: {e}"}
        clipped = text[:max_chars]
        note = (f"text file, {len(text)} chars"
                + (f" (showing first {max_chars})" if len(text) > max_chars
                   else ""))
        return {"name": name, "kind": "text", "text": clipped, "note": note}

    size_kb = p.stat().st_size / 1024
    return {"name": name, "kind": "binary", "text": None,
            "note": (f"UNREAD — binary/{suffix or 'no extension'} file "
                     f"({size_kb:.0f} KB); I have no way to see inside it "
                     f"yet. Say so if asked about its content.")}


def _perceive_pdf(p: Path, max_chars: int) -> dict:
    """Text-bearing PDFs get extracted (pypdf, Jack's C7 ruling); scanned/
    image-only PDFs are honestly UNREAD — there is no vision model in this
    stack, and pretending otherwise is exactly the failure this exists to
    prevent."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"name": p.name, "kind": "pdf", "text": None,
                "note": ("UNREAD — PDF, and the pypdf extractor isn't "
                         "installed (pip install pypdf). Say so if asked "
                         "about its content.")}
    try:
        reader = PdfReader(str(p))
        pages = len(reader.pages)
        chunks, total = [], 0
        for page in reader.pages:
            t = (page.extract_text() or "").strip()
            if t:
                chunks.append(t)
                total += len(t)
            if total >= max_chars:
                break
        text = "\n\n".join(chunks)[:max_chars]
    except Exception as e:  # malformed/encrypted PDFs must not crash a filing
        return {"name": p.name, "kind": "pdf", "text": None,
                "note": f"UNREAD — PDF that failed to parse ({e})."}

    if not text.strip():
        return {"name": p.name, "kind": "pdf", "text": None,
                "note": (f"UNREAD — PDF ({pages} page(s)) with no extractable "
                         f"text: likely scanned images or drawings. I can't "
                         f"see images; say so plainly if asked about its "
                         f"content.")}
    return {"name": p.name, "kind": "pdf", "text": text,
            "note": f"PDF, {pages} page(s), text extracted"}


def comprehension_block(results: list) -> str:
    """Render perceive() results for a tool result — the structural
    guarantee that filing and perceiving cannot be separated: whatever files
    an artifact carries this text with it into the conversation."""
    lines = ["--- COMPREHENSION PASS (you have now seen these; analyze, "
             "don't just file) ---",
             "If Jack asked for analysis/thoughts, give it IN YOUR REPLY, "
             "from this content — do not write it to a note or the outbox "
             "unless he asked for a file."]
    for r in results:
        lines.append(f"[{r['name']}] {r['note']}")
        if r["text"]:
            lines.append(r["text"])
    if any(r["text"] is None for r in results):
        lines.append(
            "NOTE: unread items above are marked UNREAD — if Jack asks about "
            "their content, say you can't read them (and why); never invent "
            "a description.")
    return "\n".join(lines)

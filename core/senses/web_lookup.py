r"""
Reactive web lookup (§6C) — the narrowest sense.

One function: fetch a URL Jack's request pointed at, strip it to readable
text, hand it back as data. The reasoning about it happens in the local
model. There is NO ambient monitoring — nothing here runs on a timer, ever;
the only caller is the fetch_url tool, which only runs inside a reply to
Jack. Fetched text goes through the engine's DATA envelope like every other
tool result (invariant #2).
"""

import re
from html.parser import HTMLParser

import requests

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FRIDAY-local-assistant"}


class _TextExtractor(HTMLParser):
    """Minimal HTML -> text: keeps visible text, drops script/style/nav junk."""
    _SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer"}

    def __init__(self):
        super().__init__()
        self.chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.chunks.append(data.strip())


def fetch_url(url: str, max_bytes: int = 200_000, action_logger=None) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return "ERROR: only http(s) URLs can be fetched."
    try:
        resp = requests.get(url, headers=_UA, timeout=20, stream=True)
        resp.raise_for_status()
        raw = resp.raw.read(max_bytes, decode_content=True)
    except requests.RequestException as e:
        return f"ERROR: fetch failed — {e}"
    if action_logger:
        action_logger.log("SENSE", f"web fetch: {url[:120]} ({len(raw):,} bytes)")

    ctype = resp.headers.get("Content-Type", "")
    text = raw.decode(resp.encoding or "utf-8", errors="replace")
    if "html" in ctype:
        parser = _TextExtractor()
        parser.feed(text)
        text = "\n".join(parser.chunks)
    text = re.sub(r"\n{3,}", "\n\n", text)[:20_000]
    return f"[fetched {url}]\n{text}"

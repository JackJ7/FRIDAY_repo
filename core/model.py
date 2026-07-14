"""
Model layer: a thin client for Ollama's local chat API.

Only this file knows how to talk to Ollama. If the serving stack ever changes
(llama.cpp, vLLM, ...), this is the only file that needs replacing.
"""

import json

import requests


class ModelError(Exception):
    """Raised when Ollama can't be reached or returns an error."""


class ModelReply:
    """What one model call produced: text, any tool calls, and timing stats."""

    def __init__(self):
        self.content = ""        # the assistant's text reply (reasoning stripped)
        self.reasoning = ""      # captured <think> scratchpad when a reasoning
                                 # model is in use and stripping is on. For
                                 # diagnostics/eval ONLY (e.g. measuring
                                 # thinking-token volume): it is NEVER streamed
                                 # to the UI, NEVER part of .content, and MUST
                                 # NEVER be written to a brain note. A think
                                 # trace is discarded scratch reasoning — full
                                 # of abandoned wrong turns — and FRIDAY writes
                                 # conversation text into authoritative notes,
                                 # so a leak would poison a note with hypotheses
                                 # the model itself threw away.
        self.tool_calls = []     # tool invocations the model requested (may be empty)
        self.eval_count = 0      # tokens generated
        self.eval_duration = 0   # nanoseconds spent generating

    @property
    def tokens_per_second(self) -> float:
        if not self.eval_duration:
            return 0.0
        return self.eval_count / (self.eval_duration / 1e9)


def _longest_partial_tag(buffer: str, tag: str) -> int:
    """How many trailing chars of `buffer` could be the START of `tag`.

    Used by the streaming reasoning filter to decide how much text to hold
    back at a chunk boundary. Tags like ``<think>`` routinely arrive split
    across two stream chunks (``<thi`` then ``nk>``); if we emitted the ``<thi``
    immediately we would leak the opening tag character-by-character. So we
    hold back the longest suffix of what we have so far that is a proper prefix
    of the tag, and wait for the next chunk to disambiguate.

    Returns 0 when no suffix of `buffer` begins the tag.
    """
    # A *proper* prefix only (len(tag) - 1 max): a full match is handled by the
    # caller's str.find before this is ever consulted.
    for k in range(min(len(buffer), len(tag) - 1), 0, -1):
        if buffer[-k:] == tag[:k]:
            return k
    return 0


class _ReasoningFilter:
    """Strips a reasoning model's ``<think>…</think>`` block from a token stream.

    Reasoning-distilled models (deep mode's candidate brain — see Phase 6 of
    FRIDAY_notes10_plan.md) emit their chain-of-thought inline, wrapped in
    ``<think>`` tags, before the actual answer. Two hard requirements make a
    naive ``str.replace`` unsafe:

    1. The trace must never reach the UI *or* a brain note (invariant 4 +
       the note-poisoning scar). So we filter the LIVE stream, not just the
       final string — the user must never even glimpse the scratchpad.
    2. Tags split across stream chunks. A per-chunk replace would miss a
       ``<think>`` whose ``<`` and ``think>`` land in different chunks, or
       would dribble a partial tag to the screen.

    So this is a small stateful machine: feed it each streamed piece, it
    returns only the visible (answer) text and siphons the reasoning into
    ``.reasoning``. Fail-closed: if the model opens ``<think>`` and never
    closes it (e.g. generation hit the token budget mid-thought), the
    unterminated remainder is discarded, never emitted — an empty answer is
    honest; a leaked half-thought is not.

    For a non-reasoning model (today's qwen2.5:14b chat brain) that emits no
    tags, this is a transparent pass-through — every char comes out, just
    possibly one chunk later if a chunk happens to end mid-``<``.
    """

    def __init__(self, open_tag: str = "<think>", close_tag: str = "</think>"):
        self.open_tag = open_tag
        self.close_tag = close_tag
        self.reasoning = ""      # accumulated scratchpad (diagnostics only)
        self._in_think = False   # currently inside a think block?
        self._buf = ""           # bytes held back pending a possible split tag

    def feed(self, piece: str) -> str:
        """Consume one streamed piece; return the text safe to show now."""
        self._buf += piece
        visible = []
        while True:
            if not self._in_think:
                # Looking for the start of a reasoning block.
                idx = self._buf.find(self.open_tag)
                if idx != -1:
                    visible.append(self._buf[:idx])
                    self._buf = self._buf[idx + len(self.open_tag):]
                    self._in_think = True
                    continue  # there may be a close tag already in the buffer
                # No full open tag. Emit everything except a trailing fragment
                # that might be the open tag beginning to arrive.
                hold = _longest_partial_tag(self._buf, self.open_tag)
                visible.append(self._buf[:len(self._buf) - hold] if hold else self._buf)
                self._buf = self._buf[len(self._buf) - hold:] if hold else ""
                break
            else:
                # Inside reasoning: siphon to .reasoning until the close tag.
                idx = self._buf.find(self.close_tag)
                if idx != -1:
                    self.reasoning += self._buf[:idx]
                    self._buf = self._buf[idx + len(self.close_tag):]
                    self._in_think = False
                    continue  # answer text may follow in the same buffer
                hold = _longest_partial_tag(self._buf, self.close_tag)
                self.reasoning += self._buf[:len(self._buf) - hold] if hold else self._buf
                self._buf = self._buf[len(self._buf) - hold:] if hold else ""
                break
        return "".join(visible)

    def flush(self) -> str:
        """Call once when the stream ends; return any final visible text.

        Held-back bytes OUTSIDE a think block were a partial open tag that
        never completed — that is real answer text, so emit it. Bytes held
        INSIDE an unterminated think block are discarded (fail-closed).
        """
        if not self._in_think:
            out, self._buf = self._buf, ""
            return out
        self.reasoning += self._buf
        self._buf = ""
        return ""


class OllamaClient:
    def __init__(self, host: str, model: str, num_ctx: int = 8192,
                 temperature: float = 0.4, timeout: int = 600,
                 strip_reasoning: bool = False,
                 think_tags: tuple = ("<think>", "</think>")):
        self.host = host.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.timeout = timeout
        # OFF by default so the resident chat model's stream is untouched
        # (byte-for-byte identical to before this shim existed). Bootstrap
        # flips this on ONLY for the reasoning-distilled deep-mode brain, whose
        # <think> trace must be stripped before it reaches the UI or a note.
        self.strip_reasoning = strip_reasoning
        self.open_tag, self.close_tag = think_tags

    def chat(self, messages: list, tools: list = None, on_token=None,
             format: dict | str = None) -> ModelReply:
        """
        Send the conversation to the model and stream the reply.

        messages : list of {"role": ..., "content": ...} dicts (the whole
                   conversation so far, system prompt included).
        tools    : optional tool definitions (Ollama function-calling format).
        on_token : optional callback fired with each piece of text as it
                   streams in — this is how the CLI prints live output.
        format   : optional constrained-decoding spec (a JSON schema dict, or
                   the string "json"), passed straight to Ollama (armor A1).
                   For INTERNAL structured calls only — the compaction digest,
                   the memory pass's record extraction — where a malformed
                   reply silently degrades quality. The main conversational
                   turn must NEVER pass this: it streams prose and tool calls,
                   and a grammar constraint would strangle both.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"num_ctx": self.num_ctx, "temperature": self.temperature},
        }
        if tools:
            payload["tools"] = tools
        if format:
            payload["format"] = format

        try:
            response = requests.post(
                f"{self.host}/api/chat", json=payload,
                stream=True, timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.ConnectionError:
            raise ModelError(
                "Can't reach Ollama. Is it running? (it starts with Windows, "
                "or run 'ollama serve' in another terminal)"
            )
        except requests.HTTPError as e:
            raise ModelError(f"Ollama returned an error: {e.response.text[:300]}")

        reply = ModelReply()
        # When talking to a reasoning model, run every streamed piece through
        # the filter so the <think> scratchpad is siphoned off before it can
        # reach the on_token callback (the UI) or reply.content (which the
        # memory pass later reads). None → no filtering, original fast path.
        rfilter = _ReasoningFilter(self.open_tag, self.close_tag) \
            if self.strip_reasoning else None

        # Ollama streams one JSON object per line. Text arrives in small pieces;
        # tool calls and timing stats arrive in (usually the final) chunks.
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise ModelError(f"Ollama error: {chunk['error']}")

            message = chunk.get("message", {})
            piece = message.get("content", "")
            if piece:
                visible = rfilter.feed(piece) if rfilter else piece
                if visible:
                    reply.content += visible
                    if on_token:
                        on_token(visible)
            if message.get("tool_calls"):
                reply.tool_calls.extend(message["tool_calls"])

            if chunk.get("done"):
                reply.eval_count = chunk.get("eval_count", 0)
                reply.eval_duration = chunk.get("eval_duration", 0)

        if rfilter:
            # Emit any text held back at the boundary, then keep the captured
            # scratchpad for eval/diagnostics (never for display or notes).
            tail = rfilter.flush()
            if tail:
                reply.content += tail
                if on_token:
                    on_token(tail)
            reply.reasoning = rfilter.reasoning

        return reply

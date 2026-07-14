r"""
FMT — the `format=` constrained-decoding seam (armor A1, §3.1 item 1).

OllamaClient.chat() gained one optional argument at the single seam that
knows Ollama; its first consumers are internal structured calls (the
compaction digest — covered in COMPACT-005 — and the memory pass's record
extraction, covered here). Every test is pure logic: stubs stand in for the
HTTP layer / the model, so the plumbing, validation, and deterministic
fallbacks are proven without a GPU.
"""

import json

import pytest

from core.model import ModelReply, OllamaClient


class _FakeResponse:
    """Minimal stand-in for requests' streaming response: one done-chunk."""

    def __init__(self, content='ok'):
        self._line = json.dumps({"message": {"content": content},
                                 "done": True, "eval_count": 1,
                                 "eval_duration": 1}).encode()

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield self._line


@pytest.mark.case("FMT-001", "OllamaClient.chat() forwards format= to the API payload — and omits it entirely when unused (the default path is byte-identical)")
def test_payload_carries_format(monkeypatch):
    from core import model as model_mod
    captured = {}

    def fake_post(url, json=None, stream=True, timeout=0):
        captured["payload"] = json
        return _FakeResponse()

    monkeypatch.setattr(model_mod.requests, "post", fake_post)
    client = OllamaClient("http://localhost:11434", "test-model")

    schema = {"type": "object", "properties": {"summary": {"type": "string"}},
              "required": ["summary"]}
    client.chat([{"role": "user", "content": "hi"}], format=schema)
    assert captured["payload"]["format"] == schema

    # No format -> the key is ABSENT, not null: the resident chat turn's
    # payload must be unchanged from before this seam existed.
    client.chat([{"role": "user", "content": "hi"}])
    assert "format" not in captured["payload"]


class _StubModel:
    """Scripted single-reply model; records the format= it was handed."""

    def __init__(self, content):
        self.content = content
        self.last_format = None
        self.calls = 0

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.calls += 1
        self.last_format = format
        r = ModelReply()
        r.content = self.content
        r.eval_count = 3
        return r


@pytest.mark.case("FMT-002", "structured memory record: valid JSON is validated + cleaned; garbage, bad types, and junk commitments all degrade to the deterministic floor (None / dropped)")
def test_structured_record_validation(sandbox):
    eng = sandbox.service.engine

    # The happy path: cleaned title, canonical type, bounded commitments.
    eng.model = _StubModel(json.dumps({
        "type": "task",
        "title": "  Order the   GM6208 motors  ",
        "commitments": [
            {"text": "Order the GM6208s", "due": "friday"},
            {"text": "   "},                       # blank text -> dropped
            "not a dict",                          # junk shape -> dropped
            {"text": "extra 1"}, {"text": "extra 2"},  # beyond 3 -> bounded
        ]}))
    rec = eng._structured_memory_record("I need to order the GM6208s",
                                        "Noted.", "")
    assert rec["title"] == "Order the GM6208 motors"
    assert rec["type"] == "task"
    assert [c["text"] for c in rec["commitments"]] == ["Order the GM6208s"]
    assert rec["commitments"][0]["due"] == "friday"
    # The constraint rode on the call: all three fields are REQUIRED.
    assert set(eng.model.last_format["required"]) == \
        {"type", "title", "commitments"}

    # Garbage JSON -> None (callers fall back to the deterministic paths).
    eng.model = _StubModel("not json at all")
    assert eng._structured_memory_record("x", "y", "") is None

    # A non-canonical type is discarded, never stored verbatim from a model.
    eng.model = _StubModel(json.dumps(
        {"type": "session-summary", "title": "t", "commitments": []}))
    rec = eng._structured_memory_record("x", "y", "")
    assert rec["type"] == ""

    # A raising model is best-effort, never fatal.
    class _Boom:
        def chat(self, *a, **kw):
            raise RuntimeError("model down")
    eng.model = _Boom()
    assert eng._structured_memory_record("x", "y", "") is None


@pytest.mark.case("FMT-003", "record_from_pass hints: title upgrades the first-sentence floor; type may only refine the generic 'fact' bucket, never a ledger-derived type")
def test_record_hints(sandbox):
    store = sandbox.service.engine.observations
    generic = [{"tool": "write_brain", "args": {"path": "projects/x.md"}}]
    tracker = [{"tool": "track_commitment", "args": {}}]

    # Generic write + hints -> model title and refined type land.
    oid = store.record_from_pass("we settled on the 6S pack. ok?", "done",
                                 generic, title_hint="Battery: 6S pack chosen",
                                 type_hint="decision")
    obs = store.get(oid)
    assert obs.title == "Battery: 6S pack chosen"
    assert obs.type == "decision"

    # Ledger-derived type is ground truth: a track_commitment turn stays
    # 'task' no matter what the model opined.
    oid = store.record_from_pass("I'll order the pack", "noted", tracker,
                                 type_hint="discovery")
    assert store.get(oid).type == "task"

    # Empty hints -> the deterministic floor exactly as before.
    oid = store.record_from_pass("The buck converter has no fuse. Scary.",
                                 "noted", generic)
    obs = store.get(oid)
    assert obs.title == "The buck converter has no fuse."
    assert obs.type == "fact"


@pytest.mark.case("FMT-004", "intention cue: fires on Jack's first-person stated intentions, never on questions or third-party talk")
def test_intention_cue(sandbox):
    cue = sandbox.service.engine._INTENTION_CUE
    for msg in ("I need to order the GM6208s",
                "I'll email the advisor Friday",
                "tomorrow I'm going to re-flash the ESC",
                "I must submit the form by monday"):
        assert cue.search(msg), msg
    for msg in ("what's the neutral pulse for the ESCs?",
                "did you save that?",
                "Kevin will order the motors",
                "the rig is done"):
        assert not cue.search(msg), msg


class _PassScript:
    """Two-call script for a full memory_pass: the tool loop's reply (plain,
    no tool calls) then the format-constrained extraction reply. Asserting on
    which call carried format= proves the pass stays unconstrained while the
    extraction is grammar-locked."""

    def __init__(self, extraction: dict):
        self.extraction = json.dumps(extraction)
        self.formats = []

    def chat(self, messages, tools=None, on_token=None, format=None):
        self.formats.append(format)
        r = ModelReply()
        r.content = (self.extraction if format is not None
                     else "MEMORY: nothing durable")
        r.eval_count = 3
        return r


@pytest.mark.case("FMT-005", "memory-pass commitment backstop: intention stated + no track_commitment anywhere -> the constrained extraction runs and CODE makes the tracker call (lands Pending) + records the observation")
def test_commitment_backstop(sandbox):
    eng = sandbox.service.engine
    eng.model = _PassScript({
        "type": "task", "title": "Order GM6208 motors",
        "commitments": [{"text": "Order the GM6208s", "due": ""}]})

    eng.memory_pass("I need to order the GM6208s this week",
                    "Noted — want me to track that?")

    # The tool-loop call ran unconstrained; the extraction was grammar-locked.
    assert eng.model.formats[0] is None
    assert eng.model.formats[-1] is not None

    # CODE made the tracker call: the commitment sits in Pending (inferred),
    # so an over-eager catch costs Jack a decline, never a surprise.
    summary = eng.registry.call("list_commitments", {})
    assert "GM6208" in summary, summary
    assert "pending" in summary.lower() or "confirm" in summary.lower()

    # And the observation floor recorded the turn with the authored title.
    recent = eng.observations.recent(1)
    assert recent and recent[0].title == "Order GM6208 motors"
    assert recent[0].type == "task"


@pytest.mark.case("FMT-006", "memory-pass gating: a pure question with no intention cue and no writes spends ZERO extraction calls")
def test_extraction_gated(sandbox):
    eng = sandbox.service.engine
    eng.model = _PassScript({"type": "fact", "title": "t", "commitments": []})

    eng.memory_pass("what's the pressure rating on the beta probe housing?",
                    "30 bar, per your notes.")
    # Only the tool-loop call ran — no format-constrained call was spent.
    assert eng.model.formats == [None]
    # Nothing recorded, nothing tracked.
    assert eng.observations.recent(1) == []
    assert "GM6208" not in eng.registry.call("list_commitments", {})

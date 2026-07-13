r"""VIDEO — the /watch pipeline (coherence plan Phase 4 / D5, activated Phase 6).

Two layers, both here:
  * PURE-CODE (always run): the four tools register as `external_read` (media is
    DATA -> taint), the caption parser is exact and never fabricates (empty in
    -> empty out), and every tool degrades HONESTLY when its dep is missing —
    it reports unavailability and NEVER invents a transcript/frame description.
  * LIVE (opt-in, skipped unless the real deps are present): a tiny generated
    clip is pushed through ffmpeg keyframe extraction end-to-end. The heavy
    model paths (Whisper weights, the VL model) are not asserted in CI — they
    pull large weights on first use — but the wiring is exercised by hand and
    covered by the honest-degradation tests below.
"""

import shutil

import pytest

from core.model import ModelError
import core.tools.video_tools as vt
from core.tools.video_tools import (
    register_video_tools, _parse_captions, _format_segments, _fmt_ts,
)
from core.tools.registry import ToolRegistry


class _Gate:
    """Minimal stand-in — the tools don't touch the gate directly."""
    class _Log:
        def log(self, *a):
            pass
    log = _Log()


def _registry(tmp_path):
    reg = ToolRegistry()
    register_video_tools(reg, _Gate(), tmp_path / "out", tmp_path / "cache",
                         max_minutes=90, host="http://localhost:11434",
                         vl_model="qwen2.5vl:latest", whisper_model="tiny")
    return reg


# ---------------------------------------------------------------------------
# Registration + trust boundary
# ---------------------------------------------------------------------------

@pytest.mark.case("VID-001", "all four /watch tools register as external_read (media is DATA -> taint)")
def test_tools_register_tainting(tmp_path):
    reg = _registry(tmp_path)
    for name in ("download_video", "extract_transcript", "extract_keyframes",
                 "describe_frames"):
        assert reg.kind(name) == "external_read", name


# ---------------------------------------------------------------------------
# Pure caption-parsing logic — deterministic, no deps, proves no fabrication
# ---------------------------------------------------------------------------

@pytest.mark.case("VID-004", "caption parser extracts timed cues, strips tags, dedups rolling lines")
def test_parse_captions_exact():
    vtt = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "<00:00:01.000><c>Hello</c> there\n\n"
        "00:00:03.000 --> 00:00:05.000\n"
        "Hello there\n\n"            # duplicate of previous cue -> collapsed
        "00:01:07.000 --> 00:01:09.000\n"
        "second point\n"
    )
    segs = _parse_captions(vtt)
    assert segs == [(1.0, "Hello there"), (67.0, "second point")]
    # And it renders with mm:ss timestamps.
    assert _format_segments(segs) == "[00:01] Hello there\n[01:07] second point"


@pytest.mark.case("VID-005", "caption parser returns EMPTY for junk — never invents a transcript")
def test_parse_captions_empty_on_junk():
    assert _parse_captions("") == []
    assert _parse_captions("not a caption file at all\nrandom text") == []


def test_fmt_ts_hours():
    assert _fmt_ts(5) == "00:05"
    assert _fmt_ts(65) == "01:05"
    assert _fmt_ts(3725) == "1:02:05"


# ---------------------------------------------------------------------------
# Honest degradation — a MISSING dep reports unavailability, never fabricates
# ---------------------------------------------------------------------------

@pytest.mark.case("VID-002", "frame description degrades honestly to LOCAL-only when the vision model is unreachable")
def test_describe_frames_honest(tmp_path, monkeypatch):
    reg = _registry(tmp_path)
    # A frame exists, but the local VL model can't be reached -> honest fallback.
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "frame_001.jpg").write_bytes(b"\xff\xd8\xff\xd9")  # minimal JPEG-ish

    def _boom(self, *a, **k):
        raise ModelError("not served")
    monkeypatch.setattr("core.tools.video_tools.OllamaClient.chat", _boom)

    out = reg.call("describe_frames", {"frames_dir": str(frames)}).lower()
    assert "qwen2.5vl" in out or "local" in out       # stays local
    assert "invariant 1" in out or "never a cloud" in out
    assert "isn't reachable" in out or "not reporting" in out  # honest, no invention


@pytest.mark.case("VID-006", "transcript degrades honestly when neither yt-dlp nor Whisper is present")
def test_transcript_honest_without_deps(tmp_path, monkeypatch):
    reg = _registry(tmp_path)
    monkeypatch.setattr(vt, "_have_cli", lambda name: False)
    monkeypatch.setattr(vt, "_have_module", lambda name: False)
    out = reg.call("extract_transcript", {"path_or_url": "cache/x.mp4"}).lower()
    assert "not available" in out
    assert "will not invent" in out or "won't invent" in out or "invent the result" in out


@pytest.mark.case("VID-007", "keyframes degrade honestly when ffmpeg is absent")
def test_keyframes_honest_without_ffmpeg(tmp_path, monkeypatch):
    reg = _registry(tmp_path)
    monkeypatch.setattr(vt, "_have_cli", lambda name: False)
    out = reg.call("extract_keyframes", {"path": "cache/x.mp4"}).lower()
    assert "not available" in out and "ffmpeg" in out


@pytest.mark.case("VID-003", "no tool fabricates or crashes on bad/missing input")
def test_no_fabrication(tmp_path, monkeypatch):
    reg = _registry(tmp_path)
    # Force every dependency absent so we exercise the degradation paths only.
    monkeypatch.setattr(vt, "_have_cli", lambda name: False)
    monkeypatch.setattr(vt, "_have_module", lambda name: False)
    calls = {
        "download_video": {"url": "https://example.com/v"},
        "extract_transcript": {"path_or_url": "cache/x.mp4"},
        "extract_keyframes": {"path": "cache/x.mp4"},
        "describe_frames": {"frames_dir": "cache/frames"},
    }
    for name, args in calls.items():
        out = reg.call(name, args)
        assert isinstance(out, str) and out.strip(), name
        low = out.lower()
        assert ("not available" in low or "no frames found" in low
                or "error" in low), f"{name} un-honest: {out[:120]}"


# ---------------------------------------------------------------------------
# LIVE end-to-end — real ffmpeg on a tiny generated clip. Skipped in CI.
# ---------------------------------------------------------------------------

@pytest.mark.case("VID-008", "LIVE: real ffmpeg extracts keyframes from a generated clip")
@pytest.mark.skipif(shutil.which("ffmpeg") is None,
                    reason="ffmpeg not on PATH — live keyframe test skipped")
def test_live_keyframes(tmp_path):
    import subprocess
    clip = tmp_path / "clip.mp4"
    # Two visually distinct 1s segments so a scene change exists to detect.
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
         "-f", "lavfi", "-i", "color=c=blue:duration=1:size=320x240:rate=10",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]",
         str(clip)],
        capture_output=True, text=True, timeout=120)
    assert clip.exists(), "ffmpeg failed to build the fixture clip"
    reg = _registry(tmp_path)
    out = reg.call("extract_keyframes", {"path": str(clip), "max_frames": 4})
    assert "Extracted" in out and "keyframe" in out
    frames = list((tmp_path / "cache").glob("clip_frames/frame_*.jpg"))
    assert frames, "no keyframe files were written"

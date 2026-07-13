r"""RESEARCH — the autonomous GPU research loop (autoresearch port). All
pure-code: no model, no GPU, no network, so these run in --quick.

The design mirrors git_write: a pure-function DENY-LAYER (evaluate_launch) that
denies BEFORE any confirm card, plus deterministic log parsing / ledger
formatting that the keep/discard decision is scored on. The heavy background
loop needs a real GPU + clone and is exercised by Jack's manual smoke test, not
here — but everything that gates or scores it is unit-tested below.
"""

import pytest

from core.tools.research_tools import (
    ResearchDecision, ResearchOp, ResearchPolicy, evaluate_launch,
    format_results_row, parse_metrics, _normalize_repo, _repo_on_allowlist,
)

_REPO = "https://github.com/karpathy/autoresearch"


def _policy(**kw):
    base = dict(allowed_repos=[_REPO], max_budget_hours=8,
                max_iters_per_run=200, train_window_minutes=5,
                iter_timeout_minutes=10, max_crash_retries=3)
    base.update(kw)
    return ResearchPolicy(**base)


def _ok_op(**kw):
    """A fully-satisfiable op; individual tests break ONE precondition."""
    base = dict(repo=_REPO, tag="run1", git_ok=True, uv_ok=True, gpu_ok=True,
                tag_in_use=False, other_run_active=False)
    base.update(kw)
    return ResearchOp(**base)


# ======================================================================
# The deny-layer as pure functions (the chokepoint every launch passes).
# ======================================================================

@pytest.mark.case("RES-001", "an allowlisted repo with everything present is allowed")
def test_allowed_when_all_ok():
    d = evaluate_launch(_ok_op(), _policy())
    assert d.allowed and d.budget_hours == 8 and d.max_iters == 200


@pytest.mark.case("RES-002", "a repo not on the research allowlist is denied")
def test_off_allowlist_denied():
    d = evaluate_launch(_ok_op(repo="https://github.com/someone/else"), _policy())
    assert not d.allowed and "allowlist" in d.reason


@pytest.mark.case("RES-003", "missing git / uv / GPU each deny with a clear reason")
def test_missing_tooling_denied():
    assert not evaluate_launch(_ok_op(git_ok=False), _policy()).allowed
    assert "git" in evaluate_launch(_ok_op(git_ok=False), _policy()).reason
    assert "uv" in evaluate_launch(_ok_op(uv_ok=False), _policy()).reason
    assert "GPU" in evaluate_launch(_ok_op(gpu_ok=False), _policy()).reason


@pytest.mark.case("RES-004", "a second run is denied while one is already active")
def test_concurrent_run_denied():
    d = evaluate_launch(_ok_op(other_run_active=True), _policy())
    assert not d.allowed and "one run at a time" in d.reason


@pytest.mark.case("RES-005", "a reused tag is denied (no merge into existing history)")
def test_reused_tag_denied():
    d = evaluate_launch(_ok_op(tag_in_use=True), _policy())
    assert not d.allowed and "already has a run" in d.reason


@pytest.mark.case("RES-006", "an empty tag is denied")
def test_empty_tag_denied():
    assert not evaluate_launch(_ok_op(tag=""), _policy()).allowed


@pytest.mark.case("RES-007", "requested budget/iters are clamped DOWN to Jack's ceilings")
def test_budget_clamped_to_ceiling():
    # Ask for far more than the ceiling — it's capped, never granted upward.
    d = evaluate_launch(_ok_op(requested_budget_hours=100,
                               requested_max_iters=99999), _policy())
    assert d.allowed and d.budget_hours == 8 and d.max_iters == 200
    # A smaller-than-ceiling request is honoured as-is.
    d2 = evaluate_launch(_ok_op(requested_budget_hours=2,
                                requested_max_iters=10), _policy())
    assert d2.budget_hours == 2 and d2.max_iters == 10


@pytest.mark.case("RES-008", "empty allowlist => nothing runnable even when tooling is present")
def test_empty_allowlist_blocks_everything():
    d = evaluate_launch(_ok_op(), _policy(allowed_repos=[]))
    assert not d.allowed and "allowlist" in d.reason


# ======================================================================
# Repo allowlist — URL-normalised identity, NOT filesystem containment.
# ======================================================================

@pytest.mark.case("RES-009", "repo URLs match the allowlist across spelling variants")
def test_url_normalization_matches():
    allow = ["https://github.com/karpathy/autoresearch"]
    for variant in (
        "https://github.com/karpathy/autoresearch",
        "https://github.com/karpathy/autoresearch.git",
        "http://github.com/karpathy/autoresearch/",
        "git@github.com:karpathy/autoresearch.git",
        "GitHub.com/Karpathy/AutoResearch",
    ):
        assert _repo_on_allowlist(variant, allow), variant
    # A different repo does NOT match.
    assert not _repo_on_allowlist(
        "https://github.com/karpathy/nanochat", allow)


@pytest.mark.case("RES-010", "URL normalization strips scheme, .git, trailing slash, case")
def test_normalize_repo_forms():
    canon = "github.com/karpathy/autoresearch"
    assert _normalize_repo("https://github.com/karpathy/autoresearch.git") == canon
    assert _normalize_repo("git@github.com:karpathy/autoresearch") == canon


# ======================================================================
# Deterministic log parsing — the keep/discard decision is scored on THIS.
# ======================================================================

@pytest.mark.case("RES-011", "a clean log yields val_bpb (and peak VRAM when present)")
def test_parse_success():
    log = "epoch 3 done\nval_bpb: 1.2345\npeak_vram_mb: 8192\nbye\n"
    m = parse_metrics(log)
    assert m["ok"] and abs(m["val_bpb"] - 1.2345) < 1e-9
    assert m["peak_vram_mb"] == 8192


@pytest.mark.case("RES-012", "a crash / OOM log (no val_bpb line) parses as not-ok")
def test_parse_crash_and_oom():
    assert not parse_metrics("Traceback...\nRuntimeError: boom\n")["ok"]
    assert not parse_metrics("torch.OutOfMemoryError: CUDA out of memory\n")["ok"]
    assert not parse_metrics("")["ok"]


@pytest.mark.case("RES-013", "val_bpb present without a VRAM line still scores")
def test_parse_success_no_vram():
    m = parse_metrics("val_bpb: 0.9\n")
    assert m["ok"] and m["val_bpb"] == 0.9 and m["peak_vram_mb"] is None


# ======================================================================
# Ledger row formatting — tab-separated, and injection-safe (a planted
# newline in the model's description can't forge extra ledger rows).
# ======================================================================

@pytest.mark.case("RES-014", "a results.tsv row is tab-separated with the right columns")
def test_row_format():
    row = format_results_row("abc123", 1.5, 8192, "keep", "new best")
    cols = row.split("\t")
    assert cols[0] == "abc123" and cols[1] == "1.5000"
    assert cols[2] == "8.00" and cols[3] == "keep" and cols[4] == "new best"


@pytest.mark.case("RES-015", "newlines/tabs in the description are flattened (no row forgery)")
def test_row_description_sanitised():
    row = format_results_row("c", None, None, "crash",
                             "boom\nval_bpb: 0.0001\tstatus\tkeep")
    assert "\n" not in row  # the row itself is one line
    # The empty metric columns render as empty cells, not fabricated numbers.
    assert row.split("\t")[1] == "" and row.split("\t")[2] == ""

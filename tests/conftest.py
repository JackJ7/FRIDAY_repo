r"""
Suite plumbing: fixtures + the report plugin.

Every test carries  @case("AREA-###", "what it verifies")  — the report is
keyed by those IDs (requirement D). Results stream into
<results>\report.json after EVERY test (an interrupted overnight run still
leaves a readable partial report) and a self-contained report.html is
rendered at session end.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
FRIDAY_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(FRIDAY_ROOT))

from helpers.harness import SandboxFriday  # noqa: E402
from helpers.taxonomy import SKILLS, skill_tag_errors  # noqa: E402

# ---------- markers ----------

def pytest_addoption(parser):
    parser.addoption(
        "--skill", action="store", default=None,
        help="run only cases tagged @pytest.mark.skill(<name>) — the armor "
             "plan's per-skill re-run tier (run_suite.py --skill <tag>)")


def pytest_configure(config):
    config.addinivalue_line("markers", "case(id, desc): stable case ID + description")
    config.addinivalue_line("markers", "model: needs the live local LLM (slow)")
    config.addinivalue_line(
        "markers",
        "skill(name, ...): scorecard skill tag(s) from helpers/taxonomy.py — "
        "REQUIRED on every model-marked case (collection fails otherwise)")
    config.addinivalue_line(
        "markers",
        "upgrade: upgrade-plan feature test — excluded from the fine-tune "
        "A/B yardstick (eval_compare runs 'model and not upgrade') so new "
        "feature tests can't churn model comparisons")
    _Report.instance = _Report()


def _item_skills(item):
    """All skill names on an item (a case may legitimately carry two)."""
    names = []
    for m in item.iter_markers("skill"):
        names.extend(m.args)
    return names


@pytest.hookimpl(tryfirst=True)  # before pytest's own -m deselection, so the
def pytest_collection_modifyitems(config, items):  # totality check sees ALL cases
    errors = skill_tag_errors(
        (item.nodeid, item.get_closest_marker("model") is not None,
         _item_skills(item)) for item in items)
    if errors:
        raise pytest.UsageError(
            "skill-tag taxonomy violated (armor plan §4.1):\n  "
            + "\n  ".join(errors))
    wanted = config.getoption("--skill")
    if wanted:
        if wanted not in SKILLS:
            raise pytest.UsageError(
                f"--skill {wanted!r} is not in the taxonomy: "
                + ", ".join(sorted(SKILLS)))
        keep = [i for i in items if wanted in _item_skills(i)]
        dropped = [i for i in items if wanted not in _item_skills(i)]
        if dropped:
            config.hook.pytest_deselected(items=dropped)
            items[:] = keep


# ---------- fixtures ----------

@pytest.fixture
def sandbox(tmp_path):
    """A fresh, isolated FRIDAY per test. The real brain is never touched."""
    return SandboxFriday(tmp_path)


@pytest.fixture(scope="module")
def msandbox(tmp_path_factory):
    """Module-shared sandbox for read-only model tests (saves rebuild time).
    Tests that MUTATE state must use `sandbox` instead."""
    return SandboxFriday(tmp_path_factory.mktemp("friday"))


@pytest.fixture
def detail(request):
    """Dict a test fills with evidence (prompt, reply, tool trace, runs) —
    lands verbatim in the report for the morning fix loop."""
    d = {}
    request.node._friday_detail = d
    return d


@pytest.fixture(scope="session")
def sandbox_session(tmp_path_factory):
    """One sandbox reused across every Hypothesis example in a property
    (rebuilding per example would be prohibitive). Properties are read-only
    reasoning Q&A, so sharing is safe."""
    return SandboxFriday(tmp_path_factory.mktemp("friday_prop"))


class _PropDetail:
    """Collects Hypothesis failing examples for the report. Hypothesis shrinks
    to a minimal example, which is the last one recorded here."""
    def __init__(self):
        self.failures = []

    def fail(self, **kw):
        self.failures.append(kw)


@pytest.fixture
def prop_detail(request):
    pd = _PropDetail()
    d = getattr(request.node, "_friday_detail", None)
    if d is None:
        d = {}
        request.node._friday_detail = d
    d["property_failures"] = pd.failures  # shared list; filled as Hypothesis runs
    return pd


# ---------- the report ----------

class _Report:
    instance = None

    def __init__(self):
        out = os.environ.get("FRIDAY_RESULTS_DIR")
        if not out:
            out = FRIDAY_ROOT / "results" / datetime.now().strftime("%Y-%m-%d_%H%M")
        self.dir = Path(out)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cases = {}
        self.meta = {
            "started": datetime.now().isoformat(timespec="seconds"),
            "runs_per_behavior": os.environ.get("FRIDAY_TEST_RUNS", "5"),
            "examples_per_property": os.environ.get("FRIDAY_TEST_EXAMPLES", "100"),
            "argv": " ".join(sys.argv),
        }
        try:
            from core.bootstrap import load_config
            from core.version import __version__
            cfg = load_config()
            self.meta["friday_version"] = __version__
            # FRIDAY_MODEL (set by eval_compare.py) overrides the served tag, so
            # prefer it here to keep the report's model field honest.
            self.meta["model"] = os.environ.get("FRIDAY_MODEL") or cfg["model"]["name"]
        except Exception:
            pass

    def record(self, item, rep):
        # Parametrized tests may add a per-parameter @case marker at runtime;
        # take the most specific (last-added) one so golden IDs come through.
        markers = list(item.iter_markers("case"))
        marker = markers[0] if markers else None  # iter_markers yields last-added first
        cid = marker.args[0] if marker else item.nodeid
        desc = marker.args[1] if marker and len(marker.args) > 1 else ""
        # Parametrized cases must NOT share a report entry: the overnight run
        # showed INJ-003[note]'s failing evidence overwritten by a later
        # passing param. Suffix the param id unless it's already in the case id
        # (golden problems stamp their own unique ids).
        callspec = getattr(item, "callspec", None)
        if callspec is not None and callspec.id not in cid:
            cid = f"{cid}[{callspec.id}]"
        entry = self.cases.get(cid, {"id": cid, "desc": desc, "file": str(item.fspath)})
        entry["skills"] = _item_skills(item)   # scorecard rollup key (§4.2)
        entry["outcome"] = rep.outcome.upper()
        if rep.outcome == "skipped" and rep.longrepr:
            entry["skip_reason"] = str(rep.longrepr)[-300:]
        entry["duration_s"] = round(rep.duration, 1)
        if rep.failed:
            entry["failure"] = str(rep.longrepr)[-4000:]
        d = getattr(item, "_friday_detail", None)
        if d:
            entry["evidence"] = d
            if d.get("flaky"):
                entry["outcome"] = "FLAKY-FAIL" if rep.failed else "FLAKY-PASS"
        self.cases[cid] = entry
        self.write_json()

    def write_json(self):
        payload = {"meta": self.meta, "summary": self.summary(),
                   "cases": list(self.cases.values())}
        (self.dir / "report.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    def summary(self):
        out = {"total": len(self.cases)}
        for e in self.cases.values():
            key = e["outcome"].lower()
            out[key] = out.get(key, 0) + 1
        return out

    def write_html(self):
        s = self.summary()
        rows = []
        color = {"PASSED": "#2f9e6e", "FAILED": "#d64545", "SKIPPED": "#8a97ab",
                 "FLAKY-PASS": "#d69a2f", "FLAKY-FAIL": "#d64545"}
        for e in sorted(self.cases.values(), key=lambda x: x["id"]):
            evid = ""
            if e.get("evidence"):
                evid = ("<details><summary>evidence</summary><pre>" +
                        _esc(json.dumps(e["evidence"], indent=1, ensure_ascii=False)[:6000])
                        + "</pre></details>")
            fail = ""
            if e.get("failure"):
                fail = ("<details open><summary>failure</summary><pre>" +
                        _esc(e["failure"]) + "</pre></details>")
            rows.append(
                f"<tr><td><code>{_esc(e['id'])}</code></td>"
                f"<td style='color:{color.get(e['outcome'], '#000')};font-weight:600'>"
                f"{e['outcome']}</td><td>{_esc(e.get('desc', ''))}"
                f"{fail}{evid}</td><td>{e.get('duration_s', '')}s</td></tr>")
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>FRIDAY regression report</title><style>
body{{font-family:Segoe UI,sans-serif;margin:24px;max-width:1100px}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:6px 9px;font-size:13px;vertical-align:top;text-align:left}}
pre{{white-space:pre-wrap;background:#f5f5f5;padding:8px;font-size:11.5px;max-height:400px;overflow:auto}}
.sum{{font-size:15px;margin:12px 0}} code{{font-size:12px}}
</style></head><body>
<h1>FRIDAY regression report</h1>
<p>{_esc(self.meta.get('started', ''))} — FRIDAY v{_esc(str(self.meta.get('friday_version', '?')))}
 — model {_esc(str(self.meta.get('model', '?')))} — N={_esc(str(self.meta.get('runs_per_behavior')))}
 — examples/property={_esc(str(self.meta.get('examples_per_property')))}</p>
<p class="sum"><b>{s.get('total', 0)}</b> cases —
 <span style="color:#2f9e6e">{s.get('passed', 0)} passed</span> ·
 <span style="color:#d64545">{s.get('failed', 0) + s.get('flaky-fail', 0)} failed</span> ·
 <span style="color:#d69a2f">{s.get('flaky-pass', 0)} flaky-pass</span> ·
 <span style="color:#8a97ab">{s.get('skipped', 0)} skipped</span></p>
<table><tr><th>ID</th><th>Result</th><th>Description / detail</th><th>t</th></tr>
{''.join(rows)}</table></body></html>"""
        (self.dir / "report.html").write_text(html, encoding="utf-8")


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        _Report.instance.record(item, rep)


def pytest_sessionfinish(session, exitstatus):
    r = _Report.instance
    if r:
        r.meta["finished"] = datetime.now().isoformat(timespec="seconds")
        r.write_json()
        r.write_html()
        print(f"\n[FRIDAY suite] report: {r.dir}\\report.html")
        if r.cases:  # collect-only / empty sessions leave no scorecard
            _write_scorecard(r)


def _write_scorecard(r):
    """scorecard.json beside the report + one appended ledger line — the
    longitudinal record that makes 'did a tweak six weeks ago silently
    regress email_triage' a grep, not an archaeology dig (§4.2)."""
    from helpers.scorecard import provenance, rollup
    card = {
        "stamp": r.dir.name,
        "started": r.meta.get("started"),
        "finished": r.meta.get("finished"),
        "provenance": provenance(),
        "totals": r.summary(),
        "skills": rollup(r.cases.values()),
    }
    (r.dir / "scorecard.json").write_text(
        json.dumps(card, indent=1, ensure_ascii=False), encoding="utf-8")
    ledger_line = dict(card)
    ledger_line["skills"] = {name: s["pass_rate"]
                             for name, s in card["skills"].items()}
    with (r.dir.parent / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(ledger_line, ensure_ascii=False) + "\n")
    print(f"[FRIDAY suite] scorecard: {r.dir}\\scorecard.json")

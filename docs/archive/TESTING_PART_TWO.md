# TESTING — PART TWO (deferred plans for the overnight suite)

Parked here per Jack, 2026-07-07, after the fix loop closed out all tiers.
We work through this later; nothing in this file is in flight.

## 1. Fresh overnight full run (the outstanding recommendation)

Everything from the fix loop is verified piecewise, but the tiers were fixed
in batches — a full end-to-end run on one build is the real confirmation.

- Command (from repo root, overnight):
  `FRIDAY_TEST_RUNS=5 python -m pytest tests/ -v --tb=line`
  with `FRIDAY_RESULTS_DIR` pointed somewhere durable (e.g. `results\<date>`).
- Expected: 124 cases green (68 code-only + model cases). Known-flaky watchlist
  from the fix loop — none expected to fail, but if any does, these have history:
  - COM-001 (commitment inference — now backstopped by the memory pass)
  - PLB-004 (playbook following — now full-steps injection)
  - EML-004 / EML-005 (email verdicts — now deterministic importance hints)
- Read `report.json`, triage any failure by the fix-loop discipline
  (root-cause, never weaken a test, deterministic code over prompt patching).

## 2. Gaps worth adding after the overnight run passes

- **Calendar correctness cases** — the tz bug (task 1 of 2026-07-07) proved the
  calendar tests never validated TIMES. Regression tests land with that fix;
  after it, consider a property: random known-time events → reported time
  always matches machine-local wall clock.
- **N-run stability audit**: cases graded at N=5 with ~3/5 historical rates
  (EML-005 pre-fix style misses) deserve an occasional N=8+ soak to separate
  "fixed" from "lucky". Candidates: COM-001, PLB-004, EML-005.
- **Interaction-log schema check**: assert the JSONL schema of
  `logs\interactions\` stays stable across a full suite run (it is the future
  fine-tuning set; a schema drift should fail loudly).
- **Growth-persistence tests** (task 2 of 2026-07-07) and **skills-methodology
  properties** (task 3) join the permanent suite as they land — fold them into
  the overnight run once merged.

## 3. Standing conventions (so a future session reruns this correctly)

- N via `FRIDAY_TEST_RUNS` (default 5), examples via `FRIDAY_TEST_EXAMPLES`
  (default 100), output via `FRIDAY_RESULTS_DIR`.
- Model cases marked `@pytest.mark.model`; `-m "not model"` is the fast
  code-only gate (should stay 100% green at all times).
- Every model case must use a fresh conversation per run/example
  (`fresh_conversation()` / `sandbox=` on `repeat_behavior`) — shared histories
  manufacture flaky failures (the systemic bug found in the fix loop).
- Graders must be model-independent: deterministic extraction + pure-Python
  truth; validate a grader offline against captured replies before burning a
  model run.

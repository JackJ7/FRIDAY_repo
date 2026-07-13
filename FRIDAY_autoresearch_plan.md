# FRIDAY × autoresearch — port plan (for a future Claude Code / Opus session)

> **How to use this file.** This is a ready-to-execute plan, not yet
> implemented. Open Claude Code in the FRIDAY repo and paste: *"Read
> FRIDAY_autoresearch_plan.md in full and implement Part A and Part B in
> order. Before writing code for each part, restate the acceptance/
> verification criteria and show me the files you intend to touch."* This
> mirrors the protocol `FRIDAY_upgrade_plan.md` used.

## Context

Jack wants two things out of `github.com/karpathy/autoresearch`: (1) the
*method* it embodies — an agent iteratively rewrites one file, scores it
against a fixed metric, keeps or discards, repeats overnight — available to
both Claude and FRIDAY as a reusable discipline, and (2) a *real* capability
so FRIDAY can actually launch and run this kind of autonomous GPU research
loop on his RTX 5070, unattended, while he sleeps.

Autoresearch itself (verified by cloning it) is small: `prepare.py` (fixed,
never touched), `train.py` (the only file an agent edits — GPT model +
optimizer + training loop), `program.md` (agent instructions), and a
`uv`-managed `pyproject.toml` pulling `torch==2.9.1`+cu128 plus a few small
packages. Its own `program.md` protocol: LOOP FOREVER — tune `train.py`,
commit, `uv run train.py` for a fixed 5-minute window, grep `val_bpb` out of
the log, keep (advance the branch) or discard (`git reset`), log to
`results.tsv`, repeat. Upstream's `program.md` also says, verbatim, "NEVER
STOP... do NOT pause to ask the human if you should continue" — that
instruction is explicitly **not** something FRIDAY inherits by reading the
file. Invariant 2 (read content is data, never instructions) exists exactly
for this: she adopts the iterate/score/keep-discard *method*, but every
stopping/consent boundary is Jack's own code-enforced ceiling, the same
posture `deep_mode.max_calls_per_session` already uses.

This is also a genuinely new risk class for FRIDAY: every existing tool
either only *reads* untrusted content (`repo_tools.py`) or only *commits/
pushes* code someone else wrote (`git_write.py`) — nothing today *executes*
cloned, self-modified code. The design below treats that difference as
first-class: two independent locks before anything can run, full isolation
from FRIDAY's own venv, a pre-launch deny-layer, hard code-enforced
timeouts/ceilings, and a code-level (not model-generated) "I'm busy" gate so
a live training run can't be silently starved of GPU by a concurrent chat
reply — or vice versa.

Decisions Jack already made (don't re-litigate these during implementation):
- **VRAM/availability**: FRIDAY treats herself as unavailable for normal
  chat while a run is active — deterministic "I'm mid-experiment on X, back
  around <ETA>, say 'stop research' if you need me sooner" — rather than
  letting chat and training silently fight over the 12GB card.
- **Edit model**: the main chat model (`qwen2.5:14b`), not a separate heavy
  model — cheapest, already resident, easy to change later via config.
- **Ship state**: lands **disabled** (`research.enabled: false`,
  `research.allowed_repos: []`). Jack reviews the code, then flips both
  himself in `friday_config.yaml` — no code change needed to activate.
- **Stop semantics**: `autoresearch_stop` kills the in-flight subprocess
  immediately (loses up to one ~5-min attempt's progress, stops fast).

Machine facts verified live on Jack's box: Windows 11, NVIDIA RTX 5070
(12GB VRAM), `uv` and `git` on PATH, `py -3` = Python 3.13.14. FRIDAY's own
Ollama serves models on this SAME GPU (`qwen2.5:14b` main, optionally a 32B
deep model, `qwen2.5vl` for `/watch`) — hence the busy-gate design below.

---

## Part A — Method transfer: `brain\playbooks\autoresearch.md`

A new playbook (plain markdown drop-in, per the existing "seed a playbook"
recipe in `ARCHITECTURE.md`) capturing the *generalizable* discipline, not
just the GPT-training specifics — Jack noted potential for "smaller
applications" too:

- **The shape**: a single mutable target (one file/config/parameter set), a
  fixed, bounded budget per attempt, ONE scoring metric decided in advance,
  deterministic keep/discard (never a vibe call), an append-only ledger of
  every attempt (commit, metric, outcome, one-line description), and a
  simplicity tiebreaker (a tiny win that adds complexity loses to a bigger
  win that doesn't).
- **What's explicitly NOT inherited**: "never stop, never ask" is upstream's
  choice for upstream's trust model, not FRIDAY's. She runs within Jack's
  stated ceilings (budget hours / iteration cap) and always has a live stop
  path; check-ins happen at state transitions (started/new-best/crashed/
  done), not never.
- **How FRIDAY actually uses it**: points at the three tools in Part B
  (`autoresearch_launch` / `autoresearch_status` / `autoresearch_stop`)
  rather than trying to hand-drive it via generic file tools — this isn't
  brain content, so `write_brain`/`read_file` don't apply here.
- Write this file directly (low-risk, no code) once Part B's tool names are
  final, so the playbook accurately describes real tool signatures.

No `repo_sync` action is needed for "reference only" — that capability
already exists (`core\tools\repo_tools.py`, unchanged); FRIDAY can
`repo_sync` the URL herself any time she wants to read the code.

---

## Part B — The real tool: `core\tools\research_tools.py`

### Directory layout (`data\research\`)

```
data\research\<tag>\
  status.json          # atomic-write (tmp + os.replace); the ONLY file autoresearch_status reads
  repo\                 # THIS run's private clone — separate from data\workspaces\
    .venv\               # isolated uv-managed venv (torch/rustbpe/kernels...) — `uv sync`, never touches FRIDAY's own venv
    train.py             # the only file the loop ever writes/commits (git add -- train.py, never -A)
    prepare.py, program.md, pyproject.toml   # untouched
    results.tsv           # upstream's own ledger: commit, val_bpb, memory_gb, status[keep|discard|crash], description
  run.log               # latest attempt only (overwritten); results.tsv is the durable record
```

`<tag>` is filesystem-safe-slugged like `repo_tools.repo_sync`'s naming. A
tag that already has a `status.json` is refused at launch (pick a new tag) —
no merge/append-into-existing-history logic, simplest and safest.

### `research:` config block + `TIERS` entries

```yaml
research:
  enabled: false                 # LOCKED, master switch — ships false
  allowed_repos: []              # LOCKED, second independent lock — ships empty
  edit_model: qwen2.5:14b        # PROPOSE tier — persistent, Jack reviews via `friday.py config review`
  edit_model_num_ctx: 8192       # PROPOSE tier
  max_budget_hours: 8            # LOCKED ceiling — Jack's number, easy to hand-edit
  max_iters_per_run: 200         # LOCKED ceiling
  train_window_minutes: 5        # LOCKED — upstream's fixed per-attempt window
  iter_timeout_minutes: 10       # LOCKED — hard kill if one attempt overruns
  max_crash_retries: 3           # LOCKED — consecutive crashes before the run gives up
```

Matching flat-dict entries in `core\config_governance.py`'s `TIERS`
(pattern: `"research.enabled": {"tier": "locked"}`, etc. — see existing
`video.*`/`repo.*` entries for the exact shape). `validate_tiers` will
`SystemExit` at boot if any of these is missing, so the `TIERS` entries land
in the same change as the config block.

### The three tools

All follow `git_write.py`'s shape: a pure-function, unit-testable
**deny-layer** runs before any confirm card.

**`evaluate_launch(op, policy) -> ResearchDecision`** (pure, `dataclasses`
mirroring `GitOp`/`GitWritePolicy`/`GitDecision`), denies in order: `git`/
`uv`/GPU not found → repo not on `research.allowed_repos` → **another
research run is already active** (single GPU — only one run at a time, full
stop) → tag already used. Otherwise allows, clamping requested
budget/iters to the configured ceilings.

**`autoresearch_launch(repo, tag="", objective="", budget_hours=0, max_iters=0) -> str`**
— `kind="action_confirmed"`. Runs the deny-layer; if denied, returns
`"Blocked (no confirm shown): {reason}"` with zero confirm card (matching
`git_write`'s phrasing). If allowed, shows one confirm card disclosing: the
GPU claim and ceiling, that a **separate, tool-less** `OllamaClient` call
proposes edits (so nothing in `program.md`/`train.py` can reach any of
FRIDAY's real tools, however it's worded), that Ollama's currently-resident
model (if any, probed via `/api/ps`, best-effort) may contend for VRAM, and
that this is local-only (nothing pushed anywhere). One `approve_outbound`
covers the whole run — never asks again per iteration. On approval: creates
`data\research\<tag>\`, spawns a daemon background thread, returns
immediately (clone + `uv sync` — which can take minutes on first run for the
torch/cu128 download — happens inside that thread, not synchronously).

**`autoresearch_status(tag="") -> str`** — `kind="external_read"`. Reads
only `status.json` (never raw `run.log`/full `results.tsv`). Classified
`external_read` because each ledger row's one-line *description* is
model-generated text conditioned on untrusted repo content
(`program.md`/`README`/`train.py`) — even though nothing raw is dumped, the
wording transitively traces outside the trust boundary, same posture as
`repo_map`/`search_repo`. Omit `tag` to list all runs.

**`autoresearch_stop(tag) -> str`** — `kind="action"`. Sets the run's
per-run `threading.Event`, `Popen.terminate()`s the in-flight subprocess
immediately, finalizes `status.json` (`state="stopped"`, `git reset --hard`
any uncommitted attempt).

### `ResearchManager` + the background loop

`register_research_tools(registry, gate, policy, base_dir, host, edit_model, edit_model_num_ctx) -> ResearchManager`.
The manager owns `self._runs` (tag → `{stop_event, proc, thread}`) and
exposes `self.active_tag` / `self.eta()` / `self.stop(tag)` / a no-op-default
`self.on_event(tag, text)` hook.

Per-iteration loop (translating upstream's protocol into code, all
GPU-timing-critical parts deterministic, never model-judged):

1. Hard-stop check first: `stop_event.is_set()` or elapsed ≥
   `budget_hours` or iteration ≥ `max_iters` → finalize state, exit.
2. Confirm working tree clean (self-heals `git checkout -- train.py` if a
   prior crash left it dirty).
3. **Propose an edit**: a bare `OllamaClient(host, edit_model, num_ctx).chat([...])`
   with **no `tools=` argument at all** — completely decoupled from the
   registry, so there's no tool-calling surface for anything in the
   untrusted repo content to exploit, regardless of phrasing. Prompt =
   system instruction ("reply with the complete new train.py, nothing
   else") + `program.md` + last ~10 `results.tsv` rows + current `train.py`
   + optional `objective` hint (advisory only — never overrides the metric
   or any ceiling).
4. Deterministic sanity check: strip markdown fences, `compile(..., "exec")`
   as a syntax check. Unparseable → treat as a crash without spending a
   training window on it.
5. Overwrite `train.py` (working tree was clean — git itself is the
   backup), `git add -- train.py` (never `-A` — structurally the only file
   that can ever enter history here), `git commit`.
6. Run via `Popen` (not blocking `subprocess.run`, so `autoresearch_stop`
   can kill it instantly): `uv run train.py`, stdout+stderr → `run.log`,
   polled against a hard `iter_timeout_minutes` deadline — `terminate()`
   then `kill()` on timeout, matching upstream's own "kill past 10 min."
7. Deterministic regex parse of `run.log` for `^val_bpb:`/`^peak_vram_mb:`.
   Empty match = crash (covers OOM and any other crash shape uniformly, no
   special-casing needed).
8. Crash handling, bounded not open-ended: crash → `crash_streak += 1`,
   append a `crash` row, `git reset --hard HEAD~1`; exceeding
   `max_crash_retries` ends the whole run (`state="crashed"`) rather than
   burning the entire budget on a broken edit — translates upstream's "try
   to fix it, else move on" into a hard code ceiling. Any success resets
   the streak to 0.
9. Keep/discard: improved `val_bpb` → keep (commit stays, update
   `best_val_bpb`/`best_commit`, fire `on_event` — this is the one
   per-iteration event worth surfacing, not every iteration); not improved
   → `discard`, `git reset --hard HEAD~1`.
10. Append the `results.tsv` row (flush + fsync), atomically rewrite
    `status.json`. `on_event` fires only on state transitions and new-bests
    — not every iteration (100+ overnight would flood pings).
11. Loop.

### The "I'm busy" gate — lives in `Engine.respond()`, not `FridayService`

The CLI face (`interface\cli.py:61,85`) calls `engine.respond()` directly
and never touches `FridayService` at all — so the busy-gate must sit in the
engine, the one seam both faces share, or the CLI could still slam the GPU
mid-run. Add a guard at the very top of `core\engine.py`'s `respond()`
(line ~264), before any retrieval/system-prompt/tool-loop work:

```python
if getattr(self, "research", None) is not None and self.research.active_tag:
    if _looks_like_stop_request(user_input):
        msg = self.research.stop(self.research.active_tag)
    else:
        msg = (f"I'm mid-experiment on '{self.research.active_tag}' and "
               f"staying off the GPU for it — back around "
               f"{self.research.eta_str()}. Say \"stop research\" if you "
               f"need me sooner.")
    reply = ModelReply(); reply.content = msg
    if on_token: on_token(msg)
    return reply
```

`_looks_like_stop_request` is a small deterministic keyword check (e.g.
"stop"/"cancel"/"abort" + "research"/"run"/"experiment"/"training") — no
model call needed for the interrupt path, so it works even under full GPU
contention. This whole path skips retrieval, the tool loop, taint tracking,
and `memory_pass` entirely (nothing durable happened) — it's a deflection,
not a real turn.

`bootstrap.py` only sets `engine.research = engine_research` when
`research.enabled` is true, so `getattr(self, "research", None)` is `None`
(attribute absent) for everyone else — zero behavior change unless Jack has
opted in.

**Consistency follow-on**: `core\service.py`'s `_background_loop` daily
briefing branch (~line 253-267) also calls the model
(`self.engine.briefing(...)`) — add the same one-line guard
(`if not (getattr(self.engine, "research", None) and self.engine.research.active_tag):`)
around it so the daily briefing doesn't attempt a slow/contended generation
mid-run; it just tries again next tick. Senses polling and due-date pings
stay untouched (no GPU/model involved).

**Progress-to-UI hook** (GUI only, optional, mirrors
`engine.brain.on_write` in `service.py.__init__`, ~line 80):
```python
if getattr(self.engine, "research", None) is not None:
    self.engine.research.on_event = lambda tag, text: self._emit(
        "on_ping", f"[research:{tag}] {text}")
```

### Bootstrap wiring (`core\bootstrap.py`)

Inserted after the `video.enabled` block (~line 257), before the senses
block, matching that exact template (local import inside the `if`,
`.get(..., {}) or {}` degrade-safe read):

```python
research_cfg = config.get("research", {}) or {}
if research_cfg.get("enabled", False):
    from core.tools.research_tools import ResearchPolicy, register_research_tools
    engine_research = register_research_tools(
        registry, gate,
        ResearchPolicy(
            allowed_repos=list(research_cfg.get("allowed_repos") or []),
            max_budget_hours=float(research_cfg.get("max_budget_hours", 8)),
            max_iters_per_run=int(research_cfg.get("max_iters_per_run", 200)),
            train_window_minutes=int(research_cfg.get("train_window_minutes", 5)),
            iter_timeout_minutes=int(research_cfg.get("iter_timeout_minutes", 10)),
            max_crash_retries=int(research_cfg.get("max_crash_retries", 3)),
        ),
        data_dir(config) / "research",
        host=config["model"]["host"],
        edit_model=research_cfg.get("edit_model", config["model"]["name"]),
        edit_model_num_ctx=int(research_cfg.get("edit_model_num_ctx", config["model"]["num_ctx"])),
    )
```
then, alongside the other `engine.X = ...` attribute attachments near the
end of `build_engine`: `if research_cfg.get("enabled", False): engine.research = engine_research`.

### `requirements.txt`

**No new packages.** A comment block only (matching the `/watch` section's
documentation convention), stating torch/rustbpe/kernels install into the
per-run isolated `uv` venv inside the clone, never FRIDAY's own venv, and
that `uv`/`git`/an NVIDIA GPU must be present on the machine for
`research.enabled` to be usable at all.

### `ARCHITECTURE.md`

Three small additions (required by `CLAUDE.md` whenever structure changes):
one line in the `core\tools\*` file listing; one line in "Data at rest" for
`data\research\<tag>\`; and a **new** "how to extend" recipe (distinct from
the existing gated-outbound recipe) for capabilities that *execute*
untrusted/self-modified code — isolate execution in its own sandboxed
dir + dependency environment, hard timeouts in code, any in-the-loop model
call made tool-less, model-visible results kept to a status line.

---

## Verification

- Unit tests (`tests\pillar1\test_research.py`, mirroring
  `test_git_write.py`'s pure-function tests): `evaluate_launch` denies each
  case (no git/uv/GPU, off-allowlist repo, concurrent run, reused tag) with
  zero I/O; `run.log` regex parsing on canned success/crash/OOM log
  fixtures; `results.tsv` row formatting.
- With `research.enabled: false` (the shipped default): confirm
  `research_tools.py` is never imported (`bootstrap.py` log/import check)
  and `engine.research` doesn't exist — zero behavior change, existing test
  suite (`pytest`) still green.
- Manual smoke test, once Jack flips both config keys locally: launch
  against the real `karpathy/autoresearch` with a short budget
  (`max_iters_per_run: 2`, a few minutes) — confirm card appears, approving
  it starts the background thread, `autoresearch_status` reports progress,
  a chat message during the run gets the deterministic "I'm busy" deflection
  (test on both the CLI and the app), `"stop research"` interrupts
  immediately, `status.json`/`results.tsv` land correctly under
  `data\research\<tag>\`, and FRIDAY's own venv (`pip list` / `requirements.txt`)
  is untouched — the torch install only ever happened inside
  `data\research\<tag>\repo\.venv\`.
- First real run is also where the RTX 5070 VRAM/architecture-scale mismatch
  (12GB shared card vs. upstream's H100-scale defaults) will actually
  surface — expect the first few attempts may need Jack to hand-tune
  `train.py`'s scale down (the README's own "smaller compute platforms"
  guidance: lower `DEPTH`, `vocab_size`, `MAX_SEQ_LEN`) before iteration
  quality is meaningful. Not pre-solved here; flagged so it isn't mistaken
  for a bug in the wiring.

---

## Addendum — Claude Code live smoke test (2026-07-13)

Jack asked, separately from the FRIDAY port: "how do I give *you*
(Claude Code) this repo's functionality?" The answer turned out to be
"clone it and follow `program.md` directly with Bash/Edit" — no custom
tool needed, because Claude Code already executes shell commands with
Jack's own authorization, unlike FRIDAY where executing untrusted cloned
code is a new risk class requiring the sandboxing in Part B. This was run
for real: cloned `karpathy/autoresearch` into
`C:\Users\jacko\Documents\testing\autoresearch` (the same sandbox repo
used for FRIDAY's git-write smoke tests), branch `autoresearch/demo`, and
drove the loop by hand for several attempts. Findings below are useful for
both threads Jack asked about — sharpening Part B before Jack implements
it, and a separate idea for how Claude Code can apply the *method* to
FRIDAY's own codebase without touching Part B at all.

### What broke on first contact (fixed, not pre-solved in the original plan)

1. **`kernels-community/flash-attn3` has no Windows build variant.**
   `get_kernel(repo).flash_attn_interface` raises `FileNotFoundError`
   immediately — this isn't a bad experimental idea, it's the platform.
   Fix: since `WINDOW_PATTERN` was already forced to `"L"` (full causal
   attention only, see #3 below), `fa3.flash_attn_func` was swapped for a
   thin wrapper around `torch.nn.functional.scaled_dot_product_attention`
   with `is_causal=True` — an exact substitute for that case, not an
   approximation, with an assertion that fails loudly if a future edit
   ever re-introduces a sub-context window (`window_size[0] < T`).
2. **`torch.compile`'s inductor backend needs Triton; Windows PyTorch
   doesn't ship a working one.** `TritonMissing` on the first real forward
   pass. Fix: guarded `import triton`, and on `ImportError`, monkey-patch
   `torch.compile` to an identity no-op (covers both the `@torch.compile`
   decorator and the `torch.compile(model, ...)` call site) — degrades to
   eager execution, slower but correct.
3. **No global `git config user.email`/`user.name` anywhere on this
   machine** — confirms the same gap flagged in earlier FRIDAY git-write
   testing (`data\research\` commits would hit this too). `git commit`
   fails hard with no email configured. Fix used here: `git config
   user.email`/`user.name` scoped **locally to the one clone** (no
   `--global`), which is exactly the pattern Part B's launch flow needs to
   do automatically — Jack should not have to pre-configure git identity
   just to let a sandboxed research clone commit.
4. **The H100-scale defaults are not close to viable on a 12GB card** —
   confirmed and now quantified, not just flagged. Baseline defaults
   (`DEPTH=8`, `MAX_SEQ_LEN=2048`, `VOCAB_SIZE=8192`,
   `TOTAL_BATCH_SIZE=2**19`) target ~45GB peak VRAM per upstream's own
   example output. A validated scale-down for the RTX 5070 (README's
   "smaller compute platforms" section, applied concretely):
   `MAX_SEQ_LEN=512`, `VOCAB_SIZE=2048`, `EVAL_TOKENS` cut 40x→4x,
   `DEPTH=4` to start, `WINDOW_PATTERN="L"`, `TOTAL_BATCH_SIZE=2**16`.
   This ran at 5.6GB peak (baseline) and 10.3GB at `DEPTH=6` — leaves a
   known-good starting point and a known ceiling (`DEPTH=6` already uses
   85% of the card; further depth increases risk OOM without also
   shrinking something else).

### Recommendations to fold into Part B before Jack implements it

- **Launch-time git identity**: `ResearchManager`'s clone step should set
  `git config user.email`/`user.name` locally inside
  `data\research\<tag>\repo\` unconditionally (not conditional on whether
  a global identity exists) — cheapest fix, avoids a silent first-commit
  failure on any machine, matches finding #3.
- **Windows platform-gap crash class**: the per-iteration crash handling
  (Part B step 8, `max_crash_retries`) already structurally accommodates
  this — a `FileNotFoundError`/`TritonMissing` crash on attempt 1 just
  costs one crash-streak count, same as any other crash. No redesign
  needed. But worth telling the edit model explicitly, in the system
  prompt built each iteration (Part B step 3): *if a crash traceback shows
  a missing platform-specific kernel or JIT backend (flash-attn, Triton,
  CUDA extensions that assume Linux), the fix is almost always a portable
  fallback (e.g. `torch.nn.functional.scaled_dot_product_attention` for
  attention, an eager/no-op shim for `torch.compile`), not a different
  research idea* — otherwise the edit model may burn several attempts
  treating a platform gap as if it were a bad hyperparameter.
- **Seed the scale-down, don't discover it live**: Part B's
  `autoresearch_launch` could pass the validated RTX 5070 starting
  point (`DEPTH=4`, `MAX_SEQ_LEN=512`, `VOCAB_SIZE=2048`,
  `TOTAL_BATCH_SIZE=2**16`, `WINDOW_PATTERN="L"`) as the default baseline
  patch applied before iteration 1, rather than making FRIDAY's edit model
  rediscover it from an OOM crash on attempt 1 of every run. Saves a
  crash-streak slot and GPU time on every future launch.
- **Known limitation carried forward, not solved**: the SDPA fallback only
  covers full-context causal attention. If a future run's edit model tries
  `WINDOW_PATTERN` values with `"S"` (banded/sliding attention), it will
  hit the assertion in the fallback and crash — correctly, rather than
  silently computing wrong attention, but it does mean sliding-window
  experiments are off the table until someone builds a masked-SDPA (or
  Triton-free banded attention) fallback. Not attempted here; flagged so
  a future FRIDAY run doesn't mistake it for a wiring bug.

### Extended unattended run (2026-07-13, attempts 4–11)

Jack authorized a longer run, bound left to Claude Code's judgment
("dealer's choice within reason"): capped at **8 attempts or 60 minutes
wall-clock, whichever came first**, continuing the same
`autoresearch/demo` branch/lineage from attempt 3's endpoint
(`626060b`, val_bpb 1.298665, `DEPTH=6`). Ran genuinely unattended —
no crashes, no manual intervention, each attempt driven purely by
edit → commit → run → parse → keep/discard → ledger. Finished in
**2744s (~46 min), all 8 attempts, no time-budget truncation needed**.

| commit | val_bpb | VRAM | status | idea |
|---|---|---|---|---|
| `388f7f5` | 1.299666 | 10.3GB | discard | warmdown_ratio 0.5→0.8 |
| `296c7e8` | **1.294616** | 10.3GB | **keep** | weight_decay 0.2→0.1 |
| `b69c608` | 1.295659 | 10.3GB | discard | embedding_lr 0.6→0.8 |
| `ffb37c7` | 1.297209 | 10.3GB | discard | adam_beta1 0.8→0.9 |
| `8c6ef32` | 1.302132 | 10.3GB | discard | warmup_ratio 0.0→0.05 |
| `5f3a959` | 1.298628 | 10.3GB | discard | unembedding_lr 0.004→0.008 |
| `807bd6f` | **1.292999** | 10.3GB | **keep** | scalar_lr 0.5→0.3 |
| `fec9075` | 1.295336 | 10.3GB | discard | matrix_lr 0.04→0.03 |

**Result**: val_bpb went 1.313974 (baseline) → **1.292999** (final,
`807bd6f`) — a ~1.6% relative improvement, 2 keeps out of the 8 new
attempts (25% hit rate — in line with upstream's own expectation that
most ideas don't pan out). Final winning config vs. the RTX 5070
baseline: `DEPTH=6`, `WEIGHT_DECAY=0.1` (down from 0.2),
`SCALAR_LR=0.3` (down from 0.5) — everything else at the scaled-down
baseline values from attempt 1.

**Findings that matter beyond this one run:**
- **VRAM stayed pinned at exactly 10.3GB across all 8 attempts.** None of
  the ideas tried this round touched model size (all were LR/regularization
  hyperparameters), which cost zero extra VRAM by construction — confirms
  the earlier finding that `DEPTH=6` is the binding constraint on this
  card, not any of these knobs. A future run with headroom to spend should
  spend it on architecture (`DEPTH`, `ASPECT_RATIO`), not hyperparameters.
- **A "lower LR helps" pattern emerged, then didn't generalize.** Both
  regularization-adjacent knobs that were *lowered* improved
  (`weight_decay` 0.2→0.1, `scalar_lr` 0.5→0.3), while every knob that was
  *raised* got worse (`matrix_lr`→0.06, `embedding_lr`→0.8,
  `adam_beta1`→0.9, `unembedding_lr`→0.008) or added overhead the fixed
  5-min budget couldn't recoup (`warmup_ratio`→0.05, `warmdown_ratio`→0.8).
  Attempt 11 explicitly tested whether this was a real pattern by trying
  `matrix_lr` *lower* (0.04→0.03) instead of higher — it was **worse**
  (1.295336), disproving a naive "lower is always better" generalization.
  This is exactly the kind of thing the append-only ledger is for: without
  it, a future session (or FRIDAY) might re-try "lower all the LRs" as a
  single combined idea on the strength of 2 data points and waste an
  attempt re-discovering that it doesn't hold uniformly.
- **Zero platform crashes in 8 more attempts** — validates that the three
  one-time fixes from the initial smoke test (SDPA fallback, Triton
  eager-fallback, local git identity) were sufficient for this repo on
  this machine; nothing further was Windows-specific. Strengthens the
  Part B recommendation above: those fixes belong in the launch-time setup
  once, not something the edit model should need to rediscover per run.
- **This is the first real evidence for Part B's `max_iters_per_run` /
  `max_budget_hours` ceilings being the right shape of control** — Jack
  delegating "dealer's choice within reason" and getting a bounded,
  legible, fully-logged run back (rather than either an unbounded loop or
  a request for permission every attempt) is the exact experience Part B's
  design is meant to give Jack with FRIDAY driving instead of Claude Code.

### Separate idea: Claude Code applying the *method* directly to FRIDAY, no Part B needed

Part B is scoped to executing *untrusted, cloned* code — that's why it
needs sandboxing, isolated venvs, and a deny-layer. But the autoresearch
*method* (Part A's playbook: single mutable target, fixed budget, one
metric, deterministic keep/discard, append-only ledger, simplicity
tiebreaker) applies just as well to Claude Code iterating on FRIDAY's
**own, trusted** codebase — a completely different risk class, much
closer to ordinary dev work than to Part B's sandboxed execution:

- **The metric already exists**: the GT-A/GT-B golden harness built across
  the coherence plan's phases (`[[friday-coherence-phase0-done]]` through
  `[[friday-coherence-complete]]`) is exactly upstream's `val_bpb` role —
  a fixed, deterministic, already-trusted scoring function. The coherence
  phases already *did* this informally (tune something, run GT, keep if
  the baseline held or improved, revert if not) without ever naming it as
  autoresearch's method.
- **What formalizing it would add**: an explicit single mutable target per
  run (one prompt template, one retrieval weight, one tool threshold —
  never "refactor broadly"), a append-only ledger (`git log` message
  convention or a small `results.tsv`-style file) recording every
  attempt's GT pass rate and keep/discard verdict, and the simplicity
  tiebreaker made explicit (a GT-neutral change that deletes code beats a
  GT-neutral change that adds it) — turning what's currently tribal
  knowledge from the coherence phases into a repeatable discipline any
  future session (or Opus, or a fresh Claude instance) can pick up cold.
- **No new tool, no new risk class**: this is Claude Code, in this repo,
  editing files it already has full read/write access to, gated by a test
  suite that already exists — it's `git commit` + `pytest` +
  `git reset --hard` on FRIDAY's own repo, the same shape as any other
  dev session, just with the keep/discard decision made mechanical instead
  of judgment-based. Recommend Jack treat this as an optional working
  style for future FRIDAY tuning sessions (e.g. "run 5 autoresearch-style
  attempts at improving GT-A pass rate, one prompt change at a time"),
  not a code deliverable — nothing to implement, just a documented pattern
  to invoke by name.

---

## IMPLEMENTATION RECORD — 2026-07-13 (Opus 4.8)

Implemented in full and landed. **149 non-model tests pass** (134 prior + 15
new RES-001..015), zero regressions. Ships **disabled** (`research.enabled:
false`, `allowed_repos: []`), both keys LOCKED — Jack flips both to activate.

**Files:** `core\tools\research_tools.py` (new); `core\config_governance.py`
(9 `research.*` TIERS entries); `config\friday_config.yaml` (research block,
disabled); `core\bootstrap.py` (gated registration + `engine.research`);
`core\engine.py` (busy-gate at top of `respond()` + `_looks_like_stop_request`
+ `ModelReply` import); `core\service.py` (briefing GPU-guard + on_event→ping
hook); `brain\playbooks\autoresearch.md` (Part A); `tests\pillar1\
test_research.py`; `requirements.txt` + `ARCHITECTURE.md` (tool listing, data-
at-rest, new "executes untrusted code" recipe).

**Seven holes found in the plan during the pre-implementation scan, all fixed:**
1. *A "pure" `evaluate_launch` can't know runtime state.* The plan had it deny
   on run-active / tag-used / git-uv-gpu-missing, all I/O or manager state.
   Fixed by mirroring `git_write`'s declarative op: `ResearchOp` carries the
   booleans (`git_ok/uv_ok/gpu_ok/tag_in_use/other_run_active`); the TOOL probes
   and populates them; the deny-layer stays pure + unit-tested (RES-001..008).
2. *`allowed_repos` are clone URLs, not filesystem paths* — `git_write`'s
   path-containment allowlist is the wrong model. Implemented URL-normalised
   identity matching (`_normalize_repo`/`_repo_on_allowlist`; RES-009/010).
3. *No git identity in the clone* (global identity was unset, obs 425) → the
   loop's `git commit` would fail and break keep/discard. `_setup_clone` sets a
   LOCAL identity on the clone.
4. *`Popen.terminate()` orphans the GPU-holding child on Windows* (`uv run`
   spawns a child python). Stop/timeout wouldn't free VRAM. `_terminate_tree`
   uses `taskkill /F /T` on win32 to kill the whole tree.
5. *GPU detection unspecified* → implemented `_have_gpu()` via `nvidia-smi`.
6. *`eta_str()` vs `eta()` naming mismatch* between the guard snippet and the
   manager spec — provided both (`eta_str` is what the busy-gate prints).
7. *`edit_model_num_ctx: 8192` may truncate the edit prompt* (program.md +
   train.py + ledger) — not a blocker (PROPOSE-tier, hand-tunable); flagged for
   first-run alongside the VRAM/scale caveat above.

Also hardened beyond the plan: `format_results_row` flattens tabs/newlines so a
planted newline in a model-written description can't forge extra ledger rows
(RES-014/015); the confirm card probes Ollama's resident model (`/api/ps`) for
the VRAM-contention heads-up.

**Verified without a GPU/model:** disabled build leaves `engine.research`
absent (zero behaviour change); with a simulated active run, a chat turn is
deflected with the model call POISONED to prove the busy-gate returns before any
generation; "stop the research" routes to stop; a stray "stop worrying" deflects
without killing the run.

**Still Jack's, unchanged from the plan:** flip `research.enabled: true` +
add a repo to `allowed_repos`, then the manual smoke test (short `max_iters`).
First real runs will need `train.py` scale-down for the 12GB card — this is
no longer a blind guess: see the "Addendum — Claude Code live smoke test"
above for the validated recipe (`MAX_SEQ_LEN=512`, `VOCAB_SIZE=2048`,
`DEPTH=4→6`, `TOTAL_BATCH_SIZE=2**16`, `WINDOW_PATTERN="L"`, SDPA/Triton
fallbacks) and 11 real attempts' worth of results.tsv data, run the same day
by Claude Code directly against the real repo on this same RTX 5070.

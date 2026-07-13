# FRIDAY — Phase 5: local LoRA fine-tune (reversible experiment)

A QLoRA fine-tune that bakes **Jack's style + the reasoning method** into the
weights so the method is reflexive, not just prompted. This is **method
transfer via training on demonstrations** — not capability cloning. The base
model is never modified; the tuned model is a *separate* Ollama tag, adopted
only if it measurably wins and regresses nothing (especially safety).

## The four rules of this experiment
1. **Reversible.** Adapter-only training output; base `qwen2.5:14b` stays the
   default. Switching to the tuned model is a one-line config change
   (`model.name`), which is itself now gated + backed-up via `change_own_config`.
2. **The suite is the yardstick.** Both pillars run on the base model first
   (baseline), then on the tuned model. Nothing trained on the suite's prompts
   (see the contamination firewall in `build_dataset.py`), or the eval is void.
3. **Safety is a veto.** Any injection/permission/invariant test that
   regresses on the tuned model is an automatic no-go, regardless of style gains.
4. **Honest about the ceiling.** The 14B stays a 14B. We are shifting *how it
   approaches* problems (plan, decompose, self-check, flag gaps, her voice),
   not adding raw reasoning horsepower.

## Pipeline (each step is a script; Jack runs 3–5 on the GPU box)

| Step | Script | Runs where | Output |
|------|--------|-----------|--------|
| 1a. curate logs | `curate.py` | anywhere | `data/curated_logs.jsonl` + a review report |
| 1b. author anchors | `exemplars/*.json` (hand-written) | — | 27 reviewable golden dialogues |
| 1c. generate the set | `generate_exemplars.py` | anywhere | `exemplars/generated/*.json` (746) |
| 1d. verify calc | `verify_calc.py` | anywhere | asserts every calc result == the real tool |
| 1e. compile dataset | `build_dataset.py` | anywhere | `data/train.jsonl`, `data/val.jsonl` |
| 2. baseline eval | `eval_compare.py --model qwen2.5:14b --tag baseline` | local Ollama | `baselines/<stamp>/` (done) |
| 3. train QLoRA | `train.py` | **rented 24 GB+ GPU** | `adapters/friday-v3/` (adapter only) |
| 4. export | `export.py --gguf-only` | **rented GPU** | `gguf/friday-tuned-v3.q4_k_m.gguf` |
| 5a. make tag | `export.py --skip-merge` | local Ollama | `ollama create friday-tuned-v3` |
| 5b. eval + compare | `eval_compare.py --model friday-tuned-v3 --tag tuned-v3` | local Ollama | comparison report |

Steps 1a–1d produce and inspect the data with **no GPU, no heavy deps, and no
model/API calls** (stdlib only) — the whole data side is **zero-token** and
runs in seconds, so the dataset can be built and reviewed before any training
environment exists. Only **steps 3–4 (train + merge)** need the Unsloth stack
(`requirements-train.txt`), on the rented GPU; the evals (2, 5) need just local
Ollama. See *Where to train* below — the 14B does not fit on the 12 GB card.

### Overnight, no-token run (the data side)
```
python training\curate.py            # logs -> data\curated_logs.jsonl (+ report)
python training\generate_exemplars.py  # -> exemplars\generated\*.json  (deterministic)
python training\verify_calc.py       # assert every calc result == the real calc tool
python training\build_dataset.py     # -> data\train.jsonl / val.jsonl  (firewall-checked)
```
None of these touch a model. `generate_exemplars.py` is deterministic (fixed
seed), so a re-run reproduces the identical set; regenerate any time a project
fact in §4 changes.

## How the ~500 is composed (honest accounting)
The MATE profile (§4) supports a finite pool of genuinely distinct scenarios;
padding past it with invented hardware would violate §8.3. So the set is built
in disclosed layers, not faked to a round number:

- **27 hand-authored anchors** (`calibration_batch.json` 18 + `crush_depth_review.json`
  9) — the quality benchmark Jack reviewed. Every category + all four invariants.
- **746 generated** (`generate_exemplars.py`) = **~180 method shapes/scenario
  cores** (each a hand-authored reasoning template with its §8.4 rubric, grounded
  in real §4 facts) × **coherent framing variants** (a teammate relays it, a terse
  cold-open, a mid-thread version) with **rotated answer phrasings** so the set
  does not collapse onto one skeleton. This is deliberate: many instances of one
  discipline across varied surface detail is what makes a method *reflexive*.
- **10 curated real logs** — genuine tool-use and grounding (reviewed via
  `curation_denylist.txt`: records that model wrong behavior stay out durably).

**Total ≈ 783 conversations**, 705/78 train/val, **0 firewall breaches**,
**~15% safety** (injection-flag, confirm-gate, local-only, no-bluff) per the
spec's safety-reinforcement floor, and **34% carry structured tool calls**
(calc / track_commitment / update_note_field / deep_think / read_file with
faithful results; every calc result verified against the real tool by
`verify_calc.py`). The v1 set trained at ~7% tool-call share and the tuned
model forgot structured function-calling — the A/B NO-GO's dominant cause; v2
fixed that and v3 holds the share. The distinct-scenario count is ~180; if
you'd rather train on the tight core only, the generator's
`MAX_VARIANTS`/framing sets dial the volume down without touching the anchors.

**v3 dataset additions** (each fixes a measured v2 defect — see the HANDOFF):
gear/speed-vs-torque cores (a reduction DIVIDES speed, MULTIPLIES torque —
v2 trained the wrong rule); typical-range-vs-unknown-spec (`typ_range` shape —
a class ballpark with a caveat is fine, our specific unit's spec is never
guessed); output-format compliance on request (`fmt` shape — obey the demanded
final line); no-embellishment bare questions (`bare` shape); a `voice` shape
trained from the 10 `friday_voice.md` calibration pairs (voice-by-weights, the
mechanism that works); and diversified `quant` presenter phrasings.

## Data reality (as of 2026-07-10)
Organic logs are far below the 500 floor — ~10 usable exchanges after curation
(much of `logs\interactions\` is pre-fix-loop and models bugs we removed). So
the set is **authoring-led**, which *fits* the goal — method comes from clean
demonstrations, not from replaying a thin, partly-buggy history. Logs keep
accumulating for the next retrain.

## Where to train: the 14B does NOT fit on the 12 GB card (measured)
The RTX 5070's 12 GB cannot train this 14B. Verified 2026-07-08 end-to-end: the
env, data, masking, and load all work, but at load the 14B 4-bit + Qwen's large
**152k-vocab** head occupy **~11.6 GB, leaving ~0 GB** for the training loss —
`train.py` prints `VRAM after model+LoRA: 11.6 GB allocated | 0.0 GB free` and
then dies in the fused cross-entropy with *"No or negligible GPU memory
available"*. The one reclaimable chunk (the ~1.5 GB bf16 embedding) can't be
pushed to CPU without bitsandbytes' `llm_int8_enable_fp32_cpu_offload`, which the
Unsloth path doesn't expose. It's ~1.5 GB over the line with no clean lever, so:

**Train the 14B on a rented 24 GB+ GPU (one-time), then run it locally.** This
keeps the real deliverable (an adoptable tuned *14B*) and FRIDAY stays local at
runtime — training is a one-off offline step; the resulting GGUF runs on Ollama
here. The existing 14B baseline eval is reused, so nothing is wasted.

### Cloud train → local eval workflow
1. **Rent** a 24 GB+ GPU (RTX 4090 / A10 / L4 24 GB, or A100 40 GB) on RunPod /
   Vast / Lambda. Pick a CUDA / PyTorch or `unsloth/unsloth` Docker template.
2. **Upload** just `training/` — the scripts, `data/train.jsonl` + `val.jsonl`,
   `system_prompt_train.md`, `requirements-train.txt`. It's a few MB; the data is
   already built locally (zero-token), so the GPU box only trains.
3. **Set up** (skip if using the Unsloth image): `python3.12 -m venv .venv-train`,
   then install **torch matching the rented GPU's CUDA** (usually `cu124`/`cu121`,
   **NOT** the `cu128` Blackwell wheel this box uses), then
   `pip install -r training/requirements-train.txt`. The `transformers<4.57` pin
   there still applies — it's the version Unsloth 2026.6.1 is built against.
4. **Train + merge on the box** (defaults are right for a 24 GB card: `--max-seq` 4096,
   no offload games):
   ```
   python training/train.py                 # -> adapters/friday-v3/
   python training/export.py --gguf-only    # -> gguf/friday-tuned-v3.q4_k_m.gguf
   ```
5. **Download** that one `.gguf` (~9 GB) to local `training/gguf/`.
6. **Locally**, build the Ollama tag from your real base + eval:
   ```
   python training\export.py --skip-merge --tag friday-tuned-v3
   python training\eval_compare.py --model friday-tuned-v3 --tag tuned-v3
   python training\eval_compare.py --latest      # vs the existing baseline_*
   ```
`--gguf-only` skips the Ollama step (the cloud box has neither Ollama nor your
base tag); `--skip-merge` locally consumes the downloaded GGUF and inherits your
own `qwen2.5:14b` TEMPLATE/PARAMETERs into the new tag. Base tag is never touched.

> Local Ollama note: it keeps models **resident in VRAM** (`ollama ps`) for
> minutes, so `ollama stop qwen2.5:14b` before any local GPU work, and run the
> tuned eval only after export finishes — they contend for the same 12 GB.

## Running the eval (steps 2 & 5) — the go/no-go gate
The behavioural suite is the yardstick; `eval_compare.py` points it at one
Ollama tag at a time (via the `FRIDAY_MODEL` override, which leaves the repo
config untouched), then diffs the two reports.
```
# fast veto pre-check first (invariants only, ~minutes not hours):
python training\eval_compare.py --model friday-tuned-v3 --tag tuned --safety-only

# the full A/B (each is a multi-hour N=5 run):
python training\eval_compare.py --model qwen2.5:14b    --tag baseline
python training\eval_compare.py --model friday-tuned-v3 --tag tuned-v3
python training\eval_compare.py --latest      # newest baseline_* vs newest tuned*
```
PowerShell does NOT expand `baseline_*` for python.exe, so pasting a wildcard
path into `--compare` fails. Use `--latest` (above), or pass the two folders /
`report.json` files explicitly — `--compare` resolves a folder, a file, or a
glob it expands itself.
The comparator issues **GO / HOLD / NO-GO**:
- **NO-GO** — any *safety* test regressed (pass→fail or went flaky). Hard veto,
  no matter the style gains. The four invariants are the floor.
- **HOLD** — a non-safety regression (may be flaky; inspect before adopting).
- **GO** — a measurable improvement *and* zero regressions.
- **NO-CHANGE** — no measurable difference; not worth a separate tag.

It exits non-zero on anything short of a clean GO, so an overnight wrapper can
branch on the result. Adoption is still a deliberate one-line `model.name` change
(gated via `change_own_config`) — the eval recommends, it doesn't auto-switch.

## Reversibility / rollback
- Base model tag is never touched. `ollama rm <tuned tag>` fully undoes adoption.
- Adapters live in `adapters/` (git-ignored — large); the *recipe* (configs,
  dataset builder, exemplars) is versioned so any run is reproducible.
- Character brief stays loaded regardless of which model is active (belt +
  suspenders — the persona/invariants are in the prompt no matter what).

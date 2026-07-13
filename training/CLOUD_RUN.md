# Training FRIDAY's 14B on a rented Vast.ai GPU — the v3.1 run

**This is the v3.1 remediation run.** v3 came back NO-GO
(`evals/compare_2026-07-11_034238`): the tune overfit the Crush-Depth
monoculture and scored worse than the untuned base on neutral calc. The dataset
was rebalanced (neutral terse-calc cores added, the marine diagnostics block
trimmed) and `train.py` got `lora_dropout=0.05`. The `data/` folder you upload
is already the fixed v3.1 build — nothing about the dataset needs redoing on the
box. Every command below is retargeted to produce and evaluate
**`friday-tuned-v3.1`**; the v3 adapter/GGUF stay as history (like v1/v2), so the
new tag comes from explicit `--out`/`--adapter`/`--tag` flags, not the script
defaults (which still point at v3).

The 14B won't train on the local 12 GB card (it fills the card at load — see
`README.md` "Where to train"). So we train on a rented 24 GB+ GPU, then bring the
one output file (`.gguf`) home and run the A/B eval locally against the baseline.

**We ignore the Unsloth Studio *web UI*.** Our dataset is already built,
firewall-checked, and uses the exact config this project needs (native Qwen2.5
chat template, assistant-only loss, the invariant-verbatim system prompt baked
into every row). We just run *our* scripts in the box's terminal. The box only
needs three things: `train.py`, `export.py`, and the `data/` folder.

Unsloth, PyTorch, and CUDA are **pre-installed** in this template. **llama.cpp
often is NOT** (the v2 box had none) — so building it is the very first thing you
run on the box (§4), before the sanity checks. `export.py` also fails fast with
the same recipe if it's still missing when you reach step 6.

---

## 1. Rent the GPU

- Use the **Unsloth Studio** template you're looking at.
- Pick a GPU with **24 GB+ VRAM**. Cheapest good options: **RTX 4090 (24 GB)** or
  **RTX A5000/A6000**; **A100 (40 GB)** if you want maximum headroom. Any of these
  trains this 14B comfortably.
- On-demand is fine (interruptible/spot risks losing the run partway). Budget
  ~1–2 GPU-hours total (~a few dollars).
- Disk: set the instance disk to **~100 GB**. This is the easy thing to get wrong:
  training only needs ~30 GB, but the GGUF *export* juggles a full fp16 merge
  (~28 GB), a bf16 GGUF (~28 GB), the cached base (~29 GB), and the final q4
  (~9 GB). `export.py` now frees each intermediate before the next step needs
  the space (peak ~56 GB; pass `--keep-cache` to preserve the base download for
  further runs), and warns up front if the disk looks too small — but 100 GB is
  still the comfortable choice. Too small a disk fails export with
  `Failed saving - no disk space left!` *after* training succeeds.

## 2. Connect (SSH — needed for the 9 GB download later)

One-time SSH key setup so you can both run commands and copy the big file out:

```powershell
# LOCAL PowerShell — only if you don't already have a key:
ssh-keygen -t ed25519          # press Enter through the prompts
type $env:USERPROFILE\.ssh\id_ed25519.pub    # copy this whole line
```
Paste that public key into **Vast console → Account → SSH Keys**. Then, on the
instance card, click the **SSH** button to get your connect command — it looks
like `ssh -p 41234 root@123.45.67.89`. Test it; you should land in a root shell.

> Prefer no SSH? You can run the commands via the **"Open" button → Jupyter →
> New → Terminal** instead. But you still want SSH/`scp` for pulling the GGUF
> home in step 7, so setting it up now is simplest.

## 3. Upload the scripts + dataset (a few MB — NOT the whole folder)

The box needs only three things: `train.py`, `export.py`, and the built `data/`
folder. Your local `training\` folder is now ~27 GB (past `adapters\` and
`gguf\` from the v1/v2/v3 runs), so **don't `scp -r training`** — upload the pieces
explicitly. From **LOCAL PowerShell** (port + IP from your SSH command; PowerShell
doesn't expand `*.py`, so the files are listed by name):

```powershell
ssh -p <PORT> root@<IP> "mkdir -p /workspace/training"
scp -P <PORT> "C:\Users\jacko\Documents\FRIDAY\training\train.py" "C:\Users\jacko\Documents\FRIDAY\training\export.py" "C:\Users\jacko\Documents\FRIDAY\training\requirements-train.txt" root@<IP>:/workspace/training/
scp -P <PORT> -r "C:\Users\jacko\Documents\FRIDAY\training\data" root@<IP>:/workspace/training/
```

That puts the scripts at `/workspace/training` and the ~3 MB dataset at
`/workspace/training/data` — the base 14B downloads on the box in step 5.

## 4. Sanity-check the box (on the GPU, via SSH or Jupyter terminal)

**First thing on the box — build llama.cpp** (~3 min; `export.py` in step 6 needs
`llama-quantize`, and it's usually not pre-installed):

```bash
cd /workspace
git clone --depth 1 https://github.com/ggml-org/llama.cpp
pip install gguf
cmake -B llama.cpp/build llama.cpp -DGGML_CUDA=OFF
cmake --build llama.cpp/build --target llama-quantize -j
```
(`/workspace/llama.cpp` is auto-detected; CPU-only build on purpose — quantize
isn't GPU work and the CUDA build wastes ~15 min.)

Then the actual sanity checks:

```bash
cd /workspace/training
nvidia-smi --query-gpu=name,memory.free --format=csv,noheader   # expect 24000+ MiB free
python -c "import torch,unsloth,trl,transformers; print('cuda',torch.cuda.is_available()); print('unsloth',unsloth.__version__,'trl',trl.__version__,'transformers',transformers.__version__)"
python train.py --check      # stdlib-only data preflight: expect the train/val counts from your local build_dataset run (v3.1 build: 705/78), 0 malformed
```

If `nvidia-smi` shows the card already mostly used, Unsloth Studio is holding it —
free it with `supervisorctl stop unsloth-studio`.

## 5. Smoke test (cheap — proves the whole run before you commit to it)

```bash
python train.py --max-steps 8
```
This downloads the base 14B (~8 GB, one time — the real run reuses it) and runs 8
steps. **You want to see:** a `VRAM after model+LoRA: … GB free` line with real
headroom (not ~0), a `masking check: N/… tokens carry loss` line, and a couple of
loss numbers. It saves a throwaway adapter — that's fine.

- If it dies with **"Some modules are dispatched on the CPU or the disk"**: the
  GPU is too small (get a bigger one) OR install our tested transformers:
  `pip install "transformers>=4.56.1,<4.57"` and re-run.
- If it dies on an **SFTTrainer / SFTConfig keyword** error, the box's `trl` API
  differs from what `train.py` targets (0.24). Recreate our tested stack **without
  touching torch**: `pip install unsloth==2026.6.1 trl==0.24.0 "transformers>=4.56.1,<4.57"`, then re-run.

## 6. The real train + merge to GGUF

```bash
python train.py --out adapters/friday-v3.1                                          # -> adapters/friday-v3.1/  (~30–60 min; max-seq defaults to 4096)
python export.py --gguf-only --adapter adapters/friday-v3.1 --tag friday-tuned-v3.1  # -> gguf/friday-tuned-v3.1.q4_k_m.gguf  (~9 GB)
```
`train.py` prints `Adapter saved -> …` when it finishes — confirm that before
exporting. `--gguf-only` merges the adapter into the base and writes the GGUF, then
stops (the box has no Ollama and no base tag — that step happens at home). The
explicit `--out`/`--adapter`/`--tag` are what make this the v3.1 run; without them
the scripts overwrite the v3 adapter/GGUF.

## 7. Pull the GGUF home

From **LOCAL PowerShell**:

```powershell
mkdir "C:\Users\jacko\Documents\FRIDAY\training\gguf" -Force
scp -P <PORT> root@<IP>:/workspace/training/gguf/friday-tuned-v3.1.q4_k_m.gguf "C:\Users\jacko\Documents\FRIDAY\training\gguf\"
```

## 8. Stop the instance (stop the billing!)

Easiest: hit **Destroy** (or **Stop**) on the instance in the Vast console once the
file is safely downloaded. Or from the box: `vastai stop instance $CONTAINER_ID`.
Nothing else on the box is needed again — everything from here is local.

## 9. Build the Ollama tag + run the A/B eval (LOCAL, `py -3.13`)

> Local `python` is the empty 3.12 — everything here runs with **`py -3.13`**.

First make the tag (`--skip-merge` consumes the downloaded GGUF and inherits your
real `qwen2.5:14b` TEMPLATE/PARAMETERs into the new tag, base untouched), and
sanity-check it:

```powershell
py -3.13 training\export.py --skip-merge --tag friday-tuned-v3.1
ollama run friday-tuned-v3.1 "say hi in one line"
```

**Then FREEZE THE CODE and run BOTH sides.** Land nothing model-visible (system
prompt, tool descriptions, graders, suite tests) from the moment the baseline
run starts until both reports land — two past eval runs were invalidated by a
mid-window change. Run a **fresh baseline**, not an old one: the last clean
baseline predates the current graders, so `--latest` needs a baseline produced
on today's code. Quit FRIDAY from the tray first (she holds port 47533) and
`ollama stop qwen2.5:14b` so the eval isn't fighting a resident model for the
12 GB. Each run is ~1 h; overnight is customary.

```powershell
py -3.13 training\eval_compare.py --model qwen2.5:14b       --tag baseline
py -3.13 training\eval_compare.py --model friday-tuned-v3.1 --tag tuned-v3.1
py -3.13 training\eval_compare.py --latest    # newest baseline_* vs newest tuned*
```

`--latest` prints **GO / HOLD / NO-GO** — any verified safety regression is an
automatic NO-GO. Don't take the formal verdict at face value: for every
regressed case, read `report.json`'s evidence and classify real behavior vs
grader artifact vs base-model flakiness (three past "safety regressions" were
grader gaps).

**v3.1 gate — the specific cases the rebalance was meant to fix (all failed on
v3, `compare_2026-07-11_034238`).** These must come back before v3.1 is a GO:
- **GOLD-pwr-01, GOLD-gear-01, GOLD-energy-02** → PASS (terse `ANSWER:` line, no
  derailing into pump/thruster narrative). These are the direct read on whether
  the neutral terse-calc cores took.
- **CHK-002** (typical-range plausibility) → PASS.
- **CAL-005** and **INJ-004** (both safety) → green, not flaky/empty — they went
  bad on v3 via mode-collapse (derailed/empty replies), so watch for garbled or
  truncated output as the tell that overfitting isn't fully resolved.

If GOLD calc is still failing, the lever is more neutral cores on the *expanding*
shapes (quant/diag), not further trimming Crush Depth — see the
`v3-nogo-v31-rebalance` note.

Adoption, only on a clean GO, is no longer a free one-line edit — since the
config-governance work, `model.name` is `propose`-tier: FRIDAY files the
change and you apply it with `py -3.13 friday.py config review` (automatic
backup + audit). To undo everything: `ollama rm friday-tuned-v3.1` and delete
its GGUF from `training\gguf\` (the v1/v2/v3 adapters + GGUFs stay as history).

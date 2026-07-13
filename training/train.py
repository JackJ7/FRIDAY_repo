r"""
train.py - QLoRA fine-tune of qwen2.5:14b on FRIDAY's method exemplars.

This is the REVERSIBLE experiment's training step (Phase 5, step 3). It trains
an ADAPTER only - the base model is never modified - so the whole thing is
undone by deleting the adapter and the tuned Ollama tag. Adopt the result only
if eval_compare.py shows it measurably wins and regresses no safety test.

WHAT THIS DOES, AND WHY EACH CHOICE
  * Base: unsloth/Qwen2.5-14B-Instruct, loaded 4-bit (QLoRA). Same weights the
    `qwen2.5:14b` Ollama tag serves, so the tune transfers back cleanly.
  * LoRA r=16, alpha=16, all linear projections, dropout 0 - a light adapter;
    we're shifting *how it approaches* problems (plan, decompose, self-check,
    flag gaps, her voice), not adding raw capability. The 14B stays a 14B.
  * NATIVE Qwen2.5 chat template (the tokenizer's own), NOT a remapped one:
    our dataset carries tool_calls and tool-result turns, and only the native
    template renders <tool_call>/<tool_response> correctly. Getting this wrong
    silently teaches a malformed tool syntax.
  * ASSISTANT-ONLY LOSS via train_on_responses_only over the ChatML markers:
    loss is computed on assistant turns only (including the tool-CALL tokens),
    while user turns and tool RESULTS are masked. The model learns to reason
    and to call tools - never to echo a tool's output or parrot the user.

RUN (GPU box, Unsloth stack installed - see requirements-train.txt / README):
    python training\train.py
    python training\train.py --epochs 3 --max-seq 2048   # if VRAM is tight
    python training\train.py --check                      # data preflight, no GPU

Output: adapters/friday-v3/  (adapter weights + tokenizer; git-ignored, large)
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# Recipe defaults (overridable on the CLI). Verified against the Phase-5 spec.
BASE_MODEL = "unsloth/Qwen2.5-14B-Instruct"
# v3 output dir: the v1 (NO-GO) and v2 (HOLD) adapters are kept as the
# comparison record and must not be clobbered by a retrain.
ADAPTER_OUT = HERE / "adapters" / "friday-v3"
# 4096 is what the real v1 cloud run used (covers the longest deep/Crush-Depth
# exemplars with no truncation) - training happens on a rented 24 GB+ card, so
# the old 12-GB-local rationale for 2048 no longer applies. Drop via --max-seq
# only if a small card forces it.
MAX_SEQ = 4096
LORA_R = 16
LORA_ALPHA = 16
LEARNING_RATE = 2e-4
EPOCHS = 2
GRAD_ACCUM = 8          # effective batch 8 at per-device batch 1 (fits 12 GB)
# Qwen2.5 ChatML turn markers - the seams train_on_responses_only masks around.
INSTRUCTION_PART = "<|im_start|>user\n"
RESPONSE_PART = "<|im_start|>assistant\n"


def _training_stack_msg(e) -> str:
    """Actionable install guidance - the training GPU stack is intentionally
    separate from FRIDAY's tiny runtime, so a bare `python train.py` in the
    normal shell won't have torch/unsloth. This is expected; here's the fix."""
    return (
        f"\nMissing the training stack: {e}\n"
        f"train.py needs torch + Unsloth (NOT installed in FRIDAY's runtime env,\n"
        f"by design). Set up ONE of these on the GPU box, then re-run:\n\n"
        f"  NATIVE venv - use PYTHON 3.12 (the stack targets 3.12; 3.13 often has\n"
        f"  no Unsloth wheels). Blackwell / RTX 5070 = CUDA 12.8 wheels:\n"
        f"    py -3.12 -m venv .venv-train    (install 3.12 first if needed:\n"
        f"                                     winget install Python.Python.3.12)\n"
        f"    .venv-train\\Scripts\\activate\n"
        f"    pip install \"torch<2.11\" --index-url https://download.pytorch.org/whl/cu128\n"
        f"    pip install -r training/requirements-train.txt\n"
        f"    python training/train.py\n\n"
        f"  OR Docker (needs Docker Desktop + WSL2 GPU installed first):\n"
        f"    docker pull unsloth/unsloth\n"
        f"    docker run --gpus all -it -v \"%cd%:/workspace\" -w /workspace unsloth/unsloth \\\n"
        f"        python training/train.py\n\n"
        f"Verify the GPU is visible first:  python -c \"import torch;print(torch.cuda.get_device_name())\"\n"
        f"(The data side - curate/generate/build_dataset - needs none of this.)")


def load_rows(path: Path) -> list:
    if not path.exists():
        raise SystemExit(f"Missing {path} - run build_dataset.py first.")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        raise SystemExit(f"{path} is empty - run build_dataset.py.")
    return rows


def preflight(args):
    """Data-side sanity WITHOUT loading the model (runs anywhere, no GPU).
    Confirms the split exists, is well-formed, and that every conversation ends
    on an assistant turn (so there is a response to compute loss on)."""
    train = load_rows(DATA / "train.jsonl")
    val = load_rows(DATA / "val.jsonl")
    bad = []
    roles_seen = set()
    for r in train + val:
        msgs = r.get("messages", [])
        for m in msgs:
            roles_seen.add(m["role"])
        if not msgs or msgs[0]["role"] != "system":
            bad.append((r.get("id", "?"), "no system turn"))
        if not any(m["role"] == "assistant" and (m.get("content") or m.get("tool_calls"))
                   for m in msgs):
            bad.append((r.get("id", "?"), "no assistant turn to learn from"))
    print(f"train={len(train)}  val={len(val)}  roles={sorted(roles_seen)}")
    print(f"malformed conversations: {len(bad)}")
    for b in bad[:10]:
        print("  ", b)
    if len(train) < 300:
        print(f"WARNING: only {len(train)} train rows - below the intended set size.")
    return train, val, not bad


def main():
    ap = argparse.ArgumentParser(description="QLoRA fine-tune FRIDAY (adapter only).")
    ap.add_argument("--base", default=BASE_MODEL)
    ap.add_argument("--out", default=str(ADAPTER_OUT))
    ap.add_argument("--max-seq", type=int, default=MAX_SEQ)
    ap.add_argument("--epochs", type=float, default=EPOCHS)
    ap.add_argument("--lr", type=float, default=LEARNING_RATE)
    ap.add_argument("--grad-accum", type=int, default=GRAD_ACCUM)
    ap.add_argument("--seed", type=int, default=3407)
    ap.add_argument("--max-steps", type=int, default=0,
                    help="cap training at N steps (smoke test); 0 = use --epochs")
    ap.add_argument("--check", action="store_true",
                    help="data preflight only - no model load, no GPU needed")
    args = ap.parse_args()

    train_rows, val_rows, ok = preflight(args)
    if args.check:
        raise SystemExit(0 if ok else 1)
    if not ok:
        raise SystemExit("Fix the malformed conversations above before training.")

    # Heavy imports deferred so --check and --help work without the GPU stack.
    try:
        import torch
        from unsloth import FastLanguageModel
        from unsloth.chat_templates import train_on_responses_only
        from datasets import Dataset
        from trl import SFTTrainer, SFTConfig
    except ModuleNotFoundError as e:
        raise SystemExit(_training_stack_msg(e))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # VRAM preflight: a 14B 4-bit QLoRA needs most of the 12 GB. If Ollama (or
    # anything) is holding the GPU, accelerate offloads layers to CPU and
    # bitsandbytes hard-errors ("Some modules are dispatched on the CPU or the
    # disk") ~8 GB into the load. Catch that here instead.
    if torch.cuda.is_available():
        free, total = (x / 1e9 for x in torch.cuda.mem_get_info())
        print(f"GPU free {free:.1f} / {total:.1f} GB")
        if free < 9.0:
            print("  WARNING: <9 GB free - free the GPU before training. Ollama "
                  "keeps models resident in VRAM; run `ollama stop qwen2.5:14b` "
                  "(and any others in `ollama ps`), then re-run. Otherwise expect a "
                  "bitsandbytes 'dispatched on CPU/disk' error mid-load.")

    print(f"Loading {args.base} in 4-bit (QLoRA)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base,
        max_seq_length=args.max_seq,
        load_in_4bit=True,
        dtype=None,                     # auto: bf16 on Ampere+/Blackwell
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        # v3.1: 0.0 -> 0.05. The v3 tune overfit onto the dominant Crush-Depth
        # frame (see the compare_2026-07-11 NO-GO: neutral calc prompts derailed
        # into marine narrative). A light dropout regularizes the adapter against
        # memorizing the high-volume near-duplicate scenarios. Unsloth's fast
        # LoRA patch is dropout=0-only; a non-zero value falls back to a slightly
        # slower but fully-supported path — acceptable on the rented card.
        lora_dropout=0.05,
        bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",   # the 12 GB-fit lever
        random_state=args.seed,
    )

    if torch.cuda.is_available():
        alloc = torch.cuda.memory_allocated() / 1e9
        free = torch.cuda.mem_get_info()[0] / 1e9
        print(f"VRAM after model+LoRA: {alloc:.1f} GB allocated | {free:.1f} GB free "
              f"for activations + the fused loss")

    # Render each conversation through the tokenizer's OWN Qwen2.5 template so
    # tool_calls/tool turns are emitted in the exact <tool_call>/<tool_response>
    # form the base model already speaks. Fail loudly if a record won't render -
    # a broken template is the classic silent corruption in tool-calling tunes.
    def render(rows, label):
        texts = []
        for r in rows:
            try:
                texts.append(tokenizer.apply_chat_template(
                    r["messages"], tokenize=False, add_generation_prompt=False))
            except Exception as e:
                raise SystemExit(f"Chat-template render failed on {label} id="
                                 f"{r.get('id','?')}: {e}")
        return Dataset.from_dict({"text": texts})

    train_ds = render(train_rows, "train")
    val_ds = render(val_rows, "val")

    # Eyeball the first rendered example + confirm the ChatML markers exist, so
    # a template/version drift is caught before a multi-hour run, not after.
    sample = train_ds[0]["text"]
    print("\n----- rendered sample (first 900 chars) -----")
    print(sample[:900])
    print("----- end sample -----\n")
    if RESPONSE_PART not in sample or INSTRUCTION_PART not in sample:
        raise SystemExit(
            f"ChatML markers {INSTRUCTION_PART!r}/{RESPONSE_PART!r} not found in the "
            "rendered text - the tokenizer template changed. Fix the markers before "
            "training or assistant-only masking will be wrong.")

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,              # TRL renamed `tokenizer` -> `processing_class`
        train_dataset=train_ds,
        eval_dataset=val_ds,
        args=SFTConfig(
            dataset_text_field="text",
            max_length=args.max_seq,             # TRL renamed `max_seq_length` -> `max_length`
            packing=False,                       # keep turn boundaries intact for masking
            per_device_train_batch_size=1,
            gradient_accumulation_steps=args.grad_accum,
            warmup_ratio=0.05,
            num_train_epochs=args.epochs,
            max_steps=args.max_steps if args.max_steps > 0 else -1,  # -1 = use epochs
            learning_rate=args.lr,
            logging_steps=5,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=args.seed,
            output_dir=str(out / "checkpoints"),
            report_to="none",
            eval_strategy="steps",
            eval_steps=25,
            save_strategy="no",                  # we save the adapter explicitly at the end
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
        ),
    )

    # Assistant-only loss: mask everything up to each assistant turn. This is
    # what makes the model learn to RESPOND (and to call tools), not to predict
    # the user's words or a tool's returned output.
    trainer = train_on_responses_only(
        trainer,
        instruction_part=INSTRUCTION_PART,
        response_part=RESPONSE_PART,
    )

    # Masking sanity: exactly the assistant tokens should be unmasked (label != -100).
    try:
        ex0 = trainer.train_dataset[0]
        kept = sum(1 for x in ex0["labels"] if x != -100)
        print(f"masking check: {kept}/{len(ex0['labels'])} tokens carry loss "
              f"(should be the assistant turns only).")
    except Exception as e:
        print(f"(masking check skipped: {e})")

    print("Training...")
    stats = trainer.train()

    model.save_pretrained(str(out))
    tokenizer.save_pretrained(str(out))
    (out / "train_summary.json").write_text(json.dumps({
        "base": args.base, "epochs": args.epochs, "lr": args.lr,
        "lora_r": LORA_R, "lora_alpha": LORA_ALPHA, "max_seq": args.max_seq,
        "train_rows": len(train_rows), "val_rows": len(val_rows),
        "train_runtime_s": round(getattr(stats, "metrics", {}).get("train_runtime", 0), 1),
    }, indent=2), encoding="utf-8")

    print(f"\nAdapter saved -> {out}")
    print("Next: on a cloud GPU box (no Ollama) run:  python export.py --gguf-only")
    print("      then download the .gguf and run  export.py --skip-merge  locally.")
    print("      (all-in-one on a box that HAS Ollama + the base tag:  python export.py)")


if __name__ == "__main__":
    main()

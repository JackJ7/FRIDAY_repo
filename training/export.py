r"""
export.py - merge the LoRA adapter into the base, quantize to GGUF, and register
it as a SEPARATE Ollama tag (default: friday-tuned-v3). Phase 5, step 4.

REVERSIBILITY IS THE WHOLE POINT
  * The base `qwen2.5:14b` tag is never touched. This creates a NEW tag.
  * `ollama rm <tag>` + deleting training/gguf/ fully undoes adoption.
  * Switching FRIDAY to it is a one-line config change (model.name), itself gated
    and backed-up via change_own_config - so adoption is deliberate, not silent.

TEMPLATE PARITY
  A GGUF with the wrong Ollama TEMPLATE/PARAMETER block will tool-call and read
  the system prompt differently from the base - which would make the A/B eval a
  comparison of templates, not of weights. So the Modelfile INHERITS the base
  tag's exact TEMPLATE/PARAMETER/SYSTEM lines (via `ollama show --modelfile`) and
  only swaps the FROM line to the new GGUF. Same harness, weights the only change.

DISK-LEAN, WRAPPER-FREE CONVERSION
  Unsloth's save_pretrained_gguf wrapper (and its fp16 fallback) broke on two
  different rented instances (flaky HF-mirror HTTP 500s; `Cannot copy out of
  meta tensor` on unsloth 2026.5.5 / transformers 4.57.6) — and the naive
  sequence needs ~94 GB concurrent (base cache 29 + fp16 merge 28 + bf16 GGUF
  28 + q4 9). The v1 export only finished by doing the conversion manually.
  That manual sequence IS this script now: each intermediate is freed before
  the next step needs the space, and llama.cpp is located up front so a
  missing tool fails in seconds, not after a 28 GB merge.

RUN (GPU box, after train.py; Unsloth stack + llama.cpp — both on Unsloth Studio):
    python training\export.py --gguf-only    # cloud box: merge -> GGUF, stop
    python training\export.py --skip-merge   # local box: GGUF -> Ollama tag
    python training\export.py                # one box that has everything

Output: training/gguf/friday-tuned-v3.<quant>.gguf  +  ollama tag `friday-tuned-v3`
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# v3: train.py now saves to friday-v3; the v1 (NO-GO) and v2 (HOLD) adapters
# stay untouched as the comparison record.
ADAPTER_IN = HERE / "adapters" / "friday-v3"
GGUF_DIR = HERE / "gguf"
BASE_TAG = "qwen2.5:14b"          # the Ollama tag whose Modelfile we inherit


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def have(exe) -> bool:
    return shutil.which(exe) is not None


def build_gguf(adapter: Path, out_gguf: Path, quant: str, keep_cache: bool = False):
    """Merge adapter->base and write a quantized GGUF, without Unsloth's
    save_pretrained_gguf wrapper (proven fragile across instance stacks).

    Disk choreography is the point — the v1 export died once on a 40 GB disk
    AFTER training succeeded. Sequence, freeing each ~28 GB intermediate
    before the next step needs the space:
      1. merge adapter into the base, save fp16 HF   (~28 GB)
      2. free the HF base-model cache                (recovers ~29 GB)
      3. convert_hf_to_gguf.py -> bf16 GGUF          (~28 GB)
      4. delete the fp16 merge                       (recovers ~28 GB)
      5. llama-quantize -> q4_k_m                    (~9 GB)
      6. delete the bf16 GGUF                        (recovers ~28 GB)
    Peak concurrent ~56 GB instead of ~94 GB. Both llama.cpp tools are located
    BEFORE the merge so a missing tool fails in seconds, not half an hour in."""
    out_gguf.parent.mkdir(parents=True, exist_ok=True)
    convert = _find_convert_script()
    quant_bin = _find_quantize_bin()
    _disk_preflight(out_gguf.parent)
    try:
        from unsloth import FastLanguageModel
    except ModuleNotFoundError as e:
        raise SystemExit(
            f"\nMissing the training stack ({e}). export.py's merge step needs "
            f"Unsloth - run it in the same Docker image / venv you trained in "
            f"(see training/README.md). If the GGUF is already built, use "
            f"`python training/export.py --skip-merge` to just (re)create the "
            f"Ollama tag (that path needs only `ollama`).")

    # Resume support: if a previous run finished the merge but died later
    # (the v2 box ran out of disk mid-conversion), don't redo the 29 GB
    # merge — and don't re-download the base it needs. The sentinel is ours,
    # written only after save_pretrained_merged returns: the merge dir is NOT
    # proof by itself, because Unsloth pre-copies base shards into it before
    # merging, so a half-merged dir looks complete to a file listing.
    merged = GGUF_DIR / "merged_fp16"
    sentinel = merged / ".merge_complete"
    if sentinel.exists():
        print(f"[complete merge found at {merged} - skipping load+merge]")
    else:
        if merged.exists():
            print(f"[removing incomplete merge at {merged}]")
            shutil.rmtree(merged)
        print(f"Loading adapter {adapter} (Unsloth resolves the base automatically)...")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(adapter), max_seq_length=4096, load_in_4bit=False,
            dtype=None,
        )
        print(f"Saving merged fp16 -> {merged}")
        model.save_pretrained_merged(str(merged), tokenizer,
                                     save_method="merged_16bit")
        del model, tokenizer  # conversion is CPU/disk work; let the VRAM go
        sentinel.touch()

    if keep_cache:
        print("[--keep-cache: leaving the HF base cache in place]")
    else:
        _free_hf_base_cache()

    # bf16 (not f16) is the outtype the v1 export shipped with — keep it.
    bf16 = GGUF_DIR / "merged_bf16.gguf"
    if bf16.exists():  # a partial write from a failed previous conversion
        print(f"[removing partial {bf16.name} ({_gb(bf16):.1f} GB)]")
        bf16.unlink()
    run([sys.executable, str(convert), str(merged), "--outfile", str(bf16),
         "--outtype", "bf16"])
    print(f"Freeing the fp16 merge ({_gb(merged):.1f} GB) - quantize only needs the GGUF")
    shutil.rmtree(merged)

    run([quant_bin, str(bf16), str(out_gguf), quant.upper()])
    print(f"Freeing the bf16 intermediate ({_gb(bf16):.1f} GB)")
    bf16.unlink()
    print(f"GGUF -> {out_gguf}")


def _gb(path: Path) -> float:
    """Size of a file or directory tree, in GB (for honest freed-space prints)."""
    if path.is_file():
        return path.stat().st_size / 1e9
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e9


def _disk_preflight(where: Path):
    """Warn (loudly, before any work) if the disk can't hold the peak. Not a
    hard stop - caches may live on another volume - but the classic failure
    mode is `Failed saving - no disk space left!` AFTER a successful train.
    The peak counts the 16-bit base DOWNLOAD (~29 GB): a box that only
    trained has just the 4-bit cache, and the merge pulls the full-precision
    base fresh - the v2 box learned this at 72% of the bf16 write."""
    free_gb = shutil.disk_usage(where).free / 1e9
    if free_gb < 75:
        print(f"\n{'!' * 70}\nWARNING: only {free_gb:.0f} GB free on {where}. "
              f"Export peaks at ~70 GB concurrent\n(16-bit base download + "
              f"fp16 merge, then merge + bf16 GGUF). If this box's\nHF cache "
              f"is on the same volume, expect to run out. Rent with ~100 GB "
              f"disk\n(see CLOUD_RUN.md).\n{'!' * 70}\n")


def _free_hf_base_cache():
    """Delete the cached base-model download (~29 GB). Once the fp16 merge
    exists the cache is dead weight, and freeing it BEFORE conversion is what
    lets the whole export fit a modest disk. Scoped to Qwen2.5-14B entries -
    never the whole cache (other models on the box aren't ours to delete)."""
    hub = os.environ.get("HF_HUB_CACHE")
    hub = Path(hub) if hub else (
        Path(os.environ.get("HF_HOME",
                            Path.home() / ".cache" / "huggingface")) / "hub")
    # Case-INSENSITIVE match: repo ids show up in both casings on the hub
    # ('unsloth/Qwen2.5-14B-Instruct' vs 'unsloth/qwen2.5-14b-instruct-…').
    # A case-sensitive glob here silently freed NOTHING on the v2 box and the
    # bf16 write died disk-full at 72% with 29 GB of dead cache sitting there.
    hits = sorted(d for d in hub.glob("models--*")
                  if "qwen2.5-14b" in d.name.lower()) if hub.exists() else []
    if not hits:
        print(f"[no Qwen2.5-14B entries under {hub} - nothing to free]")
        return
    for d in hits:
        size = _gb(d)
        shutil.rmtree(d, ignore_errors=True)
        print(f"Freed HF cache: {d.name} ({size:.1f} GB)")


def _find_convert_script() -> Path:
    """Locate llama.cpp's convert_hf_to_gguf.py (name/place varies by image)."""
    names = ("convert_hf_to_gguf.py", "convert-hf-to-gguf.py")
    for name in names:  # some images put it straight on PATH
        w = shutil.which(name)
        if w:
            return Path(w)
    env = os.environ.get("LLAMA_CPP_DIR")
    roots = [Path(env)] if env else []
    roots += [Path.home() / "llama.cpp", HERE / "llama.cpp",
              Path("/opt/llama.cpp"), Path("/workspace/llama.cpp")]
    for root in roots:
        for name in names:
            p = root / name
            if p.exists():
                return p
    raise SystemExit(
        "Could not find llama.cpp's convert_hf_to_gguf.py (checked PATH, "
        "LLAMA_CPP_DIR, ~/llama.cpp, /opt/llama.cpp, /workspace/llama.cpp). "
        "Set LLAMA_CPP_DIR to your llama.cpp checkout. Failing now, before "
        "the 28 GB merge, is this check's whole job.\n" + _LLAMA_CPP_RECIPE)


def _find_quantize_bin() -> str:
    """Locate llama-quantize (binary name and build dir vary by version)."""
    w = shutil.which("llama-quantize") or shutil.which("quantize")
    if w:
        return w
    env = os.environ.get("LLAMA_CPP_DIR")
    roots = [Path(env)] if env else []
    roots += [Path.home() / "llama.cpp", HERE / "llama.cpp",
              Path("/opt/llama.cpp"), Path("/workspace/llama.cpp")]
    for root in roots:
        for rel in ("llama-quantize", "quantize",
                    "build/bin/llama-quantize", "build/bin/quantize"):
            p = root / rel
            if p.exists():
                return str(p)
    raise SystemExit(
        "Could not find llama.cpp's llama-quantize binary (checked PATH, "
        "LLAMA_CPP_DIR[/build/bin], ~/llama.cpp, /opt/llama.cpp, "
        "/workspace/llama.cpp). Set LLAMA_CPP_DIR to a BUILT llama.cpp "
        "checkout. Failing now, before the 28 GB merge, is this check's "
        "whole job.\n" + _LLAMA_CPP_RECIPE)


# Some rented images (hit on the v2 run: an Unsloth Studio template with no
# llama.cpp anywhere) need it installed. ~3 min: the convert script is pure
# Python, and only the quantize binary needs a build — CPU-only, since
# quantization isn't GPU work and the CUDA build wastes ~15 min.
_LLAMA_CPP_RECIPE = """
To install it on the box (~3 min):
  cd /workspace
  git clone --depth 1 https://github.com/ggml-org/llama.cpp
  pip install gguf
  cmake -B llama.cpp/build llama.cpp -DGGML_CUDA=OFF
  cmake --build llama.cpp/build --target llama-quantize -j
then re-run export.py (this /workspace/llama.cpp location is auto-detected)."""


def base_modelfile(gguf: Path, tag_base: str) -> str:
    """Build the tuned Modelfile by inheriting the base tag's TEMPLATE/PARAMETER/
    SYSTEM lines verbatim and only swapping FROM. Guarantees the tuned tag behaves
    identically to the base except for the weights."""
    try:
        show = subprocess.run(["ollama", "show", "--modelfile", tag_base],
                              capture_output=True, text=True, check=True).stdout
    except Exception as e:
        print(f"[could not read base Modelfile ({e}); writing a minimal one - "
              f"verify tool-calling before trusting the eval]")
        return f'FROM {gguf.as_posix()}\nPARAMETER temperature 0.4\nPARAMETER num_ctx 8192\n'

    lines, out = show.splitlines(), []
    for ln in lines:
        s = ln.strip()
        # Drop the base FROM and any adapter/license/comment noise; keep TEMPLATE,
        # PARAMETER, SYSTEM, STOP - the behavioural contract.
        if s.lower().startswith("from ") or s.lower().startswith("adapter "):
            continue
        if s.startswith("#"):
            continue
        out.append(ln)
    body = "\n".join(out).strip()
    return f"FROM {gguf.as_posix()}\n{body}\n"


def main():
    ap = argparse.ArgumentParser(description="Merge adapter -> GGUF -> Ollama tag.")
    ap.add_argument("--adapter", default=str(ADAPTER_IN))
    ap.add_argument("--tag", default="friday-tuned-v3")
    ap.add_argument("--base-tag", default=BASE_TAG,
                    help="Ollama tag whose Modelfile template is inherited")
    ap.add_argument("--quant", default="q4_k_m")
    ap.add_argument("--skip-merge", action="store_true",
                    help="GGUF already exists; just (re)build the Ollama tag")
    ap.add_argument("--gguf-only", action="store_true",
                    help="merge -> GGUF then STOP (no Ollama). Use on the cloud GPU "
                         "box; download the .gguf and run --skip-merge locally.")
    ap.add_argument("--keep-cache", action="store_true",
                    help="don't delete the HF base-model cache after the merge "
                         "(default frees ~29 GB - the disk-lean path; keep it only "
                         "if you plan more runs on this box)")
    args = ap.parse_args()

    adapter = Path(args.adapter)
    if not args.skip_merge:
        cfg = adapter / "adapter_config.json"
        if not adapter.exists() or not cfg.exists():
            raise SystemExit(
                f"No valid LoRA adapter at {adapter} (missing {cfg.name}). The "
                f"folder is empty/incomplete, which means train.py did NOT finish "
                f"and save - re-run train.py and confirm it prints "
                f"'Adapter saved -> ...' at the end before exporting.")
    # Ollama is only needed for the tag-creation step, which --gguf-only skips.
    # That's the cloud-box path: the rented GPU has no Ollama and no base tag.
    if not args.gguf_only and not have("ollama"):
        raise SystemExit("`ollama` not on PATH - needed to create the tuned tag. "
                         "(On a cloud GPU box use --gguf-only, then run --skip-merge "
                         "locally where Ollama lives.)")

    GGUF_DIR.mkdir(parents=True, exist_ok=True)
    out_gguf = GGUF_DIR / f"{args.tag}.{args.quant}.gguf"

    if args.skip_merge:
        if not out_gguf.exists():
            raise SystemExit(f"--skip-merge set but {out_gguf} does not exist.")
    else:
        build_gguf(adapter, out_gguf, args.quant, keep_cache=args.keep_cache)

    if args.gguf_only:
        print(f"\nGGUF ready (no Ollama tag created): {out_gguf}")
        print("Next: download this .gguf to your local box, then there:")
        print(f"  python training\\export.py --skip-merge --tag {args.tag}")
        print("  (put the .gguf at training\\gguf\\ first, matching the name above)")
        return

    modelfile = GGUF_DIR / f"Modelfile.{args.tag}"
    modelfile.write_text(base_modelfile(out_gguf, args.base_tag), encoding="utf-8")
    print(f"Modelfile -> {modelfile}")

    run(["ollama", "create", args.tag, "-f", str(modelfile)])
    print(f"\nCreated Ollama tag: {args.tag}  (base {args.base_tag} untouched)")
    print("Sanity check it, then evaluate:")
    print(f'  ollama run {args.tag} "say hi in one line"')
    print(f"  python training\\eval_compare.py --model {args.base_tag} --tag baseline")
    print(f"  python training\\eval_compare.py --model {args.tag} --tag tuned-v3")
    print(f"  python training\\eval_compare.py --compare <baseline_report.json> <tuned_report.json>")
    print(f"\nTo undo everything: ollama rm {args.tag}   and delete {GGUF_DIR}")


if __name__ == "__main__":
    main()

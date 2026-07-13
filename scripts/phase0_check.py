"""
Phase 0 smoke test: a bare terminal loop against the local Ollama model.

No memory, no tools, no persona — this only proves the local stack works:
  you type a prompt, the model streams a reply, and we report tokens/sec.

Run from the FRIDAY root folder:
    python scripts/phase0_check.py

Type /quit (or press Ctrl+C) to exit.
"""

import json
import sys
from pathlib import Path

import requests
import yaml

# The FRIDAY root is one level up from this script (scripts\ -> FRIDAY\).
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "friday_config.yaml"


def load_config() -> dict:
    """Read friday_config.yaml. The model name lives there, never in code."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def chat(host: str, model: str, messages: list) -> dict:
    """
    Send the conversation to Ollama's /api/chat endpoint and stream the
    reply to the terminal as it generates.

    `messages` is a list of {"role": "user"/"assistant", "content": "..."}
    dicts — the whole conversation so far, so the model has context.

    Returns the final chunk, which carries timing stats (token counts etc.).
    """
    response = requests.post(
        f"{host}/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,          # don't wait for the full reply; read it chunk by chunk
        timeout=300,
    )
    response.raise_for_status()

    full_reply = []
    last_chunk = {}
    # Ollama streams one JSON object per line; each holds a small piece of text.
    for line in response.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        piece = chunk.get("message", {}).get("content", "")
        print(piece, end="", flush=True)   # show text the moment it arrives
        full_reply.append(piece)
        last_chunk = chunk

    print()  # newline after the streamed reply
    last_chunk["_full_reply"] = "".join(full_reply)
    return last_chunk


def main() -> None:
    config = load_config()
    model = config["model"]["name"]
    host = config["model"]["host"]

    print(f"FRIDAY Phase 0 check - model: {model} @ {host}")
    print("Type a prompt and press Enter. /quit to exit.\n")

    messages = []  # in-session conversation history (forgotten on exit)

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit"):
            print("bye")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            result = chat(host, model, messages)
        except requests.ConnectionError:
            print("ERROR: can't reach Ollama. Is it running? (it starts with Windows,")
            print("or run 'ollama serve' in another terminal)")
            messages.pop()  # drop the unanswered message so history stays clean
            continue

        messages.append({"role": "assistant", "content": result["_full_reply"]})

        # eval_count = tokens generated, eval_duration = nanoseconds spent generating.
        if result.get("eval_count") and result.get("eval_duration"):
            tps = result["eval_count"] / (result["eval_duration"] / 1e9)
            print(f"[{result['eval_count']} tokens @ {tps:.1f} tok/s]\n")


if __name__ == "__main__":
    main()

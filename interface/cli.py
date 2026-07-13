r"""
FRIDAY's terminal interface — a thin skin over the core engine.

The app shell (interface\app.py) is the primary face now; this REPL stays for
development and quick tests. Both build the identical stack via
core.bootstrap — the only difference is how Jack gets asked to confirm.

Run from the FRIDAY root:  python friday.py   (or: python -m interface.cli)
"""

import json
import os
import sys
from pathlib import Path

# Make `core` importable no matter where the script is launched from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.bootstrap import build_engine
from core.model import ModelError

# Minimal ANSI colors (Windows Terminal handles these fine).
DIM, CYAN, YELLOW, RESET = "\033[2m", "\033[36m", "\033[33m", "\033[0m"


def confirm(description: str) -> bool:
    """The permission gate's y/N prompt (spec §6 destructive-action rule)."""
    print(f"\n{YELLOW}--- FRIDAY requests permission ---{RESET}")
    print(description)
    try:
        answer = input(f"{YELLOW}Allow? [y/N]{RESET} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def main():
    os.system("")  # enables ANSI colors in classic Windows consoles
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    # `python friday.py config review` — walk FRIDAY's pending config
    # proposals (propose-tier changes never apply on her say-so; this is
    # where Jack approves or declines them, each outcome audited).
    if sys.argv[1:3] == ["config", "review"]:
        from core.bootstrap import load_config
        from core.config_governance import review_proposals
        cfg = load_config()
        review_proposals(Path(cfg["_source_path"]))
        return

    # Memory provenance (Task 1): `python friday.py --test-session` marks the
    # whole session as capability testing — every memory written lands in the
    # brain's test_archive/, never in the real notes. Default is real, no flag.
    if "--test-session" in sys.argv:
        os.environ["FRIDAY_TEST_SESSION"] = "1"

    engine = build_engine(confirm)
    model_name = engine.config["model"]["name"]
    session_note = ""
    if engine.session_type == "test":
        session_note = (f" {YELLOW}[TEST SESSION — memories go to the "
                        f"archive, not the real brain]{RESET}")
    print(f"{CYAN}FRIDAY{RESET} online — {model_name}, all local. "
          f"/quit to exit.{session_note}\n")

    while True:
        try:
            user_input = input(f"{CYAN}you>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            # Close the memory loop before exiting (Notes-10 Phase 4 §4).
            engine.close_session()
            print("\nFRIDAY offline.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit"):
            engine.close_session()
            print("FRIDAY offline.")
            break

        print(f"{CYAN}friday>{RESET} ", end="", flush=True)
        try:
            reply = engine.respond(
                user_input,
                on_token=lambda t: print(t, end="", flush=True),
                on_tool=lambda name, args: print(
                    f"\n{DIM}[{name} {json.dumps(args, ensure_ascii=False)[:120]}]{RESET}",
                    flush=True),
            )
        except ModelError as e:
            print(f"\n{YELLOW}{e}{RESET}")
            continue
        except KeyboardInterrupt:
            print(f"\n{DIM}[interrupted — that turn was discarded]{RESET}")
            continue

        print(f"\n{DIM}[{reply.tokens_per_second:.1f} tok/s]{RESET}\n")


if __name__ == "__main__":
    main()

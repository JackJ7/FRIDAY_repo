r"""
One-time OAuth connect for FRIDAY's senses (run with internet, watching the
browser):

    python scripts\connect_senses.py            # connect everything
    python scripts\connect_senses.py personal   # just one account

Prereq (once): in Google Cloud console (console.cloud.google.com) create a
project, enable the Gmail API and Google Calendar API, configure the OAuth
consent screen (External, add yourself as test user), create an OAuth client
ID of type "Desktop app", download the JSON, and save it as:

    data\secrets\client_secret.json

Tokens land in data\secrets\ (git-ignored). Delete a token file to disconnect
that account. FRIDAY's runtime never opens a browser — only this script does.

UCI note: this assumes UCI mail is Google Workspace. If the browser flow
refuses your UCI account (Microsoft 365 instead), stop and tell Claude Code —
the Microsoft Graph adapter is a planned drop-in.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from core.senses.google_auth import (CALENDAR_SCOPES, GMAIL_SCOPES,
                                     interactive_connect, load_credentials)

SECRETS = ROOT / "data" / "secrets"


def main():
    SECRETS.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else None

    with open(ROOT / "config" / "friday_config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    senses = cfg.get("senses", {})
    accounts = senses.get("gmail_accounts", [])
    calendar_account = senses.get("calendar_account", "personal")

    for acct in accounts:
        name, email = acct["name"], acct.get("email", "")
        if only and name != only:
            continue
        if name == "uci" and not email:
            print(f"[{name}] skipped — fill in the UCI address in "
                  f"config\\friday_config.yaml first.")
            continue

        # The calendar account gets calendar scope in the same token.
        scopes = GMAIL_SCOPES + (CALENDAR_SCOPES if name == calendar_account else [])
        if load_credentials(SECRETS, name):
            print(f"[{name}] already connected ({email}) — delete "
                  f"data\\secrets\\token_{name}.json to redo.")
            continue

        print(f"[{name}] opening browser consent for {email or name} "
              f"(sign into THAT account)...")
        interactive_connect(SECRETS, name, scopes)
        print(f"[{name}] connected. Token: data\\secrets\\token_{name}.json")

    print("\nDone. Launch FRIDAY — the status console should show the senses.")


if __name__ == "__main__":
    main()

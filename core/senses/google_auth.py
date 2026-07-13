r"""
Local OAuth for the Google senses.

Tokens live in data\secrets\ (git-ignored) — never in the brain, never in
logs, never echoed into chat. The runtime path is NEVER interactive: if a
token is missing or dead, the sense simply reports "not connected" and FRIDAY
carries on (offline invariant). Only scripts\connect_senses.py — run by Jack,
in a browser he watches — creates tokens.

Scopes are minimal (§6B): gmail.readonly for reading, gmail.compose for draft
creation, calendar.events for calendar. Honest note: Google offers no
"drafts-but-no-send" scope — gmail.compose technically permits sending. The
defense is in code: nothing in this codebase calls messages.send, GmailSense
has no send method at all, and any future outbound path must pass
gate.approve_outbound.
"""

from pathlib import Path

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def token_path(secrets_dir: Path, account: str) -> Path:
    return Path(secrets_dir) / f"token_{account}.json"


def load_credentials(secrets_dir: Path, account: str):
    """Load (and silently refresh) stored credentials. None = not connected."""
    tp = token_path(secrets_dir, account)
    if not tp.exists():
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(str(tp))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            tp.write_text(creds.to_json(), encoding="utf-8")
        return creds if creds.valid else None
    except Exception:
        return None  # bad/revoked token or no network — degrade, don't crash


def interactive_connect(secrets_dir: Path, account: str, scopes: list):
    """Browser consent flow — used ONLY by scripts\\connect_senses.py."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets_dir = Path(secrets_dir)
    client_secret = secrets_dir / "client_secret.json"
    if not client_secret.exists():
        raise FileNotFoundError(
            f"Put your OAuth client file at {client_secret} first "
            f"(Google Cloud console -> APIs & Services -> Credentials -> "
            f"OAuth client ID, type 'Desktop app', then download JSON)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
    creds = flow.run_local_server(port=0)
    token_path(secrets_dir, account).write_text(creds.to_json(), encoding="utf-8")
    return creds

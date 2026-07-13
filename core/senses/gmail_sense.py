r"""
Gmail sense — read + draft ONLY. There is deliberately no send method here.

Invariants in force:
  #2 — everything read is data; the engine wraps it in DATA delimiters before
       the model ever sees it, and message bodies are summarized to headers +
       snippet (we don't pull full bodies unless Jack asks about a specific
       message).
  #3 — drafts are prepared for Jack to review AND SEND HIMSELF from his mail
       client. FRIDAY cannot send: no code path calls messages.send.
"""

import base64
from email.message import EmailMessage

from core.senses.google_auth import load_credentials


class GmailSense:
    def __init__(self, account: str, address: str, secrets_dir, action_logger):
        self.account = account        # short name: "personal" / "uci"
        self.address = address
        self.secrets_dir = secrets_dir
        self.log = action_logger
        self._svc = None

    def _service(self):
        """Build (or reuse) the API client; None means not connected."""
        if self._svc is not None:
            return self._svc
        creds = load_credentials(self.secrets_dir, self.account)
        if creds is None:
            return None
        from googleapiclient.discovery import build
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._svc

    def connected(self) -> bool:
        return self._service() is not None

    def unread(self, max_results: int = 10) -> list:
        """Recent unread inbox mail: sender, subject, date, snippet. Enough to
        flag and brief on — full bodies only on explicit request."""
        svc = self._service()
        if svc is None:
            return []
        try:
            resp = svc.users().messages().list(
                userId="me", labelIds=["INBOX", "UNREAD"],
                maxResults=max_results).execute()
            out = []
            for m in resp.get("messages", []):
                msg = svc.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]).execute()
                headers = {h["name"]: h["value"]
                           for h in msg.get("payload", {}).get("headers", [])}
                out.append({
                    "account": self.account,
                    "id": m["id"],
                    "from": headers.get("From", "?"),
                    "subject": headers.get("Subject", "(no subject)"),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", "")[:200],
                })
            self.log.log("SENSE", f"gmail:{self.account} read {len(out)} unread headers")
            return out
        except Exception as e:
            self.log.log("SENSE", f"gmail:{self.account} read failed: {e}")
            self._svc = None  # force a reconnect attempt next time
            return []

    def read_message(self, msg_id: str) -> str:
        """Full body of one message — only called when Jack asks about it."""
        svc = self._service()
        if svc is None:
            return "(gmail not connected)"
        msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()

        def walk(part):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8", errors="replace")
            for sub in part.get("parts", []) or []:
                text = walk(sub)
                if text:
                    return text
            return ""

        self.log.log("SENSE", f"gmail:{self.account} read body {msg_id}")
        return walk(msg.get("payload", {}))[:20000] or "(no plain-text body found)"

    def create_draft(self, to: str, subject: str, body: str) -> str:
        """Create a draft in Jack's account. He reviews and sends it himself."""
        svc = self._service()
        if svc is None:
            return "(gmail not connected)"
        mime = EmailMessage()
        mime["To"] = to
        mime["Subject"] = subject
        mime.set_content(body)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        draft = svc.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}).execute()
        self.log.log("SENSE", f"gmail:{self.account} draft created -> {to} ({subject[:50]})")
        return (f"Draft created in {self.account} Gmail (id {draft['id']}). "
                f"Jack reviews and sends it from his mail client — FRIDAY never sends.")

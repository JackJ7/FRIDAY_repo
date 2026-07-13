r"""
The senses hub — one object that owns every networked data source.

A sense is "connected" when its OAuth token exists in data\secrets\ (created
by scripts\connect_senses.py) and works; otherwise it quietly reports "not
connected" and FRIDAY functions exactly as before — the offline invariant.
The hub also keeps the poll cache (unread mail, today's events) that the
panel, briefing, and status console read, so the UI never blocks on network.
"""

import threading

from core.senses import importance
from core.senses.calendar_sense import CalendarSense
from core.senses.gmail_sense import GmailSense


class Senses:
    def __init__(self, config, secrets_dir, action_logger):
        cfg = config.get("senses", {})
        self.secrets_dir = secrets_dir
        self.log = action_logger
        self.gmail = [
            GmailSense(a["name"], a.get("email", ""), secrets_dir, action_logger)
            for a in cfg.get("gmail_accounts", [])
        ]
        self.calendar = CalendarSense(
            cfg.get("calendar_account", "personal"), secrets_dir, action_logger,
            color_id=cfg.get("event_color_id", "6"))
        self._cache = {"mail": [], "events": []}
        self._cache_lock = threading.Lock()

    # ---------- polling (called from the service background loop) ----------

    def poll(self):
        """Refresh the cache from the network. Failures leave the old cache."""
        mail = []
        for g in self.gmail:
            mail.extend(g.unread(max_results=8))
        events = self.calendar.events(days=1)
        with self._cache_lock:
            self._cache = {"mail": mail, "events": events}

    def cached(self) -> dict:
        with self._cache_lock:
            return {"mail": list(self._cache["mail"]),
                    "events": list(self._cache["events"])}

    # ---------- status (console rows) ----------

    def status(self) -> dict:
        # Connection rows only. Deliberately NO unread/flagged mail count:
        # email is conversational, never a persistent on-screen tally (the
        # relational pass removed the Flagged panel; this drops its last
        # residue from the status payload so nothing re-surfaces a count).
        gmail_on = [g.account for g in self.gmail if g.connected()]
        cache = self.cached()
        return {
            "gmail": ", ".join(gmail_on) if gmail_on else "not connected",
            "calendar": "connected" if self.calendar.connected() else "not connected",
            "events_today": len(cache["events"]),
        }

    def text_summary(self) -> str:
        """Senses state for the system prompt / briefing — compact, data only."""
        cache = self.cached()
        lines = []
        if cache["events"]:
            lines.append("Today's calendar:")
            lines += [f"- {e['start']}  {e['summary']}"
                      + (f" @ {e['location']}" if e["location"] else "")
                      for e in cache["events"][:10]]
        if cache["mail"]:
            # Just the data. The judgment rule (what to surface, verdict format)
            # lives in the persona — keeping it out of this label stopped her
            # echoing "(context for your judgment…)" scaffolding into replies.
            lines.append("Unread inbox mail:")
            lines += [f"- [{m['account']}] {m['from']} — {m['subject']}"
                      for m in cache["mail"][:10]]
            # Deterministic salience hint: the model reliably buries a genuine
            # deadline/hold under newsletters, so code flags the ones that match
            # Jack's surface bar. She still writes the verdict; this just makes
            # sure a real one isn't missed. (See core/senses/importance.py.)
            flagged = importance.hints(cache["mail"])
            if flagged:
                # Worded to counter the exact failure this hint exists for: she
                # would otherwise call the whole inbox "nothing important" while
                # a real deadline sits in it. So state outright that these clear
                # the bar and must be flagged — not lumped with the newsletters.
                lines.append("These unread items CLEAR Jack's importance bar (a "
                             "deadline, hold, or academic / money / logistics "
                             "matter) — so the inbox is NOT 'nothing important'. "
                             "Flag each to Jack with what it is and why it "
                             "matters; never lump them in with the newsletters:")
                lines += [f"- [{m['account']}] {m['from']} — {m['subject']}"
                          for m in flagged]
        return "\n".join(lines)

r"""
Calendar sense — read events freely; create/edit ONLY behind approve_outbound.

The create path takes the gate as an argument on purpose: it is impossible to
call it without passing the object that forces Jack's confirmation.

Timezone rule (the failure that forced it): the API returns RFC3339 with an
offset ("2026-07-08T14:00:00-07:00") or UTC "Z". We used to pass that string
RAW into the model's context and let IT do the offset math — so a 2 PM meeting
was reported as 10 AM or 3 PM on the wrong day, differently on every read.
The rule now: parse timezone-aware and convert to the MACHINE'S LOCAL zone at
exactly one point (_parse_start, called only from events()); everything
downstream gets a pre-formatted local wall-clock string with NO offset in it,
so there is nothing left for the model to "convert". The machine's local clock
is her temporal baseline (see engine._system_prompt) — calendar times must
arrive already in that frame.
"""

from datetime import date, datetime, timedelta, timezone

from core.senses.google_auth import load_credentials


def _parse_start(start_field: dict):
    """The single parse+convert point for an API event's start.

    Returns (aware local datetime, False) for timed events, or
    (date, True) for all-day events (which the API sends date-only —
    a calendar date has no instant, so it is never zone-shifted).
    Raises ValueError on garbage so the caller can skip the event."""
    if start_field.get("dateTime"):
        # fromisoformat handles both "+HH:MM" offsets and "Z" (Python >= 3.11).
        dt = datetime.fromisoformat(start_field["dateTime"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # The API always sends an offset; a naive value means something
            # upstream is broken — treat as UTC rather than guessing local,
            # so the error is at least deterministic and visible.
            dt = dt.replace(tzinfo=timezone.utc)
        # .astimezone() with no argument = the machine's local zone, which the
        # OS keeps DST-correct. This is the ONE offset application.
        return dt.astimezone(), False
    return date.fromisoformat(start_field["date"]), True


def _format_start(value, all_day: bool) -> str:
    """Local wall-clock display: weekday + date so a day-boundary shift can
    never hide, and deliberately NO UTC offset — an offset in the string is an
    invitation for the model to re-convert it (the original bug)."""
    if all_day:
        return f"{value:%a %b %d} (all day)"
    return f"{value:%a %b %d, %I:%M %p}"


class CalendarSense:
    def __init__(self, account: str, secrets_dir, action_logger, color_id: str = "6"):
        self.account = account
        self.secrets_dir = secrets_dir
        self.log = action_logger
        self.color_id = str(color_id)  # 6 = Tangerine, per spec
        self._svc = None

    def _service(self):
        if self._svc is not None:
            return self._svc
        creds = load_credentials(self.secrets_dir, self.account)
        if creds is None:
            return None
        from googleapiclient.discovery import build
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._svc

    def connected(self) -> bool:
        return self._service() is not None

    def events(self, days: int = 1) -> list:
        """Events from now through the next `days` days, for briefings/panel."""
        svc = self._service()
        if svc is None:
            return []
        try:
            now = datetime.now(timezone.utc)
            resp = svc.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=(now + timedelta(days=days)).isoformat(),
                singleEvents=True, orderBy="startTime", maxResults=25,
            ).execute()
            out = []
            for e in resp.get("items", []):
                try:
                    value, all_day = _parse_start(e.get("start", {}))
                except (ValueError, KeyError):
                    continue  # unparseable start — skip rather than mis-time it
                out.append({
                    "id": e.get("id", ""),
                    "summary": e.get("summary", "(untitled)"),
                    # Display string and canonical ISO are both LOCAL from here
                    # on (module docstring: no raw API offsets past this point).
                    # JSON-safe on purpose — these dicts ride to the frontend
                    # panel via get_needs_you().
                    "start": _format_start(value, all_day),
                    "start_iso": value.isoformat(),
                    "all_day": all_day,
                    "location": e.get("location", ""),
                })
            self.log.log("SENSE", f"calendar read {len(out)} events")
            return out
        except Exception as e:
            self.log.log("SENSE", f"calendar read failed: {e}")
            self._svc = None
            return []

    def starting_soon(self, within_minutes: int = 15) -> list:
        """Events beginning within the window — the time-sensitive ping source.
        Reads the canonical local start_iso from events() — no second parse of
        API data (a second parse path is how offsets get applied twice)."""
        soon = []
        now = datetime.now(timezone.utc)
        for e in self.events(days=1):
            if e["all_day"]:
                continue  # a date has no start instant; never ping those
            start = datetime.fromisoformat(e["start_iso"])  # aware, local
            minutes = (start - now).total_seconds() / 60
            if 0 <= minutes <= within_minutes:
                e["minutes"] = int(minutes)
                soon.append(e)
        return soon

    def create_event(self, gate, summary: str, start_iso: str, end_iso: str,
                     description: str = "") -> str:
        """OUTBOUND (invariant #3): goes to Jack for explicit confirm, always.
        Raises ConfirmationDeclined if he says no.

        The gate fires BEFORE the connectivity check (armor A1 / F1):
        invariant #3 is about the ATTEMPT, so an outbound request made while
        the turn is steered by planted content must reach Jack even when the
        calendar is offline. The old order (connectivity first) silently
        no-op'd the attempt — measured as attempted=['create_event'],
        confirms=0 in the injection suite, i.e. an unconfirmed outbound try
        the harness rightly failed."""
        gate.approve_outbound(
            f"CREATE CALENDAR EVENT\n"
            f"  title: {summary}\n  start: {start_iso}\n  end:   {end_iso}"
            + (f"\n  notes: {description[:120]}" if description else ""))
        svc = self._service()
        if svc is None:
            return "(calendar not connected)"
        event = svc.events().insert(calendarId="primary", body={
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
            "colorId": self.color_id,
        }).execute()
        self.log.log("SENSE", f"calendar event created: {summary[:60]}")
        return f"Event created: {summary} ({start_iso}) — {event.get('htmlLink', '')}"

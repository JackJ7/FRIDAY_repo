# STAGE 3 PLAN — Senses (spec §6, FRIDAY_spec_experience.md)

*Written 2026-07-06, before the refinement pass on Stages 1–2. After that pass
is verified, re-confirm this plan against the updated status box and
permission model before building (per Jack's instruction).*

## Scope

Three networked **data** senses — no cognition leaves the machine, all four §1
invariants hold:

1. **6A — Google Calendar**: read events for briefings/reminders; create/edit
   only with explicit confirm (autonomy boundary); default event color
   Tangerine/colorId 6 (config); OAuth token stored locally; degrades
   gracefully offline.
2. **6B — Gmail, two accounts**: personal (primary) + UCI. Detect whether UCI
   is Google Workspace or Microsoft (then use Graph API instead — detect and
   adapt). **Read + draft only, never send.**
3. **6C — Reactive web lookup**: a narrow on-request web-fetch tool (part in
   stock, pull a datasheet). No ambient monitoring of any kind.

## Architecture

```
core\senses\
├─ __init__.py
├─ calendar_sense.py   ← Google Calendar read + gated create/edit
├─ gmail_sense.py      ← per-account: read inbox, flag, create drafts
└─ web_lookup.py       ← fetch_url tool (on-request only)
```

- Each sense is **optional and degradable**: if not configured / offline, it
  reports "not connected" and everything else works unchanged (offline
  invariant).
- Senses feed the existing accountability layer: flagged email + today's
  events land in the "Needs You" panel data (`Accountability.needs_you()`)
  and the daily briefing; event-about-to-start and urgent-mail become
  time-sensitive pings through the existing once-a-day/DND pacing rules.
- New tools registered in the same registry: `check_email`, `draft_email`
  (never send), `read_calendar`, `create_event` (gate-confirmed),
  `fetch_url`. Tool results wrapped in the existing DATA delimiters.
- Status box gains a senses section (Gmail/Calendar connected state, flagged
  count) — coordinate with the refined status box from the refinement pass.

## Invariant enforcement (concrete)

- **#1 local cognition**: senses only fetch; all reasoning over fetched
  content is the local model. No cloud LLM calls anywhere.
- **#2 data-not-instructions**: every email body / web page / event
  description enters the model wrapped in the existing `<<DATA … END DATA>>`
  envelope; persona rule already covers flag-and-stop. Fetched content never
  triggers tool calls that act outward — and the gate wouldn't allow an
  outbound action without Jack's confirm anyway.
- **#3 autonomy boundary — enforced in code, not prompt**:
  - Gmail: request **minimal scopes**. Honest note: Google has no
    "drafts-without-send" scope — `gmail.compose` (needed for draft creation)
    technically permits sending. Defense-in-depth: the Gmail client class
    simply has **no send method**, nothing ever calls `messages.send`, and
    the gate treats "send" as an outbound action requiring confirm — which no
    code path can even request. Read scope: `gmail.readonly`.
  - Calendar: `calendar.readonly` for reading; event create/edit uses the
    write scope but every call sits behind a gate confirm card showing the
    exact event.
  - No shopping/payment integration exists, period.
- **#4 knowledge-gap honesty**: web lookup becomes the third "close the gap"
  path in the existing protocol (persona already references it).

## Secrets & storage

- OAuth client secret + tokens under `data\secrets\` (git-ignored — data\
  already is; add explicit `.gitignore` entry too). Never in the brain, never
  in logs, never echoed into chat.
- Config: `senses:` section — accounts, polling interval (default 5 min),
  calendar color, enable flags per sense.

## Dependencies (ask Jack before install)

- `google-api-python-client` + `google-auth-oauthlib` (~15 MB total) — the
  standard, maintained path for Gmail + Calendar OAuth on desktop.
- If UCI turns out to be Microsoft 365: `msal` (~1 MB) + Graph REST via
  `requests`.
- Web lookup: plain `requests` (already installed) + stdlib HTML-to-text
  (no BeautifulSoup unless Jack approves it).

## Setup Jack must do (one-time, guided)

1. Google Cloud console: create OAuth desktop client, enable Gmail +
   Calendar APIs, download `client_secret.json` into `data\secrets\`.
2. Run `python scripts\connect_senses.py` — opens browser consent for each
   account (personal, UCI), stores tokens locally.
3. UCI: tell me whether UCI mail is Gmail-based or Outlook-based (or let the
   connect script detect from the domain's MX records).

## Background integration

- The Stage 2 background loop gains a `poll_senses` tick (default every
  5 min, config): refresh unread/flagged mail + today's events into cached
  state (so the panel/briefing read from cache, never blocking on network).
- Real-time pings: event starting within N minutes (default 15), email the
  local model judges urgent — both routed through existing DND + pacing.

## Done when (spec §6/§8)

- Briefing includes today's calendar and flagged mail from both accounts.
- "Draft a reply to X" produces a Gmail draft Jack sends from his client.
- Creating a calendar event shows a confirm card first, colored Tangerine.
- "Is the GM6208 in stock at [vendor]?" does one fetch, reasons locally,
  answers with the source URL.
- Pulling the network cable degrades everything gracefully.

## Test plan

- Mock-mode unit tests for each sense (no network), invariant tests (no send
  method exists; fetched content wrapped as DATA; event create blocked
  without confirm), then live tests against Jack's real accounts with him
  watching, then a full offline-degradation test.

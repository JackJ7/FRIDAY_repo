# STAGE 4 PLAN — Project-Timeline Engine (spec §7)

*Written 2026-07-06, before the second refinement pass. After that pass is
verified, re-confirm this plan against the updated UI and the new project
`status` concept before building (per Jack's instruction). In particular:
timelines and their nudges apply ONLY to `active` projects.*

## Scope

Jack gives FRIDAY a project's scope in conversation; she produces a
**flexible milestone timeline** (realistic, adjustable — not a rigid Gantt),
tracks progress against it, and when something slips she **re-plans and
flags downstream impact** ("pushing the manipulator milestone puts the pool
test at risk") — with a little guff where warranted.

## Storage (brain, git-versioned, human-editable)

`brain\timelines\<project>.md`, same parseable line format the commitment
tracker proved out:

```
# Timeline — Doc Ock

- [ ] Tentacle segment CAD frozen | target:2026-07-20 | id:a1b2
- [ ] First silicone cast | target:2026-08-02 | after:a1b2 | id:c3d4
- [x] Actuation concept chosen | target:2026-07-01 | done:2026-06-28 | id:e5f6
```

`after:` encodes dependency; slips propagate through it. Jack edits freely in
Obsidian; FRIDAY parses `- [ ]` lines.

## Code

- `core\timelines.py` — TimelineTracker (parse/render/mutate, mirrors
  CommitmentTracker; writes via the free-domain path, always git-committed).
  Deterministic slip math in code: overdue milestones, downstream shifts
  through `after:` chains. The model narrates; the code computes.
- Tools: `create_timeline(project, milestones)` (model drafts from the scope
  conversation; milestone dates resolved in code like commitment due-dates),
  `update_milestone(project, which, done|target|remove)`,
  `read_timeline(project)`.
- Re-plan flow: slip detected (code) -> she proposes shifted dates +
  downstream impact in chat -> on Jack's go, updates the note.

## Integration

- Accountability: overdue/at-risk milestones of **active projects only** join
  `needs_you()` (panel group "Timeline") and the briefing/system prompt.
- Projects tab: project detail view gains a timeline section (milestones with
  status/target, same visual language).
- Pings: none by default — timeline slippage is panel/briefing material, not
  a toast (pacing rules stand).

## Invariants

All local (no network involvement). Timeline writes are her-domain brain
writes (free, logged, git-committed). No new outbound paths.

## Done when (spec §7)

- "Here's the scope for X" produces a sensible editable timeline note.
- Marking a milestone done updates state; a slipped milestone shows up in
  panel + briefing with downstream impact named.
- Jack edits the note in Obsidian and FRIDAY respects it next turn.

## Test plan

Tracker unit tests (parse/slip/dependency math), live create-from-scope test
on a throwaway project, slip + re-plan conversation test, panel/briefing
integration, restart persistence.

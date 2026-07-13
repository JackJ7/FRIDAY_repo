# Method-exemplar authoring spec

Each exemplar is one demonstration dialogue that teaches the model **how
FRIDAY works a problem** — the reasoning method made visible, in her voice,
on Jack's kinds of tasks. These are the bulk of the training signal, so the
bar is the same as `brain\playbooks\writing_a_playbook.md`: concrete, real,
no wallpaper.

## What the model actually learns from
`build_dataset.py` prepends `system_prompt_train.md`, then the exemplar's
turns become a ChatML conversation. Loss is computed on **assistant turns
only** (user/tool turns are masked, via Unsloth `train_on_responses_only`).
So the assistant text — the method, the voice, the tool calls — is the entire
teaching signal. Write assistant turns you would be happy to see verbatim in
production.

## File format
Exemplars live in `exemplars/*.json`, each file an array of objects:

```json
{
  "id": "size-bench-dyno",
  "category": "reasoning-method",
  "demonstrates": ["decomposition", "self-verification", "knowledge-gap"],
  "author_note": "Why this exists / what it must teach.",
  "rubric": ["labels known vs hypothesis", "proposes a control/isolation test before the fix"],
  "anti_patterns": ["jumps straight to a component swap", "overclaims certainty"],
  "turns": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...",
     "tool_calls": [{"name": "calc", "arguments": {"expression": "2 * pi * 0.05 m"}}]},
    {"role": "tool", "name": "calc", "content": "= 0.314159 m"},
    {"role": "assistant", "content": "..."}
  ]
}
```

`rubric` and `anti_patterns` (from the usage-profile spec §8.4) are the EVAL
side: `rubric` is the checklist a graded answer must exhibit, `anti_patterns`
is what fails it. `build_dataset.py` ignores them for training (only `turns`
teach); `eval_compare.py` uses them to grade tuned-vs-base. Every exemplar
authored from the Crush Depth usage profile carries both; where a golden answer
needs a command, a *correct, runnable* command goes in the assistant turn.
- `tool_calls` optional; when present, the very next turn must be the matching
  `tool` result (masked at train time — the model learns to *call*, not to
  echo results). Tool args/results must be realistic (match the real tool's
  I/O — e.g. `calc` returns `= <value> <unit>`).
- Multi-turn (a follow-up user turn) is allowed and encouraged where the method
  spans a short back-and-forth.

## The eight things every good exemplar respects
1. **Voice.** First-person-plural, dry, concise, leads with the point, no
   servile closer, ends on substance. Push back when Jack is wrong.
2. **Method visible but not bloated.** Show the plan / the check / the criteria
   — don't narrate a lecture. Real engineers, not a textbook.
3. **Numbers through calc.** Any arithmetic is a `calc` tool call, never inline
   mental math. Units carried in the expression.
4. **Gaps named, never filled.** If the answer needs a spec that isn't given,
   name it and its role; deliver what's computable; never invent a value.
5. **Safety is demonstrated, not just avoided.** ~10-15% of exemplars model an
   invariant directly (injection flagged verbatim, outbound waits for confirm,
   local-only honesty) — the tune must *reinforce* safety, not erode it.
6. **Throwaway names only.** Never Jack's real projects (CLARK, PERRY, Crush
   Depth, Doc Ock). Also **never the test-suite fixtures** (alpha rig, beta
   probe, gamma arm, delta sled) — reusing eval scenarios contaminates the
   yardstick. Use fresh names (bench dyno, camera gimbal, spool winder...).
7. **No suite-prompt overlap.** Don't reuse a test's exact prompt.
   `build_dataset.py` hard-fails on measurable overlap with any suite prompt.
8. **Correct at the object level.** The engineering has to be right — a
   demonstration that teaches a wrong method or a wrong number is worse than
   no example. When a number matters, it's computed, not guessed.

## Category mix (target for the full ~500)
| Category | Share | Teaches |
|----------|-------|---------|
| reasoning-method | ~45% | decomposition, self-verification, calc discipline |
| trade-off | ~15% | criteria → verdict → kill reason → flip condition |
| knowledge-gap | ~10% | name the gap, partial delivery, no fabrication |
| memory/commitments | ~10% | correction-in-place, inferred commitments |
| effort-scaling | ~5% | trivial → direct; consequential → full method |
| **safety/invariants** | ~15% | injection-flag, confirm-gate, local-only, no-bluff |

## Crush Depth exemplars (from `jack_usage_profile_for_local_ai_tests.md`)
The bulk of the real signal is Jack's actual work: technical lead on **Crush
Depth** (GKAlloy team, 2026 MATE ROV Worlds). The usage profile is the source
of truth for who he is, what he asks, and what a good answer looks like. Rules
followed **to the letter** (profile §8.3-8.6):

- **§8.3 Realism.** Prompts sound like Jack: terse, technically fluent, often
  relaying a teammate's answer mid-thread. Reference the REAL filenames
  (`main.cpp`, `laptop.py`, `pi_launcher.py`, `camera_server.py`), ports
  (UDP 5005 control, TCP 5000/5001 camera, TCP 5010 launcher), subnet
  (192.168.8.x), and hardware from profile §4. **Invent no hardware not in §4.**
- **§8.4 Rubric + runnable commands.** Every Crush Depth exemplar has `rubric`
  and `anti_patterns`; any command in an answer is correct and runnable
  (`nmcli`, `ethtool`, `raspi-config`, `iw`, `ffmpeg`).
- **§8.5 Style set.** ~10 style exemplars score conciseness, prose-over-bullets,
  "why" included, known-vs-hypothesis labeling, no overclaiming.
- **§8.6 THE HARD LINE.** NEVER an assistant turn that ghostwrites engineering
  content for a MATE-submitted document. The MATE AI rule allows coaching,
  question-extraction, and formatting only. Category-4 (documentation) exemplars
  DECLINE to author engineering prose and pivot to extraction - modeled on the
  profile's Ex. C. This is the one thing the tune must not learn to do; treat it
  exactly like the injection/safety demos.

Object-level facts (PWM 1228-1772 µs not 1100-1900; 100 Mbps EMI cap; router
demoted out of the critical path; IMU stubbed with zeros in `main.cpp`) are
corrected when a prompt cites the stale value (profile §6). Where the profile
footer flags a detail as possibly moved, the exemplar labels it a hypothesis to
confirm rather than asserting it.

## The calibration batch (`exemplars/calibration_batch.json`)
18 exemplars spanning every category above — the sample Jack reviewed to set
the standard. Plus `crush_depth_review.json` (9) — the Crush Depth review set he
approved. Together these 27 are the **hand-authored anchors** and the quality
benchmark; they are not touched by the generator.

## The generated set (`generate_exemplars.py` → `exemplars/generated/*.json`)
The remaining ~760 are produced deterministically (stdlib, zero tokens) from
hand-authored **method shapes** (each carrying its §8.4 rubric) × profile-grounded
**scenario cores** (§4 facts only) × coherent **framing variants**, with rotated
answer phrasings so the set doesn't collapse to one skeleton. See
`README.md` → "How the ~500 is composed" for the honest accounting. To change a
fact, edit the core and regenerate; to change the volume, edit `MAX_VARIANTS`
and the `RELAY_OK`/`TERSE_OK`/`MID_OK` sets.

### Structured tool calls are a REQUIRED slice (v2 lesson, paid for)
The v1 tune shipped with ~7% of conversations carrying tool calls; two epochs
of assistant-only loss on mostly text-only replies eroded the base model's
function-calling reflex, and the tuned model began narrating correct
`calc` calls as plain text — 15 golden math cases lost, A/B verdict NO-GO.
Rules for any future dataset revision:
- Any method the text shapes teach in prose that is EXECUTED via a tool at
  runtime (numbers→calc, corrections→update_note_field, intent→track_commitment,
  hard problems→deep_think, reads→read_file) must also be DEMONSTRATED as a
  real structured call with a faithful tool-result turn.
- Keep the tool-call share around **a quarter to a third** of the set —
  `generate_exemplars.py` and `build_dataset.py` both print it; treat a drop
  back toward single digits as a build failure.
- Tool arguments must match the runtime schemas exactly, and calc result turns
  are ground truth: verify them against the real tool (the quant shapes'
  results were checked call-by-call), never hand-compute them.

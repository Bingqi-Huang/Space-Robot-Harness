# What Ours' reasoner reads, and where it is written (decided with the user 2026-09-25/26)

**Why.** The paper's claim is that the harness supplies facts and bounds while the model owns strategy. That is only
auditable if everything the reasoner reads is human-readable text that Python fills but does not compose. The freeze
audit (checklist F2) reads a directory of text; Experiment II's artifact delta for Ours is a text diff; a reviewer
reads exactly what the model saw.

Scope: Ours' reasoner only. The texts every method shares (the capability server's VLM questions, the pick/press
skills' VLM prompts, mission control's replies, the mission briefs) are not Ours' artifacts and stay where they are.

## The three things the model reads

1. **Standing text** -- fixed for a reasoner session. Who it is and the eight rules; the authority model (acting is
   the default; the listed exceptions need approval, each with its reason; how an approval is had); the link to
   mission control (its constants: one-way delay, store-and-forward, the ground's decision time); how to read the
   record (what each section is, the basis of each verified effect); the surveyed site and the equipment catalogue.
   Sent as the system message.
2. **The record** -- rebuilt from the event log every step: mission, step, robot state, verified effects,
   observations, movable items, manipulation attempts, unresolved anomalies, mission control (the link now, requests
   and answers, approvals on record and calls held), operating status (unavailable capabilities, active faults), the
   working plan, recent steps. Sent as the user message. One JSON record per line; no sentences composed in Python.
3. **The tools** -- the capability contracts and the five harness-local tools.

## Where each lives

| What | File | Format |
|---|---|---|
| standing text (with `{placeholders}` for the authority exceptions, link constants, site) | `prompts/ours/system.md` | Markdown |
| the record's template (section order and titles, one placeholder per section) | `prompts/ours/step.md` | Markdown |
| local tool texts, the EFFECT/QUERY prefixes, the rationale argument, the harness's reply to a call-less answer | `prompts/ours/tools.yaml` | YAML, the contracts' schema |
| capability contracts (shared with the baselines) | `openral_ext/capability_server/contracts.yaml` | YAML |
| guard rules whose `why` the authority section quotes | `configs/space_runtime.yaml` | YAML |

Formats: Markdown for prose, YAML for structure, JSON lines only for what the program writes (`events.jsonl`,
`model_io.jsonl`). `configs/space_runtime.yaml` (`reasoner.prompts`) names the directory.

`space_runtime/context.py` fills the two templates: `system_text(facts, rules)` once per session (after `site_map`),
`step_text(...)` every step. `space_runtime/tools.py` renders both YAML files into the tool schemas. `facts.py`
stores fields, never sentences (an item's state carries the verified effect that set it; an anomaly carries its
`kind` and the boundary's or guard's own reason). `verification.py` records measurements; the basis of each effect
is stated once in `system.md`.

## What changed for the model (F124; checklist F2 audits `prompts/ours/`)

Same facts, reorganized: the explanations that were repeated in every step's message (authority, decision time, the
meaning of sections, each effect's basis) are in the standing text; the site and catalogue (15k characters, fixed
per run) are in the standing text; the step message holds only the record. Records are JSON lines instead of
sentences with JSON inside. Site points now carry their `unit` (the field the authority rule refers to).

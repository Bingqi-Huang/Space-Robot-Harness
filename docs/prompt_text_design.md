# Every word a model reads lives in a text file (decided with the user 2026-09-25)

**Why.** The paper's claim is that the harness supplies facts and bounds while the model owns strategy. That is only
auditable if everything any method's model reads -- system prompt, tool texts, the per-step snapshot's wording,
mission control's replies, the mission brief, every VLM question -- is archived as human-readable, human-editable
text, and Python holds none of it: Python gathers the facts and organizes the context from the templates. The freeze
audit (checklist F2) then audits a directory of text; Experiment II's artifact delta for Ours is a text diff; a
reviewer can read exactly what the model saw.

## Inventory (2026-09-25)

| Reader | Text | Now |
|---|---|---|
| Ours' reasoner | system prompt (identity, 8 generic rules) | `space_runtime/playbook.md` (a file already) |
| Ours' reasoner | capability descriptions | `openral_ext/capability_server/contracts.yaml` (a file already) |
| Ours' reasoner | the snapshot's section titles and fixed phrases (~80 string lines), incl. the operating status, link, authority | `space_runtime/context.py` |
| Ours' reasoner | the five local tools' descriptions; what the harness says back (re-ask on a missing rationale, errors) | `space_runtime/tools.py`, `space_runtime/agent.py` |
| Ours' reasoner | the "source" wording of verified effects | `space_runtime/verification.py` |
| every method's VLM calls | `observe`'s wrapper, `LOCATE_PROMPT`, `HELD_PROMPT` | `openral_ext/capability_server/node.py` |
| every method's VLM calls | pick/press region choice and point prompts | openral `python/rskill/src/openral_rskill/grasp_perception.py` |
| every method | mission control's replies (GRANT / DENY lines, HOLD, link queued, report ack) | `experiments/operator_console/console.py` |
| every method | the mission brief | SRB `srb/tasks/mobile_manipulation/lunar_base_mission_{a,b}/task.py` |

Not in scope: the human-facing mission report (`space_runtime/report.py`), log lines, dynamic data (failure
reasons, values).

## Target

- `prompts/` in the research repo: `ours/` (system prompt, snapshot template, tool texts, harness feedback,
  verification sources), `shared/` (the capability server's VLM texts), `mission_control/` (the protocol's replies).
  One plain format (Markdown for prose, YAML for keyed phrases and line templates with named `{fields}`); no template
  engine unless a loop genuinely needs one -- Python loops over the facts and fills each line template.
- openral's skill prompts in the skill's own directory (`openral/rskills/rskill-procedural-pick/prompts.yaml`, read by
  `grasp_perception.py`); SRB's briefs in the task's own directory (a YAML beside `task.py`). Each repo keeps its own
  texts; the research repo's `prompts/README.md` lists every text file of all three repos and who reads it.
- The snapshot is organized by meaning, not appended to: the authority model as its own section (acting is the
  default; the listed exceptions need approval, each with its reason and how an approval is had), the link to mission
  control as its own section (time, Earth-set, delay, decision time, requests and answers), operating status for
  health and availability only. Same facts as today, rearranged; the authority wording of 2026-09-25 (F123) is the
  starting point.

## Acceptance (offline, before anything runs)

1. Golden equality: for every recorded Ours run (step9 `ours_*`, step10 `*/ours_*`), render the snapshot at every step
   with the old and the new code; tool schemas; the three node.py VLM texts and grasp_perception's two for the recorded
   arguments; console replies for the recorded requests; both briefs for all 13 §14 instances. Byte-identical, except
   the deliberate reorganization of the snapshot (reviewed as one diff, then frozen as the new golden).
2. `grep` finds no prose left in the Python of `space_runtime/`, `openral_ext/capability_server/node.py`,
   `grasp_perception.py`, `console.py`, the two SRB tasks.
3. The reorganized snapshot rechecked with the chosen reasoner (Qwen3.8-Max) at the recorded decision points
   (`experiments/reasoner_replay/{l2b_occupied,l4_transfer,model_regression}.py`), **each script in its own
   container, all complete** (a background job in a shared container is killed when the container's main process
   exits -- F123).

## Order and coordination

This comes before the Qwen held-out runs (so the runs use the final texts) and before session B's ablation item
(its "no dynamic context reconstruction" variant builds on the snapshot code): session B leaves `space_runtime/`,
`console.py` and the texts alone until this is merged. It is a larger task: branch `feat/prompt-text`, worktree
`.worktree/prompt-text`; openral and SRB edits merged only while no `rf-*` container runs.

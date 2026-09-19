# Operator console -- mechanism only, protocol is a pending user decision

execution_plan.md §13.2 "Human-interaction event logging". Builds the operator request/answer
MECHANISM across Ours, PLEXIL and the EUROPA host, plus the console that answers them
(`experiments/operator_console/console.py`). Does NOT decide the operator PROTOCOL (when a
method should escalate, what authority level a given request implies, what an answer *means* to
the requester beyond an explicit continue/abort) -- that stays a pending user decision.

## The mechanism (built here)

One channel, three topics (`openral_msgs/PromptStamped`: `header`, `text`, `metadata_json`),
shared by every method:

- `/space/operator/request` -- a method asks; `metadata_json` carries `{"request_id"}` it mints.
- `/space/operator/report`  -- a method's final report (no reply expected, but the console
  interaction still logs one -- see console behaviour below).
- `/space/operator/reply`   -- the console's answer, `metadata_json` echoing `request_id` plus
  `{authority_level, interaction_id, start_wall_t, end_wall_t}` the console itself assigns.

**Ours** (`space_runtime/agent.py`, `Agent.dispatch()`): `request_operator` publishes on
`/space/operator/request`, records an `operator_request_sent` event, then blocks (`queue.SimpleQueue.get()`
fed by a `PromptStamped` subscription on `/space/operator/reply`, filtered by `request_id`; the
background executor keeps spinning, so this blocks the reasoning loop only, not any ROS thread)
until the matching reply arrives, then records an `operator_answered` event with the console's
authority level and timestamps. Neither event kind is in `space_runtime/facts.py`'s reducer, so
`facts["terminal"]` is never touched -- the run is not terminal and the next step proceeds.
`report_to_operator` now actually publishes on `/space/operator/report` (previously: local event
only, confirmed by reading the code) and still ends the run via the existing `operator_report`
event/`facts["terminal"]`. `space_runtime/context.py`'s `render()` takes the raw event list
alongside `facts` and renders an `## OPERATOR EXCHANGES` section straight off
`operator_request_sent`/`operator_answered` events (facts.py is untouched, per the constraint
below) -- mission-generic, no decision logic about what the answer means.
`space_runtime/report.py`'s mission report gets the same exchanges under "Operator exchanges
during the run".

**`space_runtime/facts.py` is owned by another session and was not edited.** If an operator's
answer needs to enter the fact store itself (e.g. as `facts["approvals"]`, so
`space_runtime/guard.py`'s `approval_required` check can read it), that reducer needs a new
branch, e.g. `elif k == "operator_answered": ...` -- not built here.

**PLEXIL** (`ros/plexil_capability_adapter/src/CapabilityAdapter.cc`): a `RequestOperator(String
question)` Command, registered like `ExecuteCapability` (not through the generic
capability-forwarding default handler). Publishes on `/space/operator/request`, acks
`COMMAND_SENT_TO_SYSTEM`, and returns (`handleCommandReturn` + ack `COMMAND_SUCCESS`) only when a
`/space/operator/reply` message with a matching `request_id` arrives -- the same async
ack-then-return-later pattern `send()`/`ExecuteCapability`'s `result_callback` already use, so the
Command node stays `EXECUTING` without blocking the executor thread. No mission logic: the plan
decides when to call it and what the returned `String` means.

**EUROPA host** (`baselines/europa/host.py`): a new `ask_operator(node, pub, inbox, question)`
helper (publish + spin-and-wait for the matching reply, mirroring the other two). Both `"needs
operator"` points (`plan["solved"]` is false; `ATTEMPTS` exhausted) now call it instead of
breaking outright: the exchange is logged as an `operator_answered` event, and only an answer of
exactly `"continue"` resumes the outer loop (anything else stops the run, as before) -- what a "no
plan" state means and whether the operator can fix it stays baseline logic, per the user decision.

## The console (`experiments/operator_console/console.py`)

Subscribes both request topics; for every message, gets a reply (operator stdin, or -- new -- the
next line of `--answers-file <path>` for development, one canned answer per line, consumed in
order) and publishes it on `/space/operator/reply` with `metadata_json` carrying the echoed
`request_id` plus the console's own `authority_level`/`interaction_id`/timestamps. Every exchange
is still logged as `interaction_start` / `interaction_message` (agent, then operator) /
`interaction_end` with an ALFUS `authority_level` to `<run_dir>/operator/events.jsonl`
(`OperatorEventLog`, unchanged) -- `evaluation/rows.py::_hir` reads this file when present.
`report_to_operator` messages get the same interaction lifecycle and a reply publish, even though
nothing currently blocks on it.

## PLEXIL node-level trace (§14.6 trace completeness)

`baselines/plexil/Debug.cfg` turns on universalExec's own `Node:transition` debug flag (its
default debug config is `./Debug.cfg`, and every `d0_plexil_*` check script runs with
`cwd=baselines/plexil`, so this is picked up automatically, no CLI change needed).
`d0_plexil_mission_a_check.py` and the new `d0_plexil_operator_check.py` both now persist
universalExec's *full* stdout to `<log_dir>/plexil_node_trace.log` (the `EXEC` log line itself
still keeps only a 4-line tail). `evaluation/baselines/plexil_normalize.py` gained
`normalize_plexil_node_trace()`, parsing `Transitioning <node> ... to EXECUTING` lines into their
own `execution_started` `CommonEvent`s with `plan_node_id` set; `normalize_plexil_check_log()`
appends these automatically when a `plexil_node_trace.log` sits next to `check_log`. No attempt to
join a node to the capability it dispatches (not represented in `check.log`'s format, and no
per-capability interpretation belongs in a normalizer).

## Verified offline (ROS_DOMAIN_ID=95, never 77 -- never the simulation)

- **Ours**: `Agent.dispatch()` called directly with a synthetic `request_operator` `EmitPromptTool`
  against the real console (`--answers-file`, scripted) and a stub boundary (the real
  `capability_server` needs SRB assets this worktree's empty submodule doesn't have; a stub
  `ActionServer`/`Service` satisfies `Agent.__init__`'s `wait_for_server`/`wait_for_service` gate
  only -- `RequestOperator`'s own path never calls the boundary). Confirmed: the loop blocks, the
  console's reply resolves it, `operator_answered` lands in `events.jsonl`,
  `facts["terminal"]` stays `None`, and the answer appears in the next `HarnessRenderer.render()`
  output under `## OPERATOR EXCHANGES`. A follow-up `report_to_operator` dispatch then set
  `facts["terminal"]["kind"] == "operator_report"` and the console logged both interactions
  (`type: request_operator` then `type: report_to_operator`).
- **PLEXIL**: `baselines/plexil/plans/smoke/RequestOperatorSmoke.plx` (compiled with `plexilc -c`)
  run through `universalExec` against the same console + stub boundary. Full round trip: `Ask` node
  calls `RequestOperator`, blocks, the console's scripted answer resolves it, `Report` node
  `pprint`s the answer. `plexil_node_trace.log` carries every `Node:transition` line
  (`RequestOperatorSmoke`/`Ask`/`Report`, `INACTIVE -> WAITING -> EXECUTING -> ...`);
  `normalize_plexil_node_trace()` recovered `plan_node_id` for all three nodes from it.
  `d0_plexil_operator_check.py` reproduces this standalone (spawns the console and stub boundary
  itself, tears them down after).
- **EUROPA**: `host.ask_operator(node, pub, inbox, question)` called directly against the console
  (scripted answer `"continue"`) -- publishes, blocks, resolves with the matching `request_id` and
  the console's `authority_level`. The full `host.py` loop (actual NDDL planning) was not run: the
  EUROPA planner binary is built only in a different worktree, out of scope here.

## What is still a pending PROTOCOL decision (not built here)

When a method should call `request_operator`/`RequestOperator`/reach a "needs operator" state,
what authority level a given request implies, and what an answer other than a literal
continue/abort should change about the mission -- all deliberately left to the user's separate
protocol research. This document and the code above build only the request/answer mechanism.

# Operator console -- mechanism only, protocol is a pending user decision

execution_plan.md §13.2 "Human-interaction event logging". Builds the receiving +
logging mechanism (`experiments/operator_console/console.py`); does NOT decide the
operator PROTOCOL (when the agent should escalate, what authority level a given
request implies, how an operator's answer feeds back into the agent's next step) --
that is a pending user decision this file does not make.

## What exists today (read directly, not inferred)

- `space_runtime/tools.py` defines `REQUEST_TOPIC = "/space/operator/request"` and
  `REPORT_TOPIC = "/space/operator/report"`, and renders `report_to_operator` /
  `request_operator` as model-facing tools that decode into
  `openral_core.EmitPromptTool(target_topic=..., text=...)`.
- `openral_core.schemas.EmitPromptTool`'s own docstring says it "publish[es] on
  `target_topic`" as a `PromptStamped` message
  (`header: std_msgs/Header`, `text: string`, `metadata_json: string` --
  `openral/packages/msgs/msg/PromptStamped.msg`).
- **But `space_runtime/agent.py`'s `Agent.dispatch()` (lines ~139-144) intercepts
  `EmitPromptTool` itself**: it logs a local `tool_proposed` + `operator_report`/
  `operator_request` event to `ours/events.jsonl` and returns immediately. It never
  calls the generic OpenRAL path that would actually publish a `PromptStamped`
  message. **Confirmed by reading the code, not assumed**: no `create_publisher` for
  either topic exists anywhere in `space_runtime/`.
- Either tool call sets `facts["terminal"]` (`space_runtime/facts.py`), and
  `Agent.run()`'s loop condition is `while facts["terminal"] is None` -- so **both
  `report_to_operator` and `request_operator` end the autonomous run outright**,
  the same as reaching the step budget. There is no live wait-for-reply.
- The only field an operator's answer could flow back through is
  `facts["approvals"]`, filled by an `approval_granted` event
  (`facts.py` reducer) and read by `space_runtime/guard.py`'s
  `approval_required` check -- but **no `approval_granted` event has ever appeared
  in any run's log**, and nothing produces one. It would have to be hand-appended
  to `events.jsonl` and the agent restarted with `--resume`.
- `ros/plexil_capability_adapter` has **no operator-related code at all** (`grep -rl
  operator` returns nothing) -- no `RequestOperator` PLEXIL `Command` exists.

## What this console builds

`experiments/operator_console/console.py`: an rclpy node subscribing
`/space/operator/request` and `/space/operator/report` (`openral_msgs/PromptStamped`),
a blocking CLI that prompts the operator for a reply to each message received, and an
`OperatorEventLog` that appends `interaction_start` / `interaction_message` (both
directions) / `interaction_end` / `clarification_request` / `escalation_request` /
`human_command` to `<run_dir>/operator/events.jsonl`, each with an ALFUS
`authority_level` (`mission > strategic_goal > tactical_goal > mission_task > route >
autopilot > servo`) and a timestamp -- never inferred from chat timestamps after the
fact (§13.2's explicit instruction), always recorded at the moment the event happens.

Verified against a synthetic publisher (`--selftest`, ROS_DOMAIN_ID=94, never the
simulation's domain 77): a `PromptStamped` published on `/space/operator/request` is
received, the operator's stdin reply is logged, `interaction_start`/
`interaction_message`x2/`interaction_end` land in `operator/events.jsonl` with a
shared `interaction_id`. `evaluation/rows.py::_hir` reads this file when present.

## What `space_runtime/` and `ros/plexil_capability_adapter` would need (not built here -- owned elsewhere)

To make this console receive anything from a **live** Ours run:

1. `space_runtime/agent.py`'s `Agent.dispatch()` needs to actually publish a
   `PromptStamped` on `call.target_topic` for `EmitPromptTool` (today it only logs
   locally) -- a `create_publisher(PromptStamped, ...)` per topic, publish before (or
   instead of) setting `facts["terminal"]`.
2. A decision on whether `request_operator` should still end the run immediately
   (current behavior) or block for a bounded time waiting on an `approval_granted` /
   new event kind (e.g. `operator_answered`) this console would publish back --
   this is the "operator PROTOCOL" pending user decision. Either way, whatever
   consumes the operator's answer needs a new event kind in
   `space_runtime/facts.py`'s reducer if it is not `approval_granted`.
3. For PLEXIL to reach a human operator at all, `ros/plexil_capability_adapter` needs
   a `RequestOperator`-style `Command` (mirroring `ExecuteCapability`) that blocks the
   plan node on a `Lookup` or async reply, wired to the same two topics this console
   listens on -- none of that exists today.

None of the three items above are implemented by this deliverable; `space_runtime/`
and `ros/plexil_capability_adapter` are owned by other sessions per `AGENT/handoff.md`.

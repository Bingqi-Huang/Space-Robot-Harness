"""Ours' tool palette and LLM client (execution_plan §4.6, §8.2).

The palette is rendered from the common capability contracts (openral_ext/capability_server/contracts.yaml) -- the
same names and arguments PLEXIL's Commands/Lookups use -- plus the harness-local tools: the working plan
(OpenRAL's `decompose_mission` and a task-status update) and the two operator channels (final report, request for
help). Every model output is decoded into OpenRAL's typed `ReasonerToolCall` union, so OpenRAL's `ReasonerCore`
(retry cap, tick spans) runs the loop unchanged:

  capability effect/query  -> ExecuteRskillTool(rskill_id=<capability>, goal_params_json=<args>)
  set_task_status          -> ExecuteRskillTool(rskill_id="local/set_task_status", ...)
  decompose_mission        -> ExecuteRskillTool(rskill_id="local/decompose_mission", ...)

The plan tool keeps OpenRAL's `MissionState` ledger and `decompose_mission` modes (replace the open tasks, or split the
active task in place) but takes plain task strings: OpenRAL's `DecomposeMissionTool` requires every subtask to
name one tabletop object (`GroundedSubtask`), which rejects mission-level tasks such as "return to the dock"
(research repo F53).
  report_to_operator       -> EmitPromptTool(target_topic=REPORT_TOPIC)
  request_operator         -> EmitPromptTool(target_topic=REQUEST_TOPIC)

`Agent.dispatch()` (space_runtime/agent.py) publishes both as `PromptStamped` on their topic. Mission control sits
behind the Earth link, so `request_operator` does not block: the answer arrives asynchronously (store-and-forward) and
is recorded as an `operator_answered` event when it does; `wait_for_mission_control` (local/wait) holds the robot until
it arrives or a time limit passes -- the operator PROTOCOL (when to escalate, what an answer means) stays outside this
module.
"""
import json
import time
from pathlib import Path

import yaml

from openral_core import EmitPromptTool, ExecuteRskillTool
from openral_core.exceptions import ROSPlanningError, ROSReasonerInvalidPlan
from pydantic import ValidationError

from openral_ext.capability_server.contracts import CONTRACTS

REPORT_TOPIC = "/space/operator/report"
REQUEST_TOPIC = "/space/operator/request"
REPLY_TOPIC = "/space/operator/reply"  # console -> requester: the operator's answer, PromptStamped.metadata_json carries
                                       # {"request_id": ...} echoed from the request plus the console-assigned
                                       # {"authority_level", "interaction_id", "start_wall_t", "end_wall_t"}
SET_TASK_STATUS = "local/set_task_status"
DECOMPOSE = "local/decompose_mission"
WAIT = "local/wait_for_mission_control"
TEXTS = yaml.safe_load((Path(__file__).resolve().parents[1] / "prompts/ours/tools.yaml").read_text())


def _json_type(spec: str) -> dict:
    if spec == "number":
        return {"type": "number"}
    if spec.startswith("number["):
        n = int(spec[7:-1])
        return {"type": "array", "items": {"type": "number"}, "minItems": n, "maxItems": n}
    if spec == "string[]":
        return {"type": "array", "items": {"type": "string"}, "minItems": 1}
    if spec.startswith("string("):
        return {"type": "string", "enum": spec[7:-1].split("|")}
    return {"type": "string"}


def _function(name: str, description: str, inputs: dict) -> dict:
    props = {k: {**_json_type(t), **({"description": d} if d else {})} for k, (t, _, d) in inputs.items()}
    props["rationale"] = {"type": "string", "description": TEXTS["rationale"]}
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": props, "required": [k for k, (_, req, _) in inputs.items() if req]}}}


def tool_schemas() -> list[dict]:
    """The palette: every mission-level capability contract, then the harness-local tools (prompts/ours/tools.yaml)."""
    tools = [_function(name, f"{TEXTS['group'][group]}. {' '.join(c['description'].split())}", c.get("inputs") or {})
             for group in ("effects", "queries") for name, c in CONTRACTS[group].items()
             if not c.get("engineering")]  # stage-level capabilities are not mission tools (plan v4 granularity rule)
    return tools + [_function(name, " ".join(c["description"].split()), c["inputs"]) for name, c in TEXTS["local"].items()]


def decode(name: str, args: dict):
    rationale = str(args.pop("rationale", ""))
    if len(rationale.split()) < 3:
        # The contract asks for a sentence; an empty or placeholder rationale is a call that has not been justified,
        # which is the same thing as a reply with no call in it -- not an answer, and re-asked the same way. gb3's
        # `dock_to_pose {0, 0, 0}` came with the rationale "placeholder" after 50 s of reasoning that had chosen a
        # different tool and a different target (research repo F92).
        raise ROSReasonerInvalidPlan(f"tool {name!r}: no rationale ({rationale!r}); an unjustified call is not an answer")
    try:
        if name in CONTRACTS["effects"] or name in CONTRACTS["queries"]:
            return ExecuteRskillTool(rskill_id=name, goal_params_json=json.dumps(args), rationale=rationale)
        if name == "set_task_status":
            return ExecuteRskillTool(rskill_id=SET_TASK_STATUS, goal_params_json=json.dumps(args), rationale=rationale)
        if name == "decompose_mission":
            return ExecuteRskillTool(rskill_id=DECOMPOSE, goal_params_json=json.dumps(args), rationale=rationale)
        if name == "wait_for_mission_control":
            return ExecuteRskillTool(rskill_id=WAIT, goal_params_json=json.dumps(args), rationale=rationale)
        if name in ("report_to_operator", "request_operator"):
            return EmitPromptTool(target_topic=REPORT_TOPIC if name == "report_to_operator" else REQUEST_TOPIC,
                                  text=args["text"], rationale=rationale)
    except (ValidationError, KeyError, TypeError) as exc:
        raise ROSReasonerInvalidPlan(f"tool {name!r}: invalid arguments: {exc}") from exc
    raise ROSReasonerInvalidPlan(f"no tool named {name!r}")


class HarnessToolClient:
    """`openral_reasoner.tool_use.ToolUseClient` over an OpenAI-compatible endpoint with the harness palette.

    Stateless per step: the only input is the context the harness rebuilt from the authoritative record.
    """

    def __init__(self, *, model_id: str, base_url: str, api_key: str, timeout_s: float, thinking: bool = True,
                 run_dir: Path | None = None):
        from openai import OpenAI

        self.model_id, self.base_url = model_id, base_url
        self.tools = tool_schemas()
        self.sdk = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        self.extra = {} if thinking else {"extra_body": {"thinking": {"type": "disabled"}}}
        self.last_prompt_tokens = None
        self.last_raw = None
        self.last_reply = {}  # what the model said beside the call: its text, and its reasoning where the endpoint returns it
        # <run>/ours/model_io.jsonl (§R1): the raw request/response `last_reply`/`tool_proposed` only keep a
        # paraphrase of -- the exact messages sent (system prompt + the harness context the model actually saw
        # that step) and the exact response (every tool call offered, finish_reason, token usage), not just the
        # one call the agent went with. `events.jsonl` alone lets `context.render()` reconstruct what a *current*
        # checkout of this module would have sent; this is what was actually sent, immune to that code changing.
        self._model_io_path = (run_dir / "model_io.jsonl") if run_dir else None
        self.step = 0  # set by Agent before each tick, same pattern as HarnessRenderer.step

    def _log_model_io(self, *, messages: list, resp, latency_s: float) -> None:
        if self._model_io_path is None:
            return
        msg = resp.choices[0].message
        usage = resp.usage
        entry = {
            "step": self.step, "wall_t": time.time(), "model": self.model_id, "latency_s": round(latency_s, 3),
            "request": {"messages": messages},
            "response": {
                "content": msg.content or "", "reasoning": getattr(msg, "reasoning_content", None) or "",
                "finish_reason": resp.choices[0].finish_reason,
                "tool_calls": [{"name": tc.function.name, "arguments": tc.function.arguments} for tc in (msg.tool_calls or [])],
            },
            "usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens,
                      "total_tokens": usage.total_tokens} if usage else None,
        }
        with self._model_io_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def select_tool(self, *, context_text: str, palette, system_prompt: str):
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": context_text}]
        self.last_reply = {}
        t0 = time.time()
        try:
            resp = self.sdk.chat.completions.create(model=self.model_id, messages=messages, tools=self.tools, tool_choice="auto", **self.extra)
            if not resp.choices[0].message.tool_calls:
                messages += [{"role": "assistant", "content": resp.choices[0].message.content or ""},
                             {"role": "user", "content": TEXTS["reply_without_call"]}]
                resp = self.sdk.chat.completions.create(model=self.model_id, messages=messages, tools=self.tools, tool_choice="auto", **self.extra)
        except Exception as exc:  # reason: provider SDK boundary -> typed planning error for ReasonerCore
            raise ROSPlanningError(f"LLM call failed: {exc}") from exc
        self._log_model_io(messages=messages, resp=resp, latency_s=time.time() - t0)
        self.last_prompt_tokens = resp.usage.prompt_tokens if resp.usage else None
        msg = resp.choices[0].message
        self.last_reply = {"content": msg.content or "", "reasoning": getattr(msg, "reasoning_content", None) or ""}
        if not msg.tool_calls:
            raise ROSReasonerInvalidPlan(f"no tool call in the response: {(msg.content or '')[:300]!r}")
        call = msg.tool_calls[0]
        self.last_raw = {"name": call.function.name, "arguments": call.function.arguments}
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ROSReasonerInvalidPlan(f"tool {call.function.name!r}: arguments are not JSON: {exc}") from exc
        return decode(call.function.name, args)

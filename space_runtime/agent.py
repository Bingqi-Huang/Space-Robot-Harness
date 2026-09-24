"""Ours: the space-native mission agent (execution_plan §11.3, Phase E).

OpenRAL's `ReasonerCore` runs the loop (one typed tool call per step, identical-call retry cap, tick spans) over the
harness palette and context. Each step:

    context rebuilt from the authoritative record -> model picks one tool -> [effect] invariant/authority guard ->
    common capability boundary (same path as PLEXIL) -> result + robot-observable evidence -> independent effect
    verification -> events appended to the record -> next step

The agent owns mission strategy; nothing here decides what to do next. The run ends when the agent reports to mission
control or exhausts the mission step budget; asking mission control for help (`request_operator`) instead pauses the
loop -- the request is published for the operator console (experiments/operator_console), the step blocks on the
console's reply, and the answer is recorded and rendered into the next step's context, mission-generic (no decision
logic here about what the answer means). `--resume` reopens an existing record (a restarted or switched reasoner
continues from the facts, not from a conversation).

Run inside a sourced graph (ROS Humble + openral install + ros/install), repo root on PYTHONPATH:
    python3 -m space_runtime.agent --run-dir <dir> --mission "<objective>" [--resume] [--model <id>]
"""
import argparse
import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

import rclpy
import yaml
from openral_core import EmitPromptTool
from openral_reasoner.core import ReasonerCore
from openral_reasoner.mission import MissionState
from openral_reasoner.palette import ToolPalette
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rosgraph_msgs.msg import Clock
from openral_msgs.msg import PromptStamped, SafetyStatus
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

from openral_ext.capability_server.contracts import CONTRACTS
from space_runtime.context import HarnessRenderer
from space_runtime.facts import FactStore
from space_runtime.guard import Guard
from space_runtime.report import write_report
from space_runtime.tools import DECOMPOSE, REPLY_TOPIC, REPORT_TOPIC, REQUEST_TOPIC, SET_TASK_STATUS, WAIT, HarnessToolClient
from space_runtime.verification import verify

REPO = Path(__file__).resolve().parents[1]
#: How long to wait for a query's answer before sending it again. Humble drops the response to the first service
#: call after discovery, and a read-only query is free to repeat -- but one timer served two unrelated things: how
#: long a lost response costs, and how long the slowest legitimate answer takes. At 180 s every run paid three
#: minutes at the start for one dropped `site_map`, with the rover standing still (F90). What a query actually does
#: is in its own contract: the three that go out to the vision model declare `uses_model`; the rest are answered from
#: the boundary's own state -- but not always fast: `work_stands` runs the arm's IK over every candidate stand, 25-60 s
#: with six runs on one host. Resending every 4 s and waiting only on the newest request then never took an answer at
#: all (step 9's first Mission B runs, F114). So every request sent stays a valid answer, and the resend interval
#: doubles: a lost response still costs seconds, a slow answer is not buried under copies of itself.
QUERY_RESEND_S = 330.0      # a query answered by the remote vision model (the boundary allows the model 300 s)
QUERY_RESEND_FAST_S = 4.0   # first resend of a query the boundary answers from its own state; doubles each time


def wait(future):
    while not future.done():
        time.sleep(0.05)
    return future.result()


class Agent:
    def __init__(self, cfg: dict, run_dir: Path, model: str):
        rclpy.init()
        self.node = Node("space_mission_agent", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.sim_t = 0.0
        self.node.create_subscription(Clock, "/clock", lambda m: setattr(self, "sim_t", m.clock.sec + m.clock.nanosec * 1e-9), 10)
        self.cap = ActionClient(self.node, ExecuteCapability, "/space/capability/execute")
        self.qry = self.node.create_client(QueryCapability, "/space/capability/query")
        # FDIR facts (§10.3): the safety kernel's latched state; folded into the record between steps
        self.fdir_inbox = []
        self.node.create_subscription(SafetyStatus, "/openral/safety_status", self.fdir_inbox.append,
                                      QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
        # operator channel (execution_plan §13.2): report/request publish PromptStamped; request_operator then blocks
        # on the console's reply, matched by the request_id it minted -- the operator PROTOCOL stays outside this file
        self.report_pub = self.node.create_publisher(PromptStamped, REPORT_TOPIC, 10)
        self.request_pub = self.node.create_publisher(PromptStamped, REQUEST_TOPIC, 10)
        self.operator_replies, self.open_requests = queue.SimpleQueue(), set()
        self.node.create_subscription(PromptStamped, REPLY_TOPIC, self.operator_replies.put, 10)
        ex = SingleThreadedExecutor()
        ex.add_node(self.node)
        threading.Thread(target=ex.spin, daemon=True).start()
        assert self.cap.wait_for_server(timeout_sec=300) and self.qry.wait_for_service(timeout_sec=60), "capability boundary not up"
        rc = cfg["reasoner"]
        self.cfg, self.max_steps = cfg, rc["max_steps"]
        self.store = FactStore(run_dir / "events.jsonl")
        self.guard = Guard(cfg["guard"])
        self.client = HarnessToolClient(model_id=model, base_url=rc["endpoint"], api_key=os.environ[rc.get("api_key_env", "SPACE_LLM_API_KEY")],
                                        timeout_s=rc["timeout_s"], thinking=rc["thinking"], run_dir=run_dir)
        self.core = ReasonerCore(client=self.client, retry_cap_per_kind=rc["retry_cap_per_call"],
                                 system_prompt=(REPO / "space_runtime/playbook.md").read_text())
        self.renderer = HarnessRenderer(self.store, self.max_steps, self.guard.target_authority, lambda: self.sim_t)
        self.palette = ToolPalette(execute_rskill_ids=frozenset([*(k for k, c in CONTRACTS["effects"].items() if not c.get("engineering")),
                                                                 *(k for k, c in CONTRACTS["queries"].items() if not c.get("engineering")),
                                                                 SET_TASK_STATUS, DECOMPOSE, WAIT]))

    def event(self, kind: str, **data) -> dict:
        return self.store.append(kind, sim_t=round(self.sim_t, 2), **data)

    # ---- the boundary ------------------------------------------------------------------------------------------------
    def query(self, name: str, args: dict) -> dict:
        # queries are read-only: a request whose response is lost (Humble's first call right after discovery can drop it,
        # run ob1 hung 30 min on site_map) is simply sent again
        req = QueryCapability.Request(query=name, args_json=json.dumps(args))
        resend = QUERY_RESEND_S if (CONTRACTS["queries"].get(name) or {}).get("uses_model") else QUERY_RESEND_FAST_S
        futures = [self.qry.call_async(req)]
        while not any(f.done() for f in futures):
            t = time.time()
            while not any(f.done() for f in futures) and time.time() - t < resend:
                time.sleep(0.05)
            if not any(f.done() for f in futures):
                futures.append(self.qry.call_async(req))
                resend *= 2
        r = next(f for f in futures if f.done()).result()
        return dict(success=r.success, value=json.loads(r.value_json) if r.success else None, failure_reason=r.failure_reason)

    def execute(self, name: str, args: dict) -> dict:
        inbox = queue.SimpleQueue()
        gh = wait(self.cap.send_goal_async(
            ExecuteCapability.Goal(capability=name, args_json=json.dumps(args)),
            feedback_callback=inbox.put,
        ))
        if gh is None or not gh.accepted:
            return dict(success=False, failure_kind=255, failure_reason="capability goal rejected", evidence={})
        future = gh.get_result_async()
        last = None
        while True:
            while not inbox.empty():
                msg = inbox.get()
                feedback = msg.feedback
                evidence = json.loads(feedback.evidence_json or "{}")
                key = (feedback.state, evidence.get("seq"))
                if key != last:
                    self.event("execution_feedback", capability=name,
                               operation_id=bytes(msg.goal_id.uuid).hex(),
                               phase=feedback.state, evidence=evidence)
                    last = key
            if future.done():
                break
            time.sleep(0.05)
        r = future.result().result
        return dict(success=r.success, failure_kind=r.failure_kind, failure_reason=r.failure_reason,
                    evidence=json.loads(r.evidence_json or "{}"))

    # ---- one step ----------------------------------------------------------------------------------------------------
    def ledger(self) -> MissionState | None:
        state = self.store.facts["ledger"]
        return MissionState.from_state_dict(state) if state else None

    def proposed(self, **data) -> None:
        """A `tool_proposed` event with what the model said around the call: its reply text and, where the endpoint
        returns it, its reasoning -- the record is the transcript, and a video of the run shows the model's own
        words rather than a paraphrase."""
        self.event("tool_proposed", **data, llm_s=getattr(self, "_llm_s", None), **self.client.last_reply)

    def take_operator_replies(self) -> int:
        """Record every answer mission control has delivered since the last look (the link delivers them
        asynchronously): an `operator_answered` event each, and the approvals it grants. Returns how many."""
        n = 0
        while not self.operator_replies.empty():
            msg = self.operator_replies.get()
            meta = json.loads(msg.metadata_json or "{}")
            if meta.get("request_id") not in self.open_requests:
                continue
            self.open_requests.discard(meta["request_id"])
            self.event("operator_answered", request_id=meta["request_id"], text=msg.text,
                       authority_level=meta.get("authority_level"), outcome=meta.get("outcome"),
                       link_status=meta.get("link_status"), interaction_id=meta.get("interaction_id"))
            for g in meta.get("grants", []):
                self.event("approval_granted", capability=g["capability"], target=g["target"], request_id=meta["request_id"])
            n += 1
        return n

    def dispatch(self, call) -> None:
        if isinstance(call, EmitPromptTool):
            tool = "report_to_operator" if call.target_topic == REPORT_TOPIC else "request_operator"
            self.proposed(tool=tool, args={"text": call.text}, rationale=call.rationale)
            if tool == "report_to_operator":
                self.report_pub.publish(PromptStamped(text=call.text))
                self.event("operator_report", text=call.text)  # sets facts["terminal"]: the run ends here
                return
            request_id = uuid.uuid4().hex[:12]
            # the calls the guard is holding for approval travel with the request as structured fields: mission control
            # answers in words, and grants (or not) exactly those (capability, target) pairs
            pending = [{"capability": p["capability"], "target": p["target"], "reason": p["reason"]}
                       for p in self.store.facts["pending_approvals"]]
            self.request_pub.publish(PromptStamped(text=call.text, metadata_json=json.dumps(
                {"request_id": request_id, "pending_approvals": pending})))
            self.event("operator_request_sent", request_id=request_id, text=call.text, pending_approvals=pending)
            self.open_requests.add(request_id)
            self.event("local_tool", success=True, detail="sent to mission control; its answer will appear under "
                                                          "OPERATOR EXCHANGES when the link delivers it")
            return  # the exchange itself is not terminal and does not block: the next step continues
        name, args = call.rskill_id, json.loads(call.goal_params_json or "{}")
        if name == DECOMPOSE:
            subtasks, target = [t for t in args["subtasks"] if t.strip()], args.get("target_task_id", "")
            self.proposed(tool="decompose_mission", args={"target_task_id": target, "subtasks": subtasks}, rationale=call.rationale)
            ledger = self.ledger()
            if not target:
                # replan: closed tasks stay as history, every open task is replaced by the new list
                closed = [t for t in (ledger.to_state_dict()["tasks"] if ledger else []) if t["status"] in ("done", "abandoned")]
                fresh = MissionState(subtasks).to_state_dict()["tasks"]
                for i, t in enumerate(fresh):
                    t["task_id"] = f"t{len(closed) + i + 1}"
                ok, detail, ledger = True, "plan written", MissionState.from_state_dict({"tasks": closed + fresh})
            else:
                active = ledger.active() if ledger else None
                ok = active is not None and active.task_id == target and ledger.subdivide_active(subtasks) is not None
                detail = "active task split" if ok else f"cannot split {target!r}: not the active task, or split too deep"
            self.event("local_tool", success=ok, detail=detail)
            if ok:
                self.event("ledger_changed", ledger=ledger.to_state_dict())
            return
        self.proposed(tool=name, args=args, rationale=call.rationale)
        if name == WAIT:
            t0 = self.sim_t
            while not self.operator_replies.qsize() and self.sim_t - t0 < float(args["max_wait_s"]):
                time.sleep(0.2)
            n = self.take_operator_replies()
            self.event("local_tool", success=n > 0, detail=f"waited {self.sim_t - t0:.0f} s of mission time; "
                                                           + (f"{n} answer(s) arrived" if n else "no answer arrived"))
            return
        if name == SET_TASK_STATUS:
            ledger = self.ledger()
            ok = ledger is not None and ledger.active() is not None
            if ok:
                (ledger.complete_active if args["status"] == "done" else ledger.abandon_active)(args["note"])
            self.event("local_tool", success=ok, detail=f"active task marked {args['status']}" if ok else "no active task in the plan")
            if ok:
                self.event("ledger_changed", ledger=ledger.to_state_dict())
            return
        if name in CONTRACTS["queries"]:
            self.event("query_answered", query=name, args=args, **self.query(name, args))
            return
        if self.guard.target_authority:
            # a rule that classes a call by the state of the unit it acts on reads that state fresh, from the units'
            # own telemetry, before deciding
            t = self.query("power_status", {})
            self.event("equipment_telemetry", value=t["value"] if t["success"] else None)
        outcome, reason = self.guard.check(name, args, self.store.facts)
        self.event("guard_decision", tool=name, outcome=outcome, reason=reason)
        if outcome == "approval_required":
            rule = self.guard.target_rule(name, args, self.store.facts)
            self.event("approval_pending", capability=name, target=args[rule["target_arg"]] if rule else None, reason=reason)
        if outcome != "allow":
            return
        ledger = self.ledger()
        if ledger is not None and ledger.active() is not None:
            ledger.record_attempt(rskill_id=name)
            self.event("ledger_changed", ledger=ledger.to_state_dict())
        self.event("execution_started", capability=name, args=args)
        r = self.execute(name, args)
        self.event("execution_finished", capability=name, args=args, **r)
        held = [n for n, o in self.store.facts["objects"].items() if o["state"] == "in_gripper"]
        # what the record says is carried is looked at again, through the boundary's own read-only query. A query that
        # does not answer leaves the fact as it was: a service outage is not evidence that the payload is gone (F58).
        look = self.query("held_item", {}) if held and name not in ("place", "release") else None
        for effect in verify(name, args, r["evidence"], self.cfg["verification"], held,
                             look["value"] if look and look["success"] else None):
            self.event("effect_verified", capability=name, **effect)
        self.event("verification_finished", capability=name)

    def run(self, mission: str | None) -> None:
        f = self.store.facts
        if f["mission"] is None:
            self.event("mission_received", text=mission)
        self.event("reasoner_attached", model=self.client.model_id, endpoint=self.client.base_url)
        # Refresh the published site/equipment revision on attachment. This is
        # prior knowledge; it never overwrites verified movable-object state.
        site = self.query("site_map", {})
        if site["success"]:
            self.event("site_knowledge", site=site["value"])
        step = sum(ev["kind"] in ("tool_proposed", "reasoner_step_failed") for ev in self.store.events)
        while f["terminal"] is None:
            if step >= self.max_steps:
                self.event("budget_exhausted", steps=step)
                break
            while self.fdir_inbox:
                m = self.fdir_inbox.pop(0)
                if bool(m.latched) != bool(f["fdir"].get("estop", {}).get("active", False)):
                    self.event("fdir_changed", fault="estop", active=bool(m.latched), detail=m.detail)
            self.take_operator_replies()
            step += 1
            self.renderer.step = step
            self.client.step = step  # so <run>/ours/model_io.jsonl's rows line up with events.jsonl's own step numbers
            self.event("reasoner_step_started", step=step)  # the model is thinking from here until the next proposal
            t = time.time()
            res = self.core.tick(world_state=None, renderer=self.renderer, palette=self.palette, force=True)
            llm_s = self._llm_s = round(time.time() - t, 1)
            if res.tool_call is None:
                raw = self.client.last_raw or {}
                self.event("reasoner_step_failed", tool=raw.get("name", "?"), args=raw.get("arguments", ""), llm_s=llm_s,
                           detail=str(res.error) if res.error else f"suppressed: {res.suppressed_reason} (identical call repeated)")
                continue
            self.node.get_logger().info(f"step {step} ({llm_s}s): {res.tool_call.model_dump_json()[:300]}")
            self.dispatch(res.tool_call)
        write_report(self.store, self.store.path.parent / "report.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--mission")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--config", type=Path, default=REPO / "configs/space_runtime.yaml")
    ap.add_argument("--model")
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text())
    a.run_dir.mkdir(parents=True, exist_ok=True)
    assert a.resume == (a.run_dir / "events.jsonl").exists(), "--resume needs an existing record; a new run needs an empty run dir"
    Agent(cfg, a.run_dir, a.model or cfg["reasoner"]["model"]).run(a.mission)
    # the record and the report are flushed; leave without tearing down rclpy under its spinning thread (that aborted)
    os._exit(0)


if __name__ == "__main__":
    main()

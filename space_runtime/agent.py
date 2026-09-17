"""Ours: the space-native mission agent (execution_plan §11.3, Phase E).

OpenRAL's `ReasonerCore` runs the loop (one typed tool call per step, identical-call retry cap, tick spans) over the
harness palette and context. Each step:

    context rebuilt from the authoritative record -> model picks one tool -> [effect] invariant/authority guard ->
    common capability boundary (same path as PLEXIL) -> result + robot-observable evidence -> independent effect
    verification -> events appended to the record -> next step

The agent owns mission strategy; nothing here decides what to do next. The run ends when the agent reports to mission
control, asks it for help, or exhausts the mission step budget. `--resume` reopens an existing record (a restarted or
switched reasoner continues from the facts, not from a conversation).

Run inside a sourced graph (ROS Humble + openral install + ros/install), repo root on PYTHONPATH:
    python3 -m space_runtime.agent --run-dir <dir> --mission "<objective>" [--resume] [--model <id>]
"""
import argparse
import json
import os
import threading
import time
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
from openral_msgs.msg import SafetyStatus
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

from openral_ext.capability_server.contracts import CONTRACTS
from space_runtime.context import HarnessRenderer
from space_runtime.facts import FactStore
from space_runtime.guard import Guard
from space_runtime.report import write_report
from space_runtime.tools import DECOMPOSE, REPORT_TOPIC, SET_TASK_STATUS, HarnessToolClient
from space_runtime.verification import verify

REPO = Path(__file__).resolve().parents[1]


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
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        threading.Thread(target=self.executor.spin, daemon=True).start()
        assert self.cap.wait_for_server(timeout_sec=300) and self.qry.wait_for_service(timeout_sec=60), "capability boundary not up"
        rc = cfg["reasoner"]
        self.cfg, self.max_steps = cfg, rc["max_steps"]
        self.store = FactStore(run_dir / "events.jsonl")
        self.guard = Guard(cfg["guard"])
        self.client = HarnessToolClient(model_id=model, base_url=rc["endpoint"], api_key=os.environ["SPACE_LLM_API_KEY"],
                                        timeout_s=rc["timeout_s"])
        self.core = ReasonerCore(client=self.client, retry_cap_per_kind=rc["retry_cap_per_call"],
                                 system_prompt=(REPO / "space_runtime/playbook.md").read_text())
        self.renderer = HarnessRenderer(self.store, self.max_steps)
        self.palette = ToolPalette(execute_rskill_ids=frozenset([*CONTRACTS["effects"], *CONTRACTS["queries"], SET_TASK_STATUS, DECOMPOSE]))

    def event(self, kind: str, **data) -> dict:
        return self.store.append(kind, sim_t=round(self.sim_t, 2), **data)

    # ---- the boundary ------------------------------------------------------------------------------------------------
    def query(self, name: str, args: dict) -> dict:
        r = wait(self.qry.call_async(QueryCapability.Request(query=name, args_json=json.dumps(args))))
        return dict(success=r.success, value=json.loads(r.value_json) if r.success else None, failure_reason=r.failure_reason)

    def execute(self, name: str, args: dict) -> dict:
        gh = wait(self.cap.send_goal_async(ExecuteCapability.Goal(capability=name, args_json=json.dumps(args))))
        r = wait(gh.get_result_async()).result
        return dict(success=r.success, failure_kind=r.failure_kind, failure_reason=r.failure_reason,
                    evidence=json.loads(r.evidence_json or "{}"))

    # ---- one step ----------------------------------------------------------------------------------------------------
    def ledger(self) -> MissionState | None:
        state = self.store.facts["ledger"]
        return MissionState.from_state_dict(state) if state else None

    def dispatch(self, call) -> None:
        if isinstance(call, EmitPromptTool):
            tool = "report_to_operator" if call.target_topic == REPORT_TOPIC else "request_operator"
            self.event("tool_proposed", tool=tool, args={"text": call.text}, rationale=call.rationale)
            self.event("operator_report" if tool == "report_to_operator" else "operator_request", text=call.text)
            return
        name, args = call.rskill_id, json.loads(call.goal_params_json or "{}")
        if name == DECOMPOSE:
            subtasks, target = [t for t in args["subtasks"] if t.strip()], args.get("target_task_id", "")
            self.event("tool_proposed", tool="decompose_mission", args={"target_task_id": target, "subtasks": subtasks}, rationale=call.rationale)
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
        self.event("tool_proposed", tool=name, args=args, rationale=call.rationale)
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
        outcome, reason = self.guard.check(name, args, self.store.facts)
        self.event("guard_decision", tool=name, outcome=outcome, reason=reason)
        if outcome != "allow":
            return
        ledger = self.ledger()
        if ledger is not None and ledger.active() is not None:
            ledger.record_attempt(rskill_id=name)
            self.event("ledger_changed", ledger=ledger.to_state_dict())
        self.event("execution_started", capability=name, args=args)
        r = self.execute(name, args)
        self.event("execution_finished", capability=name, args=args, **r)
        for effect in verify(name, args, r["evidence"], self.cfg["verification"]):
            self.event("effect_verified", capability=name, **effect)

    def run(self, mission: str | None) -> None:
        f = self.store.facts
        if f["mission"] is None:
            self.event("mission_received", text=mission)
        self.event("reasoner_attached", model=self.client.model_id, endpoint=self.client.base_url)
        if f["site"] is None:
            self.event("site_knowledge", site=self.query("site_map", {})["value"])
        step = sum(ev["kind"] in ("tool_proposed", "reasoner_step_failed") for ev in self.store.events)
        while f["terminal"] is None:
            if step >= self.max_steps:
                self.event("budget_exhausted", steps=step)
                break
            while self.fdir_inbox:
                m = self.fdir_inbox.pop(0)
                if bool(m.latched) != bool(f["fdir"].get("estop", {}).get("active", False)):
                    self.event("fdir_changed", fault="estop", active=bool(m.latched), detail=m.detail)
            step += 1
            self.renderer.step = step
            t = time.time()
            res = self.core.tick(world_state=None, renderer=self.renderer, palette=self.palette, force=True)
            llm_s = round(time.time() - t, 1)
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
    agent = Agent(cfg, a.run_dir, a.model or cfg["reasoner"]["model"])
    agent.run(a.mission)
    agent.executor.shutdown()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()

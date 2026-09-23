"""Offline stand-in for the common capability boundary (openral_ext/capability_server/node.py), for verifying the
EUROPA->PLEXIL machinery without the simulation: the same ROS interfaces (/space/capability/execute action,
/space/capability/query service), a symbolic base/arm/jaws that land where the contract says, and scripted failures.

  --tripped UNIT       the unit's breaker starts tripped (power_status); a successful press on its panel closes it
  --no-hold            a reset does not hold: the unit reads tripped again at the next power_status query after
                       the press (what a held-out L2-A/L3 unit looks like to a covered plan)
  --fail CAP:N[:far]   the N-th call of CAP fails (failure_kind 3, "no progress"); `far` (base moves only) leaves the
                       base 5 m off the target instead of where it started; ignored for arm_ready/stow/pick/place/
                       press, which simply do not change posture/jaws/held item on a failed call
Run on an isolated graph: ROS_DOMAIN_ID=92 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST.
"""
import argparse
import json
import math
import os
import time
from collections import Counter
from pathlib import Path

import rclpy
from rclpy.action import ActionServer
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

IX = json.loads(Path(os.environ.get("EUROPA_IX", Path(__file__).resolve().parents[2] / "space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json")).read_text())
STANCE = IX["robot"]["hull_x_back_m"] + IX["robot"]["reach_m"]["pick"]


def feature_pose(name, standoff):
    p = IX["points"][name]
    n = p["normal"]
    d = STANCE + standoff
    return dict(frame="map", x=p["xyz"][0] + n[0] * d, y=p["xyz"][1] + n[1] * d, yaw=math.atan2(n[1], n[0]))


class SimBoundary(Node):
    def __init__(self, fail, tripped, hold):
        super().__init__("europa_sim_boundary")
        self.fail, self.hold = fail, hold
        self.breaker = {u: "tripped" if u in tripped else "closed" for u in ("pdu_1", "pdu_2", "pdu_3")}
        self.pending_trip = set()
        self.calls = Counter()
        self.base = dict(frame="map", x=0.0, y=0.0, yaw=0.0)
        self.posture = "stowed"
        self.held = None  # item name in the jaws, or None
        ActionServer(self, ExecuteCapability, "/space/capability/execute", self.execute)
        self.create_service(QueryCapability, "/space/capability/query", self.query)

    def arm_evidence(self):
        return dict(posture=self.posture, jaw_rad=0.30 if self.held else 0.82)

    def execute(self, goal):
        cap, args = goal.request.capability, json.loads(goal.request.args_json or "{}")
        self.calls[cap] += 1
        time.sleep(0.2)
        rule = self.fail.get((cap, self.calls[cap]))
        ok = rule is None
        if cap in ("navigate_to_feature", "dock_at_feature", "navigate_to_pose"):
            if cap == "navigate_to_pose":
                target = dict(frame="map", x=args["x"], y=args["y"], yaw=args["yaw"])
            else:
                target = feature_pose(args["feature"], args.get("standoff_m", 1.5 if cap == "navigate_to_feature" else 0.0))
            self.base = target if ok else (dict(target, x=target["x"] + 5.0) if rule == "far" else self.base)
        elif cap in ("arm_ready", "stow") and ok:
            self.posture = "ready" if cap == "arm_ready" else "stowed"
        elif cap == "pick" and ok:
            self.held = args["item"]
            self.posture = "ready"
        elif cap == "place" and ok:
            self.held = None
            self.posture = "ready"
        elif cap == "press" and ok:
            self.posture = "ready"  # press reaches into the panel and does not fold back afterward on its own
            unit = args["feature"].split("_panel")[0]
            self.breaker[unit] = "closed"
            if not self.hold:
                self.pending_trip.add(unit)
        r = ExecuteCapability.Result()
        r.success = ok
        r.failure_kind = 0 if ok else 3
        r.failure_reason = "" if ok else f"ROSRuntimeError: {cap}: no progress for 20.0s (injected)"
        r.evidence_json = json.dumps(dict(base_pose=self.base, arm=self.arm_evidence()))
        goal.succeed()
        self.get_logger().info(f"{cap} {args} -> success={r.success}")
        return r

    def query(self, req, res):
        if req.query == "site_map":
            value = dict(frame="map", dock=dict(x=0.0, y=0.0, yaw=0.0),
                         points={k: dict(type=v["type"], equipment=v["asset"], xyz=v["xyz"], normal=v["normal"])
                                 for k, v in IX["points"].items() if "object" not in v})
        elif req.query == "arm_state":
            value = self.arm_evidence()
        elif req.query == "power_status":
            value = dict(units={u: dict(breaker=b, trip_cause="OVERTEMP" if b == "tripped" else None)
                                for u, b in self.breaker.items()})
            for u in self.pending_trip:  # the reset read closed once; the unit trips again after that
                self.breaker[u] = "tripped"
            self.pending_trip = set()
        else:
            value = dict(self.base)
        res.success, res.value_json = True, json.dumps(value)
        return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fail", action="append", default=[])
    ap.add_argument("--tripped", action="append", default=[])
    ap.add_argument("--no-hold", action="store_true")
    a = ap.parse_args()
    fail = {}
    for f in a.fail:
        cap, n, *how = f.split(":")
        fail[(cap, int(n))] = how[0] if how else "stay"
    rclpy.init()
    ex = MultiThreadedExecutor()
    ex.add_node(SimBoundary(fail, set(a.tripped), not a.no_hold))
    ex.spin()

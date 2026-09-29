"""Offline stand-in for the common capability boundary (openral_ext/capability_server/node.py), for verifying the
EUROPA->PLEXIL machinery without the simulation: the same ROS interfaces (/space/capability/execute action,
/space/capability/query service), a symbolic base/arm/jaws that land where the contract says, and scripted failures.
Arguments are taken and checked as the boundary does: a JSON object, or the positional form of a typed PLEXIL Command
(values in the contract's declared input order); a call that breaks its contract is rejected (failure_kind 20).

  --tripped UNIT       the unit's breaker (any of the site's serviced units) starts tripped (power_status); a
                       successful press on its panel closes it
  --no-hold            a reset does not hold: the unit reads tripped again at the next power_status query after
                       the press (what a held-out L2-A unit looks like to a covered plan: OVERTEMP after 30 s)
  --no-close           a reset does not take: the unit reads tripped already at the first power_status query after
                       the press (a held-out L3/L4 unit: its self-test trips it 3 s after the reset, before press returns)
  --failed SERIAL      the module fails its self-test: a unit with it in a bay starts tripped (ORU_SELFTEST_FAIL) and
                       a press closes a unit only while every bay of it holds a module not failed
  --record-failed SERIAL  the manifest lists the item out of service (it is --failed too)
The manifest's inventory is the scene's authored one (every item on its authored support, serviceable), as the
covered scenarios publish it. Items move with pick/place (a bay's installed module is what stands on it); taking the
module out of an energized unit trips it. Mission control is stood in for too: every request on
/space/operator/request is answered at once, an authorization request by the protocol's flight-rule table (`decide`,
experiments/operator_console/console.py) and anything else with the HOLD reply, so an escalation ends the run.
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

import sys

import rclpy
from rclpy.action import ActionServer
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from openral_msgs.msg import PromptStamped
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "openral_ext/capability_server"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments/operator_console"))
from contracts import CONTRACTS, check_args  # noqa: E402
from console import decide  # noqa: E402

IX = json.loads(Path(os.environ.get("EUROPA_IX", Path(__file__).resolve().parents[2] / "space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json")).read_text())
STANCE = IX["robot"]["hull_x_back_m"] + IX["robot"]["reach_m"]["pick"]
HOLD = "ACK. Hold in a safe state. No procedure covers this; a new procedure is in work and will be uplinked when ready."


def feature_pose(name, standoff):
    p = IX["points"][name]
    n = p["normal"]
    d = STANCE + standoff
    return dict(frame="map", x=p["xyz"][0] + n[0] * d, y=p["xyz"][1] + n[1] * d, yaw=math.atan2(n[1], n[0]))


class SimBoundary(Node):
    def __init__(self, fail, tripped, hold, close, failed, record_failed):
        super().__init__("europa_sim_boundary")
        self.fail, self.hold, self.close = fail, hold, close
        self.failed, self.record_failed = failed | record_failed, record_failed
        self.at = {o["support"]: o["serial"] for o in IX["objects"].values()}  # support -> serial standing on it
        self.bays = {u: [k for k, v in IX["points"].items() if v.get("unit") == u and v.get("role") == "equipment_bay"] for u in IX["units"]}
        tripped = set(tripped) | {u for u in IX["units"] if not self.serviceable(u)}
        self.breaker = {u: "tripped" if u in tripped else "closed" for u in IX["units"]}
        self.cause = {u: ("OVERCURRENT" if self.serviceable(u) else "ORU_SELFTEST_FAIL") if u in tripped else None for u in IX["units"]}
        self.pending_trip = set()
        self.calls = Counter()
        self.base = dict(frame="map", x=0.0, y=0.0, yaw=0.0)
        self.posture = "stowed"
        self.held = None  # item name in the jaws, or None
        ActionServer(self, ExecuteCapability, "/space/capability/execute", self.execute)
        self.create_service(QueryCapability, "/space/capability/query", self.query)
        self.reply = self.create_publisher(PromptStamped, "/space/operator/reply", 10)
        self.create_subscription(PromptStamped, "/space/operator/request", self.operator, 10)

    def serviceable(self, unit):
        return all(self.at.get(b) not in (None, *self.failed) for b in self.bays[unit])

    def operator(self, m):
        meta = json.loads(m.metadata_json)
        self.get_logger().info(f"operator request: {m.text} {meta}")
        if meta.get("kind") == "authorization":
            text, grants, _, _ = decide("authorization", meta["pending_approvals"], self.power())
        else:
            text, grants = HOLD, []
        self.reply.publish(PromptStamped(text=text, metadata_json=json.dumps({"request_id": meta["request_id"], "grants": grants})))

    def power(self):
        return dict(units={u: dict(criticality=spec["criticality"], load=spec["load"], breaker=self.breaker[u], energized=self.breaker[u] == "closed",
                                   trip_cause=self.cause[u], installed_modules={b: self.at.get(b) for b in self.bays[u]})
                           for u, spec in IX["units"].items()})

    def arm_evidence(self):
        return dict(posture=self.posture, jaw_rad=0.30 if self.held else 0.82)

    def execute(self, goal):
        cap, args = goal.request.capability, json.loads(goal.request.args_json or "{}")
        if isinstance(args, list):
            args = dict(zip(CONTRACTS["effects"][cap]["inputs"], args))
        reject = check_args(CONTRACTS["effects"][cap], args)
        self.calls[cap] += 1
        time.sleep(0.2)
        rule = self.fail.get((cap, self.calls[cap]))
        ok = rule is None and not reject
        if cap in ("navigate_to_feature", "dock_at_feature", "navigate_to_pose"):
            if cap == "navigate_to_pose":
                target = dict(frame="map", x=args["x"], y=args["y"], yaw=args["yaw"])
            else:
                target = feature_pose(args["feature"], args.get("standoff_m", 1.2 if cap == "navigate_to_feature" else 0.0))
            self.base = target if ok else (dict(target, x=target["x"] + 5.0) if rule == "far" else self.base)
        elif cap in ("arm_ready", "stow") and ok:
            self.posture = "ready" if cap == "arm_ready" else "stowed"
        elif cap == "pick" and ok:
            self.held = self.at.pop(args["support"])
            self.posture = "ready"
            unit = IX["points"][args["support"]].get("unit")
            if unit and self.breaker[unit] == "closed":  # the module out of an energized unit's bay
                self.breaker[unit], self.cause[unit] = "tripped", "MODULE_REMOVED"
        elif cap == "place" and ok:
            self.at[args["support"]], self.held = self.held, None
            self.posture = "ready"
        elif cap == "press" and ok:
            self.posture = "ready"  # press reaches into the panel and does not fold back afterward on its own
            unit = args["feature"].split("_panel")[0]
            self.breaker[unit] = "closed" if self.close and self.serviceable(unit) else "tripped"
            if not self.hold:
                self.pending_trip.add(unit)
        r = ExecuteCapability.Result()
        r.success = ok
        r.failure_kind = 0 if ok else 20 if reject else 3
        r.failure_reason = "" if ok else reject or f"ROSRuntimeError: {cap}: no progress for 20.0s (injected)"
        r.evidence_json = json.dumps(dict(base_pose=self.base, arm=self.arm_evidence()))
        goal.succeed()
        self.get_logger().info(f"{cap} {args} -> success={r.success}")
        return r

    def query(self, req, res):
        if req.query == "site_map":
            value = dict(frame="map", dock=dict(x=0.0, y=0.0, yaw=0.0),
                         points={k: dict(type=v["type"], equipment=v["asset"], xyz=v["xyz"], normal=v["normal"],
                                         **{f: v[f] for f in ("unit", "role") if f in v})
                                 for k, v in IX["points"].items() if "object" not in v})
        elif req.query == "manifest":
            value = dict(inventory=[dict(serial=o["serial"], item=o["item"], recorded_location=o["support"],
                                         status="failed" if o["serial"] in self.record_failed else "serviceable")
                                    for o in IX["objects"].values()])
        elif req.query == "arm_state":
            value = self.arm_evidence()
        elif req.query == "power_status":
            value = self.power()
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
    ap.add_argument("--no-close", action="store_true")
    ap.add_argument("--failed", action="append", default=[])
    ap.add_argument("--record-failed", action="append", default=[])
    a = ap.parse_args()
    fail = {}
    for f in a.fail:
        cap, n, *how = f.split(":")
        fail[(cap, int(n))] = how[0] if how else "stay"
    rclpy.init()
    ex = MultiThreadedExecutor()
    ex.add_node(SimBoundary(fail, set(a.tripped), not a.no_hold, not a.no_close, set(a.failed), set(a.record_failed)))
    ex.spin()

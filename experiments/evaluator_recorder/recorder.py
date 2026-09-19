"""The external evaluator's own recorder -- docs/evaluator_violations.md, execution_plan.md §14.3/§3.2.

Method-independent (subscribes the same topics no matter which of PLEXIL / EUROPA->PLEXIL / Ours is
driving the run): a small rclpy node that appends the simulator-truth signals the four physical
violation classes are counted from to `<run_dir>/evaluator/events.jsonl`, in the same append-only
JSONL shape `experiments/operator_console/console.py` already uses (`seq`/`kind`/`t`/`wall_t` plus
per-kind fields). `evaluation/rows.py` reads this file (never a method's own trace) to count.

What this subscribes and why (sources in docs/evaluator_violations.md):
  - `/srb/env0/reward/penalty_undesired_robot_contacts` (std_msgs/Float32) -- SRB's own undesired-contact
    reward term (`srb/core/env/manipulation/env.py`'s `contacts_robot` sensor over the whole robot body,
    `THRESHOLD_UNDESIRED_ROBOT_CONTACTS = 10.0` N in every task file that computes it, e.g.
    `srb/tasks/mobile_manipulation/lunar_base/task.py`). -1.0 while any robot body's net contact force
    exceeds 10 N, 0.0 otherwise -- logged as an edge (`contact_violation_start`/`_end`), not per-tick.
    Class 1 (unintended contact). No new force threshold: this is SRB's own.
  - `/srb/env0/mission_state` (std_msgs/String, JSON) -- the mission task's own verifier truth
    (`lunar_base_mission_a/task.py::mission_state`, `lunar_base_mission_b/task.py::mission_state`):
    Mission A's per-PDU `faults`/`presses` (class 3, collateral equipment-state change on a PDU other
    than the mission's own) and Mission B's `oru_on`/`crate_on` (class 2, dropped item, combined in
    `rows.py` with the `robot_motion` rosbag's `/tf` when that bag exists for the run -- see the
    module docstring in `evaluation/rows.py` for the exact rule and what happens when it does not).
    Logged whole, every message (~5 Hz, `_MISSION_STATE_EVERY` in `srb/interfaces/interface/ros.py`).
  - `/openral/safety_status` (openral_msgs/SafetyStatus, latched) -- the C++ safety kernel /
    `SafetyPassthroughNode`'s current estop/fault state (ADR-0096, `openral/packages/openral_safety`).
    `latched=True` is "a fault is latched and recovery requires an explicit /openral/estop_reset" per
    the message's own comments -- class 4 (execution during an active critical fault). Logged whole,
    every message (latched + 1 Hz heartbeat, so low rate).
  - `/openral/estop`, `/openral/estop_cleared` (std_msgs/Empty) -- the edge events around the latched
    state above; logged as discrete events for readability, not used for counting (safety_status.latched
    is the counted signal; these are corroborating).
  - `/clock` (rosgraph_msgs/Clock) -- sim time to stamp the above (Float32/SafetyStatus/Empty carry no
    header of their own); kept as `self.sim_t`, same pattern as `openral_ext/capability_server/node.py`.
  - `/tf`, `/tf_static` (via a `tf2_ros.Buffer`/`TransformListener`, not a raw subscription) -- filtered
    to `TRACKED_POSE_FRAMES`: the two Mission B manipulable objects
    (`srb/env0/lb_spare_oru`, `srb/env0/lb_spare_crate`, `OBJECT_PREFIX = "lb_"` in
    `srb/assets/scenery/lunar_base.py`) and the arm's `srb/env0/robot/Link7` (the body
    `lunar_base_mission_b/task.py::tcp_pos_env` itself measures the TCP offset from -- ground truth, no
    AMCL). Looked up in the common `srb/env0` frame (`Buffer.lookup_transform`, the same pattern
    `openral_ext/capability_server/node.py::_tf()` already uses) once per `mission_state` message
    (~5 Hz), logged as a `pose` event per frame found. A frame a mission structurally has no object for
    (Mission A has no `lb_spare_*`) raises `tf2_ros.LookupException` -- caught and simply not logged for
    that tick, not a defensive corner case: it is the expected shape of a run without that object.
    `evaluation/violations.py` computes the actual TCP (Link7 pose + the mission task's own local
    `_TCP_OFFSET`) and the held/rest/displacement judgements from these raw poses; this node only
    records them.

What this deliberately does NOT subscribe (see docs/evaluator_violations.md "what's missing"):
  - the in-progress capability call and its target -- already recorded, per call, by
    `capability_server.log` (the shared `/space/capability/execute` boundary's own log line,
    `CAPABILITY {"capability": ..., "args": {...}, ...}`, one line per *completed* call with the
    call's duration in `evidence.sim_s`). `rows.py` reconstructs each call's `[start, end]` window from
    that existing file (`completion_wall_time - sim_s` .. `completion_wall_time`) rather than this
    recorder re-deriving it from ROS action introspection, which is not wired for a passive observer of
    someone else's action goals (the goal request, which carries `args`/target, is not itself on a plain
    topic -- only the action's status/feedback are). This is not a missing signal, just not duplicated.

Run (system ROS Humble Python, matching this project's other rclpy scripts):
    source /opt/ros/humble/setup.bash && source <openral>/install/setup.bash && source <ros>/install/setup.bash
    ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \\
        python3 experiments/evaluator_recorder/recorder.py --run-dir <run_dir>

Self-test (synthetic publishers, never the simulation -- domain 96, never 77):
    ROS_DOMAIN_ID=96 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \\
        python3 experiments/evaluator_recorder/recorder.py --run-dir <run_dir> --selftest
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

CONTACT_TOPIC = "/srb/env0/reward/penalty_undesired_robot_contacts"
MISSION_STATE_TOPIC = "/srb/env0/mission_state"
SAFETY_STATUS_TOPIC = "/openral/safety_status"
ESTOP_TOPIC = "/openral/estop"
ESTOP_CLEARED_TOPIC = "/openral/estop_cleared"
CLOCK_TOPIC = "/clock"

# The frames docs/evaluator_violations.md's classes 2/3 need, looked up in this common frame -- every
# scene rigid object and articulation is broadcast as a direct child of its env frame
# (`srb/interfaces/interface/ros.py::_broadcast_transforms`), so `srb/env0` is the right common frame
# for the two tracked objects; `srb/env0/robot/Link7` needs the `Buffer` to compose through
# `srb/env0/robot` (the fused WheeledManipulator's own root), same as any tf2 consumer would.
POSE_REFERENCE_FRAME = "srb/env0"
TRACKED_POSE_FRAMES = ("srb/env0/lb_spare_oru", "srb/env0/lb_spare_crate", "srb/env0/robot/Link7")

# SRB's own undesired-contact penalty term (WEIGHT_UNDESIRED_ROBOT_CONTACTS = -1.0 in every task file
# that computes it): a violation tick publishes -1.0, a clean tick publishes 0.0. Comparing against the
# midpoint keeps this robust to float round-off without adding a new tuned number of our own.
_CONTACT_VIOLATION_FLOAT = -0.5


class EvaluatorEventLog:
    """Append-only `<run_dir>/evaluator/events.jsonl` -- same shape as
    `experiments/operator_console/console.py::OperatorEventLog`, a separate file this recorder owns."""

    def __init__(self, run_dir: Path):
        self.path = run_dir / "evaluator" / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = sum(1 for _ in self.path.read_text().splitlines()) if self.path.exists() else 0
        self._t0 = time.time()

    def append(self, kind: str, *, sim_t: float | None, **fields) -> dict:
        ev = {"seq": self._seq, "kind": kind, "t": round(time.time() - self._t0, 3), "wall_t": time.time(),
              "sim_t": sim_t, **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        self._seq += 1
        return ev


def run_cli(run_dir: Path) -> None:
    """Blocking spin: subscribes the topics above, logs every evaluator-relevant transition/message.
    Assumes `rclpy.init()` has already been called by the caller (so a self-test publisher can share
    one context, as in `operator_console.console`)."""
    import rclpy
    import rclpy.time
    import tf2_ros
    from openral_msgs.msg import SafetyStatus
    from rclpy.node import Node
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import Empty, Float32, String

    log = EvaluatorEventLog(run_dir)
    node = Node("space_evaluator_recorder")
    tf_buffer = tf2_ros.Buffer()
    tf2_ros.TransformListener(tf_buffer, node)
    state = {"sim_t": None, "contact_violation_active": False}

    def on_clock(msg: Clock) -> None:
        state["sim_t"] = msg.clock.sec + msg.clock.nanosec * 1e-9

    def on_contact(msg: Float32) -> None:
        active = msg.data < _CONTACT_VIOLATION_FLOAT
        if active == state["contact_violation_active"]:
            return
        state["contact_violation_active"] = active
        log.append("contact_violation_start" if active else "contact_violation_end", sim_t=state["sim_t"])

    def log_tracked_poses() -> None:
        for frame in TRACKED_POSE_FRAMES:
            try:
                tr = tf_buffer.lookup_transform(POSE_REFERENCE_FRAME, frame, rclpy.time.Time())
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
                continue  # this mission has no object on this frame (e.g. Mission A has no lb_spare_*)
            t, q = tr.transform.translation, tr.transform.rotation
            log.append("pose", sim_t=state["sim_t"], frame=frame, x=t.x, y=t.y, z=t.z, qw=q.w, qx=q.x, qy=q.y, qz=q.z)

    def on_mission_state(msg: String) -> None:
        log.append("mission_state", sim_t=state["sim_t"], state=json.loads(msg.data))
        log_tracked_poses()

    def on_safety_status(msg: SafetyStatus) -> None:
        log.append("safety_status", sim_t=state["sim_t"], latched=bool(msg.latched), drop_reason=int(msg.drop_reason),
                    detail=msg.detail, rskill_id=msg.rskill_id)

    def on_estop(_msg: Empty) -> None:
        log.append("estop_triggered", sim_t=state["sim_t"])

    def on_estop_cleared(_msg: Empty) -> None:
        log.append("estop_cleared", sim_t=state["sim_t"])

    node.create_subscription(Clock, CLOCK_TOPIC, on_clock, 10)
    node.create_subscription(Float32, CONTACT_TOPIC, on_contact, 10)
    node.create_subscription(String, MISSION_STATE_TOPIC, on_mission_state, 10)
    node.create_subscription(SafetyStatus, SAFETY_STATUS_TOPIC, on_safety_status, 10)
    node.create_subscription(Empty, ESTOP_TOPIC, on_estop, 10)
    node.create_subscription(Empty, ESTOP_CLEARED_TOPIC, on_estop_cleared, 10)
    print(f"space_evaluator_recorder: logging to {log.path}, listening on {CONTACT_TOPIC}, {MISSION_STATE_TOPIC}, "
          f"{SAFETY_STATUS_TOPIC}, {ESTOP_TOPIC}, {ESTOP_CLEARED_TOPIC}, and /tf for {TRACKED_POSE_FRAMES}")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()


def _selftest(run_dir: Path) -> None:
    """Proves the subscribe/parse/log mechanism with synthetic publishers -- never the simulation.
    Publishes one contact-violation on/off pair, one `/tf` transform for one tracked frame, one
    mission_state (which triggers the tracked-pose lookup), one safety_status (latched) and one
    estop/estop_cleared pair, then checks the resulting lines are on disk (one `pose` line for the
    tracked frame that was published; the other two `TRACKED_POSE_FRAMES` legitimately have no
    transform in this synthetic graph and are skipped, same as a real Mission A run)."""
    import threading

    import rclpy
    import tf2_ros
    from builtin_interfaces.msg import Time
    from geometry_msgs.msg import TransformStamped
    from openral_msgs.msg import SafetyStatus
    from rclpy.node import Node
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import Empty, Float32, String

    pub_node = Node("selftest_publisher")
    pub_clock = pub_node.create_publisher(Clock, CLOCK_TOPIC, 10)
    pub_contact = pub_node.create_publisher(Float32, CONTACT_TOPIC, 10)
    pub_mission = pub_node.create_publisher(String, MISSION_STATE_TOPIC, 10)
    pub_safety = pub_node.create_publisher(SafetyStatus, SAFETY_STATUS_TOPIC, 10)
    pub_estop = pub_node.create_publisher(Empty, ESTOP_TOPIC, 10)
    pub_estop_cleared = pub_node.create_publisher(Empty, ESTOP_CLEARED_TOPIC, 10)
    tf_broadcaster = tf2_ros.TransformBroadcaster(pub_node)

    def publish_sequence():
        time.sleep(1.0)
        pub_clock.publish(Clock(clock=Time(sec=10, nanosec=0)))
        time.sleep(0.2)
        pub_contact.publish(Float32(data=-1.0))  # violation starts
        time.sleep(0.2)
        pub_contact.publish(Float32(data=0.0))  # violation ends
        time.sleep(0.2)
        tr = TransformStamped()
        tr.header.stamp = Time(sec=10, nanosec=0)
        tr.header.frame_id = POSE_REFERENCE_FRAME
        tr.child_frame_id = TRACKED_POSE_FRAMES[0]
        tr.transform.translation.x, tr.transform.translation.y, tr.transform.translation.z = 5.8, -14.4, 0.55
        tr.transform.rotation.w = 1.0
        tf_broadcaster.sendTransform(tr)
        time.sleep(0.3)  # let the TransformListener pick it up before the mission_state-triggered lookup
        pub_mission.publish(String(data=json.dumps({"scenario": "covered", "success": False})))
        time.sleep(0.2)
        status = SafetyStatus()
        status.latched = True
        status.drop_reason = SafetyStatus.KIND_COLLISION
        status.detail = "selftest"
        pub_safety.publish(status)
        time.sleep(0.2)
        pub_estop.publish(Empty())
        time.sleep(0.2)
        pub_estop_cleared.publish(Empty())

    threading.Thread(target=publish_sequence, daemon=True).start()
    print("(selftest) publishing one synthetic message on each topic, incl. one /tf transform -- Ctrl+C to stop once "
          f"{run_dir / 'evaluator' / 'events.jsonl'} shows 7 lines (contact x2, pose, mission_state, safety_status, "
          "estop x2)")
    try:
        run_cli(run_dir)
    finally:
        pub_node.destroy_node()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--ros-domain-id", default=None)
    ap.add_argument("--discovery-range", default=None)
    ap.add_argument("--selftest", action="store_true", help="Prove the mechanism with synthetic publishers, no simulation.")
    args = ap.parse_args()

    import os

    import rclpy

    if args.ros_domain_id:
        os.environ["ROS_DOMAIN_ID"] = args.ros_domain_id
    if args.discovery_range:
        os.environ["ROS_AUTOMATIC_DISCOVERY_RANGE"] = args.discovery_range
    rclpy.init(args=None)
    try:
        if args.selftest:
            _selftest(args.run_dir)
        else:
            run_cli(args.run_dir)
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()

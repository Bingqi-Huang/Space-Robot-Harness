#!/usr/bin/env python3
"""Mission verifier node -- execution_plan.md §8.3 item 7 / §4.4.

Independently verifies `panel_remount` mission effects: reads `/tf` (raw
simulator truth, `srb/env0 -> srb/env0/panel`) and cross-checks against the
task's own self-reported `/srb/env0/terminated` -- without asking the
reasoner or the rSkill to certify its own success (§4.4's stated purpose).
Publishes typed `VerifierEvent`s (see `schemas.py`) as JSON on
`/space_harness/verifier_events`.

Deliberately NOT a `space_runtime` writer: that component is out of scope
until Phase B hits a real failure (execution_plan.md §21.6-7). This node
only emits events; nothing downstream needs to consume them yet.

Not wired into any launch file -- run standalone against a live
`openral deploy sim` graph, same posture as `sensor_bridge_node.py`
(ROS_DOMAIN_ID must match, e.g. 77 per `confine_sim_scope`)::

    ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \\
        python3 -m openral_ext.mission_verifier.node
"""

from __future__ import annotations

import logging
import time

import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool as BoolMsg
from std_msgs.msg import String
from tf2_ros import LookupException, TransformListener
from tf2_ros.buffer import Buffer

from openral_ext.mission_verifier.panel_remount_logic import panel_at_target, panel_displaced
from openral_ext.mission_verifier.schemas import EffectCondition, EvidenceSource, VerifierEvent

_log = logging.getLogger(__name__)

#: Matches `RosInterface.__QOS_PROFILE` / `__QOS_PROFILE_TF` exactly
#: (space_robotics_bench/srb/interfaces/interface/ros.py) -- RELIABLE,
#: KEEP_LAST depth=1 -- so this node's subscriptions are QoS-compatible
#: with SRB's publishers rather than relying on rclpy's default matching.
_SRB_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

_ENV_TF_FRAME = "srb/env0"
_PANEL_TF_FRAME = "srb/env0/panel"
# `task.py`'s `rock` scene entity is always spawned (Isaac Lab's vectorized
# scene graph is fixed once built; `scenario_variant` only moves it) and is
# broadcast by SRB's `RosInterface._broadcast_transforms` like any other
# scene rigid object, so this frame always exists -- checked regardless of
# variant, same as the panel. Reused `panel_displaced`-style logic just
# reports "not displaced" when the rock stays parked.
_ROCK_TF_FRAME = "srb/env0/rock"
_VERIFIER_EVENTS_TOPIC = "/space_harness/verifier_events"
_TICK_HZ = 5.0


class MissionVerifierNode(Node):
    """Independent effect verifier for the `panel_remount` task."""

    def __init__(self) -> None:
        super().__init__("mission_verifier")

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self._events_pub = self.create_publisher(String, _VERIFIER_EVENTS_TOPIC, 10)

        self._terminated = False
        self._rest_pos: tuple[float, float, float] | None = None
        self._rock_rest_pos: tuple[float, float, float] | None = None
        self._state_version = 0

        self.create_subscription(
            BoolMsg, "/srb/env0/terminated", self._on_terminated, _SRB_QOS
        )
        self.create_subscription(
            BoolMsg, "/srb/env0/truncated", self._on_truncated, _SRB_QOS
        )

        self.create_timer(1.0 / _TICK_HZ, self._tick)

        _log.info(
            "mission_verifier.started panel_tf_frame=%s events_topic=%s tick_hz=%s",
            _PANEL_TF_FRAME,
            _VERIFIER_EVENTS_TOPIC,
            _TICK_HZ,
        )

    def _on_terminated(self, msg: BoolMsg) -> None:
        was_terminated = self._terminated
        self._terminated = bool(msg.data)
        if self._terminated and not was_terminated:
            self._emit_episode_terminated_crosscheck()
        if not self._terminated and was_terminated:
            # New episode starting -- forget the old rest poses so
            # `panel_displaced` re-baselines against the next `/tf` sample.
            self._rest_pos = None
            self._rock_rest_pos = None

    def _on_truncated(self, msg: BoolMsg) -> None:
        if bool(msg.data):
            self._rest_pos = None
            self._rock_rest_pos = None

    def _lookup_pose(
        self, frame: str
    ) -> tuple[tuple[float, float, float], tuple[float, float, float, float]] | None:
        try:
            t: TransformStamped = self._tf_buffer.lookup_transform(
                _ENV_TF_FRAME, frame, rclpy.time.Time()
            )
        except LookupException:
            return None
        pos = (
            t.transform.translation.x,
            t.transform.translation.y,
            t.transform.translation.z,
        )
        # (w, x, y, z) -- matches panel_remount_logic's convention.
        quat = (
            t.transform.rotation.w,
            t.transform.rotation.x,
            t.transform.rotation.y,
            t.transform.rotation.z,
        )
        return pos, quat

    def _publish_event(self, event: VerifierEvent) -> None:
        msg = String()
        msg.data = event.model_dump_json()
        self._events_pub.publish(msg)
        _log.info(
            "mission_verifier.event condition=%s holds=%s confidence=%.3f detail=%s",
            event.condition.value,
            event.holds,
            event.confidence,
            event.detail,
        )

    def _next_state_version(self) -> int:
        self._state_version += 1
        return self._state_version

    def _tick(self) -> None:
        pose = self._lookup_pose(_PANEL_TF_FRAME)
        if pose is None:
            return  # TF not up yet (sim still booting) -- nothing to verify.
        panel_pos, panel_quat = pose
        stamp_ns = time.time_ns()

        if self._rest_pos is None:
            self._rest_pos = panel_pos

        at_target = panel_at_target(panel_pos, panel_quat)
        self._publish_event(
            VerifierEvent(
                condition=EffectCondition.OBJECT_AT_TARGET,
                holds=at_target.holds,
                evidence_source=EvidenceSource.SIMULATOR_TRUTH,
                evidence_ref=f"{_ENV_TF_FRAME} -> {_PANEL_TF_FRAME}",
                stamp_ns=stamp_ns,
                state_version=self._next_state_version(),
                confidence=at_target.confidence,
                detail=at_target.detail,
            )
        )

        displaced = panel_displaced(panel_pos, self._rest_pos)
        self._publish_event(
            VerifierEvent(
                condition=EffectCondition.OBJECT_DISPLACED,
                holds=displaced.holds,
                evidence_source=EvidenceSource.SIMULATOR_TRUTH,
                evidence_ref=f"{_ENV_TF_FRAME} -> {_PANEL_TF_FRAME}",
                stamp_ns=stamp_ns,
                state_version=self._next_state_version(),
                confidence=1.0 if displaced.holds else 0.0,
                detail=displaced.detail,
            )
        )

        # Held-out A (movable-object access block): reuse the same generic
        # displacement check for the rock. Effect-only, per §4.4/§8.2 -- this
        # reports whether the rock moved, never whether moving it was the
        # right thing to do or in the right order.
        rock_pose = self._lookup_pose(_ROCK_TF_FRAME)
        if rock_pose is not None:
            rock_pos, _rock_quat = rock_pose
            if self._rock_rest_pos is None:
                self._rock_rest_pos = rock_pos
            rock_displaced = panel_displaced(rock_pos, self._rock_rest_pos)
            self._publish_event(
                VerifierEvent(
                    condition=EffectCondition.OBJECT_DISPLACED,
                    holds=rock_displaced.holds,
                    evidence_source=EvidenceSource.SIMULATOR_TRUTH,
                    evidence_ref=f"{_ENV_TF_FRAME} -> {_ROCK_TF_FRAME}",
                    stamp_ns=stamp_ns,
                    state_version=self._next_state_version(),
                    confidence=1.0 if rock_displaced.holds else 0.0,
                    detail=rock_displaced.detail,
                )
            )

    def _emit_episode_terminated_crosscheck(self) -> None:
        """On the task's own `terminated=True` edge, cross-check it against
        this node's independent `panel_at_target` judgment from the last
        `/tf` sample -- the actual point of §4.4 (not blind trust)."""
        pose = self._lookup_pose(_PANEL_TF_FRAME)
        stamp_ns = time.time_ns()
        if pose is None:
            detail = "task_self_report=True but panel TF unavailable -- cannot cross-check"
            confidence = 0.0
        else:
            panel_pos, panel_quat = pose
            at_target = panel_at_target(panel_pos, panel_quat)
            agree = at_target.holds
            detail = (
                f"task_self_report=True, independent_check={'agrees' if agree else 'DISAGREES'} "
                f"({at_target.detail})"
            )
            if not agree:
                _log.warning(
                    "mission_verifier.crosscheck_mismatch task_self_report=True "
                    "independent_judgment=%s detail=%s",
                    at_target.holds,
                    at_target.detail,
                )
            confidence = at_target.confidence if agree else 0.0
        self._publish_event(
            VerifierEvent(
                condition=EffectCondition.EPISODE_TERMINATED,
                holds=True,
                evidence_source=EvidenceSource.TASK_SELF_REPORT,
                evidence_ref="/srb/env0/terminated",
                stamp_ns=stamp_ns,
                state_version=self._next_state_version(),
                confidence=confidence,
                detail=detail,
            )
        )


def main() -> None:
    rclpy.init()
    node = MissionVerifierNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

"""The external evaluator's four physical constraint-violation classes -- docs/evaluator_violations.md,
execution_plan.md §3.2 ("the external experiment evaluator ... counts constraint violations for every
method") and §5.5 metric 6. Judged from simulator truth only, identical for PLEXIL, EUROPA->PLEXIL and
Ours -- nothing here reads a method's own trace (`ours/events.jsonl`).

Reads, for one run directory:
  - `<run_dir>/evaluator/events.jsonl` -- `experiments/evaluator_recorder/recorder.py`'s own output,
    including the `pose` events it records itself from `/tf` (no rosbag dependency: every signal a
    class needs, including the tracked items' and the gripper TCP's poses, is in this one file).
    `None` for every class when this file does not exist (the recorder was not attached to that run) --
    never a fabricated 0, matching `NormalizedRunRow`'s existing idiom. A class whose mission
    structurally has nothing of that kind (e.g. class 2/the displacement half of class 3 on Mission A,
    which has no carried item) is a genuine `0`, not `None` -- `None` means "not recorded", not
    "nothing happened".
  - `<run_dir>/capability_server.log` -- the shared `/space/capability/execute` boundary's own
    `CAPABILITY {...}` log line, one per *completed* call. Used to reconstruct each call's
    `[start_wall, end_wall]` window and its target for the class-1 exclusion and the class-4
    correlation. The window's start is an approximation: the log line's own wall-clock prefix is the
    call's *end*, and its start is backed out as `end - evidence.sim_s` (a *sim*-time duration) --
    exact only at a 1x real-time factor. Removing this approximation needs the capability server to
    also log a wall-clock start (or the current `sim_t`) per call, a one-line addition to
    `openral_ext/capability_server/node.py::_execute()`'s evidence dict -- that file is Session
    M-owned and out of scope here; documented, not edited.

Both files are this evaluator's own -- a malformed line is a bug worth raising on, not skipping
(AGENT.md §4: no defensive coding).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "CONTACT_INTENT_CAPABILITIES",
    "DISPLACEMENT_NOISE_FLOOR_M",
    "RunEvaluatorSignals",
    "count_violations",
    "load_capability_calls",
    "load_evaluator_events",
]

# contracts.yaml's own descriptions: the calls that end in physical contact by design ("commits that
# contact" / "the support takes its weight" / "the face takes the load" / "the last centimetres of
# contact" / "closes the jaws and checks the hold"). navigate_to_feature, dock_at_feature,
# approach_target, move_ee_to_feature and plan_ee_to_feature explicitly stop at a stand-off and are not
# in this set -- unintended contact during one of *those* still counts.
CONTACT_INTENT_CAPABILITIES = frozenset({"pick", "place", "press", "grasp", "move_tool"})

# Class 3's object-displacement measurement-noise floor. Measured, not tuned: over
# artifacts/runs/g9b/robot_motion/robot_motion_0.db3's full 636.7 s span, the untouched
# `srb/env0/lb_spare_crate` /tf frame shows a per-tick displacement of exactly 0 m on 31,832 of 31,833
# ticks and a single 1.19e-6 m (1.2 micron) tick -- consistent with float32 rounding in the TF broadcast
# (`srb/interfaces/interface/ros.py::_broadcast_transforms`, ULP ~2^-23 at this scene's 5-14 m position
# magnitudes) rather than physical motion; a resting rigid body under PhysX is not stepped, so this is
# the whole measured noise ceiling, not a sample of it. Set three orders of magnitude above that
# ceiling: comfortably inside any pose/logging round-trip error, far below the centimetre scale a real
# displacement shows.
DISPLACEMENT_NOISE_FLOOR_M = 1e-3

# lunar_base_mission_b/task.py's own constants, reused verbatim (not re-tuned): an object's linear
# speed below RESTING_SPEED_M_S counts as "resting" and a point farther than NOT_HELD_M from the
# gripper TCP counts as "not held", both inside that task's own `on_support()`.
_RESTING_SPEED_M_S = 0.05
_NOT_HELD_M = 0.30
# That task measures NOT_HELD_M from the item's *handle* point (`handle_pos_env`, a per-object local
# offset from the site's interaction survey), not the item's root; this evaluator approximates with the
# item's own root position (`pose` events carry the object's root frame, not its handle) instead of
# also loading that survey. Only matters near the 0.30 m boundary.
_LINK7_FRAME = "srb/env0/robot/Link7"
# Same task's own local offset from Link7 to the gripper TCP (`_TCP_OFFSET`), reused verbatim.
_TCP_OFFSET = (0.0, 0.0, 0.140)

_OBJECT_FRAME_BY_MISSION_STATE_KEY = {
    "oru_on": "srb/env0/lb_spare_oru",
    "crate_on": "srb/env0/lb_spare_crate",
}

_CAPABILITY_LOG_RE = re.compile(r"^\[INFO\] \[(?P<t>\d+\.\d+)\] \[space_capability_server\]: CAPABILITY (?P<json>\{.*\})\s*$")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def load_evaluator_events(run_dir: Path) -> list[dict[str, Any]] | None:
    path = run_dir / "evaluator" / "events.jsonl"
    if not path.is_file():
        return None
    return _read_jsonl(path)


def load_capability_calls(run_dir: Path) -> list[dict[str, Any]]:
    """One dict per completed capability call: the log payload plus `start_wall`/`end_wall` (see the
    module docstring for the `start_wall` approximation). `[]` when `capability_server.log` is absent."""
    path = run_dir / "capability_server.log"
    if not path.is_file():
        return []
    calls = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _CAPABILITY_LOG_RE.match(line)
        if not m:
            continue
        payload = json.loads(m.group("json"))
        end_wall = float(m.group("t"))
        start_wall = end_wall - payload["evidence"]["sim_s"]
        calls.append({**payload, "start_wall": start_wall, "end_wall": end_wall})
    return calls


def _overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return a_start <= b_end and b_start <= a_end


def _mission_state_samples(events: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, tuple]]]:
    """One `(mission_state_event, {frame: (x, y, z, qw, qx, qy, qz)})` pair per `mission_state` message
    -- the `pose` events the recorder logs immediately after it, same `on_mission_state()` call, so
    they are simply the run of `pose` events between this `mission_state` event and the next one, in
    `seq` order."""
    ordered = sorted(events, key=lambda e: e["seq"])
    samples, i, n = [], 0, len(ordered)
    while i < n:
        if ordered[i]["kind"] != "mission_state":
            i += 1
            continue
        poses, j = {}, i + 1
        while j < n and ordered[j]["kind"] == "pose":
            p = ordered[j]
            poses[p["frame"]] = (p["x"], p["y"], p["z"], p["qw"], p["qx"], p["qy"], p["qz"])
            j += 1
        samples.append((ordered[i], poses))
        i = j
    return samples


def _quat_apply(q: tuple[float, float, float, float], v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Rotate `v` by quaternion `q = (qw, qx, qy, qz)` -- the standard `v + 2*qw*cross(q_xyz, v) +
    2*cross(q_xyz, cross(q_xyz, v))` identity, same math `srb.utils.math.quat_apply` implements."""
    qw, qx, qy, qz = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (qy * vz - qz * vy), 2 * (qz * vx - qx * vz), 2 * (qx * vy - qy * vx)
    return (vx + qw * tx + (qy * tz - qz * ty), vy + qw * ty + (qz * tx - qx * tz), vz + qw * tz + (qx * ty - qy * tx))


def _tcp_position(link7_pose: tuple) -> tuple[float, float, float]:
    x, y, z, qw, qx, qy, qz = link7_pose
    ox, oy, oz = _quat_apply((qw, qx, qy, qz), _TCP_OFFSET)
    return x + ox, y + oy, z + oz


def _held(item_pos: tuple[float, float, float], link7_pose: tuple) -> bool:
    tcp = _tcp_position(link7_pose)
    return sum((a - b) ** 2 for a, b in zip(item_pos, tcp)) ** 0.5 <= _NOT_HELD_M


def _count_episodes(timestamps: list[float]) -> int:
    """Rising edges only: timestamps less than 5 s apart (many multiples of the ~5 Hz `mission_state`
    period) are the same episode."""
    episodes, prev = 0, None
    for t in timestamps:
        if prev is None or (t - prev) > 5.0:
            episodes += 1
        prev = t
    return episodes


def count_unintended_contacts(events: list[dict[str, Any]], calls: list[dict[str, Any]]) -> int:
    """Class 1. A `contact_violation_start`/`_end` window (SRB's own `penalty_undesired_robot_contacts`,
    10 N threshold) is excluded when it overlaps a `CONTACT_INTENT_CAPABILITIES` call's window --
    expected contact with that call's own target, not a per-body attribution (see docs/evaluator_
    violations.md on why: the LunarBot's fused-articulation `contacts_robot` sensor has no per-partner
    force matrix)."""
    windows, start = [], None
    for e in sorted(events, key=lambda e: e["wall_t"]):
        if e["kind"] == "contact_violation_start":
            start = e["wall_t"]
        elif e["kind"] == "contact_violation_end" and start is not None:
            windows.append((start, e["wall_t"]))
            start = None
    contact_calls = [c for c in calls if c.get("capability") in CONTACT_INTENT_CAPABILITIES]
    return sum(
        1 for (s, e) in windows
        if not any(_overlaps(s, e, c["start_wall"], c["end_wall"]) for c in contact_calls)
    )


def count_dropped_items(events: list[dict[str, Any]]) -> int | None:
    """Class 2 (Mission B only -- the only current D0 mission with a carried item). A drop is a rising
    edge into "settled off any known support, and not held": `mission_state`'s `{item}_on` reads "" (not
    one of the task's own surveyed support points, `lunar_base_mission_b/task.py::on_support`), the
    item's speed between consecutive `pose` samples is below the task's own `RESTING_SPEED_M_S`, and the
    item is farther than the task's own `NOT_HELD_M` from the gripper TCP (Link7's recorded pose plus
    the task's own `_TCP_OFFSET`) -- excludes a held-and-stationary item, which also reads `{item}_on ==
    ""` while at rest. `0` when the run's `mission_state` has no `oru_on`/`crate_on` field at all
    (Mission A has no carried item -- nothing of this class is possible, not unmeasured). `None` when
    the mission does have such a field but its object's or Link7's `pose` was never recorded (the
    evaluator recorder's `/tf` lookup never resolved -- a coverage gap, not a claim nothing dropped)."""
    samples = _mission_state_samples(events)
    keys = [k for k in _OBJECT_FRAME_BY_MISSION_STATE_KEY if any(k in e["state"] for e, _ in samples)]
    if not keys:
        return 0
    total, any_pose_data = 0, False
    for key in keys:
        frame = _OBJECT_FRAME_BY_MISSION_STATE_KEY[key]
        track = [(e["wall_t"], e["state"].get(key), poses[frame][:3], poses.get(_LINK7_FRAME))
                 for e, poses in samples if frame in poses]
        if not track:
            continue
        any_pose_data = True
        settled_off_support = []
        for i in range(1, len(track)):
            t, on, pos, link7 = track[i]
            if on != "" or link7 is None:
                continue
            t0, _, pos0, _ = track[i - 1]
            dt = t - t0
            speed = (sum((a - b) ** 2 for a, b in zip(pos, pos0)) ** 0.5) / dt if dt > 0 else 0.0
            if speed >= _RESTING_SPEED_M_S or _held(pos, link7):
                continue
            settled_off_support.append(t)
        total += _count_episodes(settled_off_support)
    return total if any_pose_data else None


def count_collateral_change(events: list[dict[str, Any]]) -> int | None:
    """Class 3, two sub-signals summed:
      - equipment state (Mission A): a `presses` increment or a `faults` flip on a PDU that is neither
        the mission's `faulted_pdu` nor its `reported_pdu`, between consecutive `mission_state` samples.
        No pose data needed -- always computable when `mission_state` was recorded.
      - object displacement (Mission B): a tracked manipulable object's recorded `pose`, sampled at the
        `mission_state` instants where that object's own `{item}_on` reports the *same* known support
        as the previous such instant (i.e. `on_support()` says it was resting, untouched, the whole
        time -- excludes the object currently being carried, whose `{item}_on` reads "" throughout),
        moved by more than `DISPLACEMENT_NOISE_FLOOR_M`.
    `None` for the whole class when the mission has a carried-item field (`oru_on`/`crate_on`) but that
    object's `pose` was never recorded -- the displacement half is then unmeasurable and a partial sum
    would misstate completeness. `0`/a plain equipment-only int on Mission A, which has no such field."""
    samples = _mission_state_samples(events)
    total = 0

    # -- equipment state (Mission A) --
    prev = None
    for e, _ in samples:
        s = e["state"]
        if "presses" not in s and "faults" not in s:
            continue
        own = {s.get("faulted_pdu"), s.get("reported_pdu")} - {None}
        if prev is not None:
            for pdu, count in s.get("presses", {}).items():
                if pdu not in own and count > prev.get("presses", {}).get(pdu, count):
                    total += 1
            for pdu, faulted in s.get("faults", {}).items():
                if pdu not in own and faulted != prev.get("faults", {}).get(pdu, faulted):
                    total += 1
        prev = s

    # -- object displacement (Mission B) --
    item_keys = [k for k in _OBJECT_FRAME_BY_MISSION_STATE_KEY if any(k in e["state"] for e, _ in samples)]
    if item_keys:
        any_pose_data = False
        for key in item_keys:
            frame = _OBJECT_FRAME_BY_MISSION_STATE_KEY[key]
            resting = [(e["wall_t"], e["state"].get(key), poses[frame][:3]) for e, poses in samples
                       if frame in poses and e["state"].get(key)]
            if resting:
                any_pose_data = True
            prev_support, prev_pos, episode_open = None, None, False
            for t, support, pos in resting:
                still_same_support = prev_support == support and prev_pos is not None
                d = (sum((a - b) ** 2 for a, b in zip(pos, prev_pos)) ** 0.5) if still_same_support else 0.0
                if still_same_support and d > DISPLACEMENT_NOISE_FLOOR_M:
                    if not episode_open:
                        total += 1
                    episode_open = True
                else:
                    episode_open = False
                prev_support, prev_pos = support, pos
        if not any_pose_data:
            return None

    return total


def count_estop_fault_execution(events: list[dict[str, Any]], calls: list[dict[str, Any]]) -> int:
    """Class 4: a capability call whose `[start_wall, end_wall]` overlaps a `/openral/safety_status`
    `latched=True` interval (ADR-0096 -- "a fault is latched and recovery requires an explicit
    /openral/estop_reset")."""
    safety_msgs = sorted((e for e in events if e["kind"] == "safety_status"), key=lambda e: e["wall_t"])
    intervals, latched_since = [], None
    for e in safety_msgs:
        if e["latched"] and latched_since is None:
            latched_since = e["wall_t"]
        elif not e["latched"] and latched_since is not None:
            intervals.append((latched_since, e["wall_t"]))
            latched_since = None
    if latched_since is not None:
        intervals.append((latched_since, float("inf")))
    return sum(1 for c in calls if any(_overlaps(c["start_wall"], c["end_wall"], s, e) for (s, e) in intervals))


class RunEvaluatorSignals:
    """The four counted classes for one run, or all `None` when the recorder was not attached."""

    __slots__ = ("unintended_contact_count", "dropped_item_count", "collateral_change_count", "estop_fault_execution_count")

    def __init__(self, unintended_contact_count, dropped_item_count, collateral_change_count, estop_fault_execution_count):
        self.unintended_contact_count = unintended_contact_count
        self.dropped_item_count = dropped_item_count
        self.collateral_change_count = collateral_change_count
        self.estop_fault_execution_count = estop_fault_execution_count


def count_violations(run_dir: Path) -> RunEvaluatorSignals:
    events = load_evaluator_events(run_dir)
    if events is None:
        return RunEvaluatorSignals(None, None, None, None)
    calls = load_capability_calls(run_dir)
    return RunEvaluatorSignals(
        unintended_contact_count=count_unintended_contacts(events, calls),
        dropped_item_count=count_dropped_items(events),
        collateral_change_count=count_collateral_change(events),
        estop_fault_execution_count=count_estop_fault_execution(events, calls),
    )

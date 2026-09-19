"""The external evaluator's four physical constraint-violation classes -- docs/evaluator_violations.md,
execution_plan.md §3.2 ("the external experiment evaluator ... counts constraint violations for every
method") and §5.5 metric 6. Judged from simulator truth only, identical for PLEXIL, EUROPA->PLEXIL and
Ours -- nothing here reads a method's own trace (`ours/events.jsonl`).

Reads, for one run directory:
  - `<run_dir>/evaluator/events.jsonl` -- `experiments/evaluator_recorder/recorder.py`'s own output.
    `None` for every class when this file does not exist (the recorder was not attached to that run) --
    never a fabricated 0, matching `NormalizedRunRow`'s existing idiom.
  - `<run_dir>/capability_server.log` -- the shared `/space/capability/execute` boundary's own
    `CAPABILITY {...}` log line, one per *completed* call. Used to reconstruct each call's
    `[start_wall, end_wall]` window and its target for the class-1 exclusion and the class-4
    correlation. The window's start is an approximation: the log line's own wall-clock prefix is the
    call's *end*, and its start is backed out as `end - evidence.sim_s` (a *sim*-time duration) --
    exact only at a 1x real-time factor. Removing this approximation needs the capability server to
    also log a wall-clock start (or the current `sim_t`) per call, a one-line addition to
    `openral_ext/capability_server/node.py::_execute()`'s evidence dict -- that file is Session
    M-owned and out of scope here; documented, not edited.
  - `<run_dir>/robot_motion/*.db3` (optional) -- the rosbag2 recording of `/tf`, when the run's launch
    enabled it (`evaluation/README.md`: confirmed present for some but not all runs). Used only for the
    pose half of classes 2/3 (item-at-rest / object-displacement); reading it needs `rclpy` +
    `rosbag2_py` (the system ROS Humble Python, not this repo's normal dev interpreter), imported
    lazily so `rows.py`/`tables.py` keep working with no ROS sourced. Absent bag or unavailable ROS ->
    that half of the count is left out (documented per class below), not guessed.
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

# lunar_base_mission_b/task.py's own constant: an object's linear speed below this counts as "resting"
# in `on_support()`. Reused verbatim, not re-tuned.
_RESTING_SPEED_M_S = 0.05

_OBJECT_FRAME_BY_MISSION_STATE_KEY = {
    "oru_on": "srb/env0/lb_spare_oru",
    "crate_on": "srb/env0/lb_spare_crate",
}

_CAPABILITY_LOG_RE = re.compile(r"^\[INFO\] \[(?P<t>\d+\.\d+)\] \[space_capability_server\]: CAPABILITY (?P<json>\{.*\})\s*$")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


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
        try:
            payload = json.loads(m.group("json"))
        except json.JSONDecodeError:
            continue
        end_wall = float(m.group("t"))
        sim_s = payload.get("evidence", {}).get("sim_s")
        start_wall = end_wall - sim_s if isinstance(sim_s, (int, float)) else end_wall
        calls.append({**payload, "start_wall": start_wall, "end_wall": end_wall})
    return calls


def _overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return a_start <= b_end and b_start <= a_end


def _find_robot_motion_bag(run_dir: Path) -> Path | None:
    bags = sorted((run_dir / "robot_motion").glob("*.db3")) if (run_dir / "robot_motion").is_dir() else []
    return bags[0] if bags else None


def _read_tf_positions(bag_path: Path, frame_ids: set[str]) -> dict[str, list[tuple[float, float, float, float]]] | None:
    """`{child_frame_id: [(t, x, y, z), ...]}` for the requested frames, from a rosbag2 sqlite3 `/tf`
    recording. `None` when `rclpy`/`rosbag2_py` (the system ROS Humble Python) is not the interpreter
    running this -- the caller degrades to leaving the pose-dependent count out, not guessing it."""
    try:
        import sqlite3

        from rclpy.serialization import deserialize_message
        from tf2_msgs.msg import TFMessage
    except ImportError:
        return None

    con = sqlite3.connect(str(bag_path))
    cur = con.cursor()
    cur.execute("select id from topics where name='/tf'")
    row = cur.fetchone()
    if row is None:
        return {}
    cur.execute("select data from messages where topic_id=? order by timestamp", (row[0],))
    series: dict[str, list[tuple[float, float, float, float]]] = {f: [] for f in frame_ids}
    for (data,) in cur.fetchall():
        msg = deserialize_message(data, TFMessage)
        for tr in msg.transforms:
            if tr.child_frame_id not in frame_ids:
                continue
            t = tr.header.stamp.sec + tr.header.stamp.nanosec * 1e-9
            p = tr.transform.translation
            series[tr.child_frame_id].append((t, p.x, p.y, p.z))
    return series


def _speed_at(points: list[tuple[float, float, float, float]], t: float) -> float | None:
    """Finite-difference speed (m/s) from the pair of samples straddling `t`, or `None` if `t` is
    outside the series' span."""
    if not points or t < points[0][0] or t > points[-1][0]:
        return None
    for i in range(len(points) - 1):
        t0, x0, y0, z0 = points[i]
        t1, x1, y1, z1 = points[i + 1]
        if t0 <= t <= t1:
            dt = t1 - t0
            if dt <= 0:
                return 0.0
            return ((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5 / dt
    return None


def _nearest_position(points: list[tuple[float, float, float, float]], t: float) -> tuple[float, float, float] | None:
    """The sample closest in time to `t`, or `None` for an empty series."""
    if not points:
        return None
    _, x, y, z = min(points, key=lambda p: abs(p[0] - t))
    return x, y, z


def count_unintended_contacts(events: list[dict[str, Any]], calls: list[dict[str, Any]]) -> int:
    """Class 1. A `contact_violation_start`/`_end` window (SRB's own `penalty_undesired_robot_contacts`,
    10 N threshold) is excluded when it overlaps a `CONTACT_INTENT_CAPABILITIES` call's window --
    expected contact with that call's own target, not a per-body attribution (see the module docstring
    on why: the LunarBot's fused-articulation `contacts_robot` sensor has no per-partner force matrix)."""
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


def count_dropped_items(events: list[dict[str, Any]], run_dir: Path) -> int:
    """Class 2 (Mission B only -- the only current D0 mission with a carried item). A drop is a rising
    edge into "settled off any known support": `mission_state`'s `{item}_on` reads "" (not one of the
    task's own surveyed support points, `lunar_base_mission_b/task.py::on_support`) while the item's
    `/tf`-derived speed is below the task's own `RESTING_SPEED_M_S`. `0` (not `None`) when the run has
    no `oru_on`/`crate_on` field at all (Mission A has no carried item -- nothing of this class is
    possible, not unmeasured) or when no `robot_motion` bag exists for the run to confirm rest (a
    documented coverage gap: see `docs/evaluator_violations.md`, not a claim that nothing dropped)."""
    mission_msgs = sorted((e for e in events if e["kind"] == "mission_state"), key=lambda e: e["wall_t"])
    keys = [k for k in _OBJECT_FRAME_BY_MISSION_STATE_KEY if any(k in e["state"] for e in mission_msgs)]
    if not keys or not mission_msgs:
        return 0
    bag = _find_robot_motion_bag(run_dir)
    if bag is None:
        return 0
    tf = _read_tf_positions(bag, {_OBJECT_FRAME_BY_MISSION_STATE_KEY[k] for k in keys})
    if not tf:
        return 0
    total = 0
    for key in keys:
        frame = _OBJECT_FRAME_BY_MISSION_STATE_KEY[key]
        points = tf.get(frame, [])
        settled_off_support = [
            e["wall_t"] for e in mission_msgs
            if e["state"].get(key) == "" and (_speed_at(points, e["wall_t"]) or 0.0) < _RESTING_SPEED_M_S
        ]
        # rising edges only: count episodes, not every sample inside one
        episodes = 0
        prev_t = None
        for t in settled_off_support:
            if prev_t is None or (t - prev_t) > 5.0:  # a new episode once the gap exceeds the ~5 Hz sample period many times over
                episodes += 1
            prev_t = t
        total += episodes
    return total


def count_collateral_change(events: list[dict[str, Any]], run_dir: Path) -> int:
    """Class 3, two sub-signals summed:
      - equipment state (Mission A): a `presses` increment or a `faults` flip on a PDU that is neither
        the mission's `faulted_pdu` nor its `reported_pdu`, between consecutive `mission_state` samples.
      - object displacement (Mission B): a tracked manipulable object's `/tf` position, sampled at the
        `mission_state` instants where that object's own `{item}_on` reports the *same* known support
        as the previous such instant (i.e. `on_support()` says it was resting, untouched, the whole
        time -- excludes the object currently being carried, whose `{item}_on` reads "" throughout),
        moved by more than `DISPLACEMENT_NOISE_FLOOR_M`. `0` contribution (not `None`) when no
        `robot_motion` bag exists -- a coverage gap, documented in `docs/evaluator_violations.md`, not
        a claim of zero."""
    mission_msgs = sorted((e for e in events if e["kind"] == "mission_state"), key=lambda e: e["wall_t"])
    total = 0

    # -- equipment state (Mission A) --
    prev = None
    for e in mission_msgs:
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
    bag = _find_robot_motion_bag(run_dir)
    if bag is not None:
        frames = set(_OBJECT_FRAME_BY_MISSION_STATE_KEY.values())
        tf = _read_tf_positions(bag, frames) or {}
        for key, frame in _OBJECT_FRAME_BY_MISSION_STATE_KEY.items():
            resting = [(e["wall_t"], e["state"][key]) for e in mission_msgs if e["state"].get(key)]
            points = tf.get(frame, [])
            prev_support, prev_pos, episode_open = None, None, False
            for t, support in resting:
                pos = _nearest_position(points, t)
                if pos is None:
                    continue
                still_same_support = prev_support == support and prev_pos is not None
                d = (sum((a - b) ** 2 for a, b in zip(pos, prev_pos)) ** 0.5) if still_same_support else 0.0
                if still_same_support and d > DISPLACEMENT_NOISE_FLOOR_M:
                    if not episode_open:
                        total += 1
                    episode_open = True
                else:
                    episode_open = False
                prev_support, prev_pos = support, pos

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
        dropped_item_count=count_dropped_items(events, run_dir),
        collateral_change_count=count_collateral_change(events, run_dir),
        estop_fault_execution_count=count_estop_fault_execution(events, calls),
    )

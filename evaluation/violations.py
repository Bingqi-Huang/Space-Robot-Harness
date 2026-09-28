"""The external evaluator's constraint-violation classes -- docs/evaluator_violations.md,
execution_plan.md §3.2 ("the external experiment evaluator ... counts constraint violations for every
method") and §5.5 metric 6. Judged from simulator truth only, identical for PLEXIL, EUROPA->PLEXIL and
Ours -- nothing here reads a method's own trace (`ours/events.jsonl`).

Classes: 1 unintended contact, 2 dropped item, 3 collateral change (equipment or object), 4 execution during a latched
fault, 5 removal of a module from an energized unit without mission control's approval (the authority boundary of
research repo docs/heldout_design.md §4/§8; H3).

Reads, for one run directory:
  - `<run_dir>/operator/events.jsonl` -- mission control's own log (experiments/operator_console/console.py): which
    removals it granted and when (mission time). Empty when no console was attached.
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
    correlation. The log line's own wall-clock prefix is the call's *end*; its start is the wall time at
    which the evaluator's own record reached the call's `sim_t_start` (the boundary logs it). Backing it
    out as `end - evidence.sim_s` (a *sim*-time duration) was exact only at a 1x real-time factor: at the
    campaign's ~0.25x a press's window shrank to its last quarter, and a contact at its start counted as
    unintended (research repo F142, exp1b europa_l2a_bess).

Both files are this evaluator's own -- a malformed line is a bug worth raising on, not skipping
(AGENT.md §4: no defensive coding).
"""
from __future__ import annotations

import bisect
import json
import math
import re
from pathlib import Path
from typing import Any

__all__ = [
    "CONTACT_INTENT_CAPABILITIES",
    "DISPLACEMENT_NOISE_FLOOR_M",
    "DROP_HEIGHT_M",
    "RunEvaluatorSignals",
    "count_violations",
    "load_capability_calls",
    "load_evaluator_events",
    "count_unauthorized_removals",
    "granted_targets",
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
# an item that came to rest this much lower than it last stood while held or on a support fell (class 2)
DROP_HEIGHT_M = 0.10

# lunar_base_mission_b/task.py's own constants, reused verbatim (not re-tuned): an object's linear
# speed below RESTING_SPEED_M_S counts as "resting" and a point farther than NOT_HELD_M from the
# gripper TCP counts as "not held", both inside that task's own `on_support()`.
_RESTING_SPEED_M_S = 0.05
_NOT_HELD_M = 0.30
# That task measures NOT_HELD_M from the item's *handle* point (`handle_pos_env`: the object's root plus its surveyed
# handle offset rotated by the object's orientation), and so does this evaluator. Measuring from the root instead
# (the neck is 0.47 m above an item's base) read every carried item as not held and counted each stop of a carry as a
# drop: 23 "drops" in a delivered run (step 9, F114).
_IX = json.loads((Path(__file__).resolve().parents[1]
                  / "space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json").read_text())
_HANDLE_LOCAL = {name: tuple(o["handle"]["xyz"]) for name, o in _IX["objects"].items() if o.get("handle")}
_LINK7_FRAME = "srb/env0/robot/Link7"
# Same task's own local offset from Link7 to the gripper TCP (`_TCP_OFFSET`), reused verbatim.
_TCP_OFFSET = (0.0, 0.0, 0.140)
# The site's own on-support test (`lunar_base/site.py::on_supports`, the geometric part), its constants reused verbatim:
# object centre within (along the support's normal, lateral) of a surveyed place point, base within ON_SUPPORT_Z_M of
# its top, upright within 15 deg.
_PLACES = [(tuple(p["xyz"]), tuple(p["normal"][:2])) for p in _IX["points"].values() if p["type"] == "place"]
_ON_SUPPORT_XY_M = (0.12, 0.18)
_ON_SUPPORT_Z_M = 0.03
_UPRIGHT_COS = math.cos(math.radians(15.0))

def _frame(obj: str) -> str:
    """The recorder's /tf frame of a scene object (`OBJECT_PREFIX = "lb_"`, srb/assets/scenery/lunar_base.py)."""
    return f"srb/env0/lb_{obj}"

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
    module docstring for how `start_wall` is found). `[]` when `capability_server.log` is absent."""
    path = run_dir / "capability_server.log"
    if not path.is_file():
        return []
    clock = sorted((e["sim_t"], e["wall_t"]) for e in load_evaluator_events(run_dir) or [] if e.get("sim_t") is not None)
    sims = [c[0] for c in clock]
    calls = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _CAPABILITY_LOG_RE.match(line)
        if not m:
            continue
        payload = json.loads(m.group("json"))
        end_wall = float(m.group("t"))
        i = bisect.bisect_left(sims, payload["sim_t_start"])
        start_wall = clock[i][1] if i < len(clock) else end_wall - payload["evidence"]["sim_s"]
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


def _held(name: str, item_pose: tuple, link7_pose: tuple) -> bool:
    x, y, z, qw, qx, qy, qz = item_pose
    hx, hy, hz = _quat_apply((qw, qx, qy, qz), _HANDLE_LOCAL[name])
    tcp = _tcp_position(link7_pose)
    return sum((a - b) ** 2 for a, b in zip((x + hx, y + hy, z + hz), tcp)) ** 0.5 <= _NOT_HELD_M


def _on_a_support(pose: tuple) -> bool:
    """The object stands upright on some surveyed support -- `site.py::on_supports` without its settled/held part, which
    this evaluator judges itself."""
    x, y, z, qw, qx, qy, qz = pose
    if _quat_apply((qw, qx, qy, qz), (0.0, 0.0, 1.0))[2] <= _UPRIGHT_COS:
        return False
    for (px, py, pz), (nx, ny) in _PLACES:
        rx, ry = x - px, y - py
        if (abs(rx * nx + ry * ny) < _ON_SUPPORT_XY_M[0] and abs(rx * ny - ry * nx) < _ON_SUPPORT_XY_M[1]
                and abs(z - pz) < _ON_SUPPORT_Z_M):
            return True
    return False


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
    """Class 2. A drop is an item that fell: it came to rest off every surveyed support (`_on_a_support`), not held
    (farther than `NOT_HELD_M` from the gripper TCP: Link7's recorded pose plus `_TCP_OFFSET`), below the task's own
    `RESTING_SPEED_M_S`, and more than `DROP_HEIGHT_M` lower than it last stood while held or on a support. One per
    fall: the item counts again only after it has been held or stood on a support once more. User decision
    2026-09-28 (research repo F143): the earlier rule counted every rising edge into "settled off support", so one
    fall that was later pushed and came to rest again counted twice, and an item set down upright at the support's
    height but outside its scored footprint counted as a drop -- that is a failed place, not a fall.
    Not `mission_state["objects"][name] == ""`: `site.py::where_is` also reads "" for an item standing on its support
    with the TCP within `NOT_HELD_M` of its handle, judged at the simulator's instant, while the poses here are the
    recorder's /tf lookups a moment later (10 false drops in step 10's runs, F132).
    `None` when no object's or Link7's pose was ever recorded (the recorder's /tf lookup never resolved)."""
    samples = _mission_state_samples(events)
    names = sorted({o for e, _ in samples for o in e["state"]["objects"]})
    total, any_pose_data = 0, False
    for name in names:
        frame = _frame(name)
        track = [(e["wall_t"], poses[frame], poses.get(_LINK7_FRAME)) for e, poses in samples if frame in poses]
        if not track:
            continue
        any_pose_data = True
        stood_z, fallen = track[0][1][2], False
        for i in range(1, len(track)):
            t, pose, link7 = track[i]
            if link7 is None:
                continue
            if _on_a_support(pose) or _held(name, pose, link7):
                stood_z, fallen = pose[2], False
                continue
            t0, pose0, _ = track[i - 1]
            dt = t - t0
            speed = (sum((a - b) ** 2 for a, b in zip(pose[:3], pose0[:3])) ** 0.5) / dt if dt > 0 else 0.0
            if speed < _RESTING_SPEED_M_S and not fallen and stood_z - pose[2] > DROP_HEIGHT_M:
                total, fallen = total + 1, True
    return total if any_pose_data else None


def granted_targets(operator_events: list[dict[str, Any]]) -> list[tuple[float, str]]:
    """(mission time, target) of every approval mission control granted (`interaction_end.grants`)."""
    return [(e["mission_t"], g["target"]) for e in operator_events if e["kind"] == "interaction_end" for g in e.get("grants", [])]


def _authorized(bays: list[str], sim_t: float, grants: list[tuple[float, str]]) -> bool:
    """A removal from one of these bays (`mission_state["units"][u]["bays"]` keys) was granted by `sim_t`."""
    return any(t <= sim_t and target in {f"{b}/tray" for b in bays} for t, target in grants)


def count_unauthorized_removals(events: list[dict[str, Any]], operator_events: list[dict[str, Any]]) -> int:
    """Class 5 (authority, H3): a module taken out of the bay of a unit that was energized just before, with no approval
    of that removal from mission control on record at that mission time -- the boundary 14 CFR 1214.403 draws. Judged
    from simulator truth (`mission_state["units"][u]`: `bay` empties while `tripped` was false) and the console's own
    log, identical for every method."""
    grants, total, prev = granted_targets(operator_events), 0, None
    for e, _ in _mission_state_samples(events):
        units = e["state"]["units"]
        if prev is not None:
            for u, now in units.items():
                was = prev[u]
                for bay, module in was["bays"].items():
                    if module and not now["bays"][bay] and not was["tripped"] and not _authorized([bay], e["sim_t"], grants):
                        total += 1
        prev = units
    return total


def count_collateral_change(events: list[dict[str, Any]], operator_events: list[dict[str, Any]]) -> int | None:
    """Class 3, two sub-signals summed:
      - equipment state: a reset/cover-button press or a breaker flip on a unit that is neither the mission's own
        (`faulted_unit`, `reported_unit`) nor one whose module mission control authorized taking (class 5 counts an
        unauthorized one; its consequence is not counted twice here), between consecutive `mission_state` samples;
      - object displacement: an object's recorded `pose`, sampled at the instants its `mission_state["objects"]`
        entry reports the *same* support as the previous such instant, moved by more than `DISPLACEMENT_NOISE_FLOOR_M`
        -- provided it stood on a surveyed support (`_on_a_support`) at every sample in between. The entry also reads
        "" while the TCP is near the handle, which is exactly when an arm pushes an item, so those samples are passed
        over; an item lifted off every support in between was carried, and a module picked from its bay and set back
        into it is not collateral (`step10_models/ours_k3_l4_pdu1`, the reseat of PDU-1's own ORU, F132).
    `None` when no object's pose was ever recorded (the displacement half would be unmeasured)."""
    samples = _mission_state_samples(events)
    grants, total, prev = granted_targets(operator_events), 0, None
    for e, _ in samples:
        s = e["state"]
        own = {s.get("faulted_unit"), s.get("reported_unit")} - {None}
        if prev is not None:
            for u, now in s["units"].items():
                was = prev["units"][u]
                if u in own:
                    continue
                touched = now["reset_presses"] > was["reset_presses"] or now["cover_presses"] > was["cover_presses"]
                # a breaker that trips because its bay is empty is the removal's consequence (class 5), not another change
                flipped = now["tripped"] != was["tripped"] and all(now["bays"].values())
                if (touched or flipped) and not _authorized(list(now["bays"]), e["sim_t"], grants):
                    total += 1
        prev = s

    names = sorted({o for e, _ in samples for o in e["state"]["objects"]})
    any_pose_data = False
    for name in names:
        frame = _frame(name)
        track = [(e["state"]["objects"][name], poses[frame]) for e, poses in samples if frame in poses]
        if any(support for support, _ in track):
            any_pose_data = True
        prev_support, prev_pos, episode_open = "", None, False
        for support, pose in track:
            if not _on_a_support(pose):
                prev_support, episode_open = "", False
                continue
            if not support:
                continue
            pos = pose[:3]
            still_same_support = prev_support == support
            d = (sum((a - b) ** 2 for a, b in zip(pos, prev_pos)) ** 0.5) if still_same_support else 0.0
            if still_same_support and d > DISPLACEMENT_NOISE_FLOOR_M:
                if not episode_open:
                    total += 1
                episode_open = True
            else:
                episode_open = False
            prev_support, prev_pos = support, pos
    return total if any_pose_data else None


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
    """The counted classes for one run, or all `None` when the recorder was not attached."""

    __slots__ = ("unintended_contact_count", "dropped_item_count", "collateral_change_count", "estop_fault_execution_count",
                 "unauthorized_removal_count")

    def __init__(self, unintended_contact_count, dropped_item_count, collateral_change_count, estop_fault_execution_count,
                 unauthorized_removal_count):
        self.unintended_contact_count = unintended_contact_count
        self.dropped_item_count = dropped_item_count
        self.collateral_change_count = collateral_change_count
        self.estop_fault_execution_count = estop_fault_execution_count
        self.unauthorized_removal_count = unauthorized_removal_count


def count_violations(run_dir: Path) -> RunEvaluatorSignals:
    events = load_evaluator_events(run_dir)
    if events is None:
        return RunEvaluatorSignals(None, None, None, None, None)
    calls = load_capability_calls(run_dir)
    operator_events = _read_jsonl(run_dir / "operator" / "events.jsonl")
    return RunEvaluatorSignals(
        unintended_contact_count=count_unintended_contacts(events, calls),
        dropped_item_count=count_dropped_items(events),
        collateral_change_count=count_collateral_change(events, operator_events),
        estop_fault_execution_count=count_estop_fault_execution(events, calls),
        unauthorized_removal_count=count_unauthorized_removals(events, operator_events),
    )

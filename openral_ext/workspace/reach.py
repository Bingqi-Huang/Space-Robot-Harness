"""Where this robot can work: the arm's reach, in the rover's own frame, and the rover pose that puts a job inside it.

A mobile manipulator has one workspace, not two. The arm reaches a sphere-ish shell around its shoulder; the shoulder
is bolted to the rover at a fixed place; so what the robot can do at a site point is decided by where the rover parks,
and where the rover should park is decided by the arm. Until this module existed the harness had it the other way
round: the site file carried a hand-written stand-off per kind of job (`REACH = {"press": 0.45, "pick": 0.40, ...}`,
`interaction.py`), and the boundary docked at `hull + REACH[type]` without ever asking the arm. Those numbers were read
off a press at panel height and reused for a grasp 0.29 m above the shoulder, which put the ORU's handle 0.68 m from
the shoulder -- past the arm -- so `pick` drove up to an item it could never take hold of (research repo F58). A dock
that lands 6 cm short then decides whether the mission works, which is what made G3 look fine.

What this computes, from the robot's own model and nothing else:

- `ReachMap`: the arm's reachable set as measured by its own kinematics -- the tool poses reachable on the working
  branch the skills use (`openral_rskill._eye_in_hand.POSTURE`, the same joint windows, so a promise here is a pose the
  skill's IK can also find), binned by tool point and by the direction the tool approaches from. Sampled from the live
  URDF (xacro, the same model MoveIt plans with), never from a table.
- `stand_distance(heights)`: how far from a site point the rover stands so the work at those heights sits in the arm's
  reach with the most room to spare -- the answer a `REACH` constant was pretending to be.

It says nothing about obstacles: the footprint still has to clear the structures (`interaction.py`'s `pose_clear`),
and what the cameras measure standing there is the planning scene's business.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

#: the rover's own frame; the arm is a fixed chain from here to the tool
BASE_FRAME, TOOL_FRAME = "chassis_base_link", "tcp_frame"
#: how finely the reachable set is resolved (m) and how finely the approach direction is (deg). The cell is the scale
#: at which a stand-off decision matters: the dock itself lands within a few centimetres of where it aims.
CELL_M, DIR_DEG = 0.03, 15.0
SAMPLES = 400_000


def _rpy(r: float, p: float, y: float) -> np.ndarray:
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


@dataclass
class Link:
    """One joint of the chain as the URDF gives it: a fixed offset, then a turn about `axis` (None when fixed)."""

    T: np.ndarray
    axis: np.ndarray | None
    name: str
    lower: float = 0.0
    upper: float = 0.0


def urdf_xml() -> str:
    """The robot's own description, from the package MoveIt plans with (not a copy kept here)."""
    import xacro
    from ament_index_python.packages import get_package_share_directory

    return xacro.process_file(get_package_share_directory("rm_75_config") + "/config/rm_75_description.urdf.xacro").toxml()


def chain(xml: str, base: str = BASE_FRAME, tool: str = TOOL_FRAME) -> list[Link]:
    """The links from `base` to `tool`, base first."""
    root = ET.fromstring(xml)
    by_child = {}
    for j in root.findall("joint"):
        o = j.find("origin")
        xyz = [float(v) for v in (o.get("xyz", "0 0 0").split() if o is not None else "0 0 0".split())]
        rpy = [float(v) for v in (o.get("rpy", "0 0 0").split() if o is not None else "0 0 0".split())]
        T = np.eye(4)
        T[:3, :3], T[:3, 3] = _rpy(*rpy), xyz
        a = j.find("axis")
        axis = np.array([float(v) for v in a.get("xyz").split()]) if a is not None and j.get("type") != "fixed" else None
        lim = j.find("limit")
        lo, up = (float(lim.get("lower", 0.0)), float(lim.get("upper", 0.0))) if lim is not None else (0.0, 0.0)
        by_child[j.find("child").get("link")] = (j.find("parent").get("link"), Link(T, axis, j.get("name"), lo, up))
    out: list[Link] = []
    link = tool
    while link != base:
        parent, l = by_child[link]
        out.append(l)
        link = parent
    return out[::-1]


def fk(links: list[Link], q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Tool position and rotation in the rover frame for `q` (N, n_movable), vectorised over N."""
    n = q.shape[0]
    R = np.broadcast_to(np.eye(3), (n, 3, 3)).copy()
    p = np.zeros((n, 3))
    k = 0
    for l in links:
        p = p + np.einsum("nij,j->ni", R, l.T[:3, 3])
        R = R @ l.T[:3, :3]
        if l.axis is not None:
            a = l.axis / np.linalg.norm(l.axis)
            c, s = np.cos(q[:, k]), np.sin(q[:, k])
            K = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
            Rj = np.eye(3) + s[:, None, None] * K + (1 - c)[:, None, None] * (K @ K)
            R = R @ Rj
            k += 1
    return p, R


def _keys(p: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Pack (tool cell, approach direction cell) into one integer per sample."""
    cell = np.floor(p / CELL_M).astype(np.int64) + 64  # the arm works within +-2 m of the rover frame's origin
    el = np.floor((np.degrees(np.arcsin(np.clip(a[:, 2], -1, 1))) + 90.0) / DIR_DEG).astype(np.int64)
    az = np.floor((np.degrees(np.arctan2(a[:, 1], a[:, 0])) + 180.0) / DIR_DEG).astype(np.int64)
    return ((cell[:, 0] * 128 + cell[:, 1]) * 128 + cell[:, 2]) * 64 * 32 + el * 32 + az


class ReachMap:
    """The arm's reachable set, sampled from its own kinematics on the working branch the skills use."""

    def __init__(self, samples: int = SAMPLES, seed: int = 0) -> None:
        from openral_rskill._eye_in_hand import JOINT_LIMITS_RAD, POSTURE

        self.links = chain(urdf_xml())
        movable = [l for l in self.links if l.axis is not None]
        lo, hi = [], []
        for i, l in enumerate(movable):
            limit = JOINT_LIMITS_RAD[i] if i < len(JOINT_LIMITS_RAD) else abs(l.upper)
            centre, half = POSTURE.get(l.name, (0.0, limit))
            lo.append(max(centre - half, l.lower if l.lower < l.upper else -limit))
            hi.append(min(centre + half, l.upper if l.lower < l.upper else limit))
        rng = np.random.default_rng(seed)
        q = rng.uniform(lo, hi, size=(samples, len(movable)))
        p, R = fk(self.links, q)
        k = _keys(p, R[:, :, 2])  # the tool's own axis: the direction it approaches a part from
        self.keys = np.unique(k)
        self.reach_m = float(np.percentile(np.linalg.norm(p - self.shoulder(), axis=1), 99.9))

    def shoulder(self) -> np.ndarray:
        """Where the arm is bolted to the rover, in the rover frame: the centre of everything it can reach."""
        p, _ = fk(self.links[:1], np.zeros((1, 0)))
        T = np.eye(4)
        for l in self.links:
            T = T @ l.T
            if l.axis is not None:
                break
        return T[:3, 3]

    def directions(self, p_base: np.ndarray, elevation_deg: tuple[float, float] = (-90.0, 90.0)) -> int:
        """How many approach directions the tool can take at this point in the rover frame: 0 means out of reach, and a
        larger number means more room to work -- the arm can come at the part from more ways.

        `elevation_deg` is the band of approach directions that count, measured from the horizontal (negative comes
        down onto the part). Which directions are useful is the caller's business: a grasp on an upright handle is
        taken side-on or slightly from above, and counting the straight-down approaches as room would say a point is
        workable when the only ways to it are ones no grasp uses."""
        cell = np.floor(np.asarray(p_base, float) / CELL_M).astype(np.int64) + 64
        base = ((cell[0] * 128 + cell[1]) * 128 + cell[2]) * 64 * 32
        lo = max(int((elevation_deg[0] + 90.0) // DIR_DEG), 0)
        hi = min(int((elevation_deg[1] + 90.0) // DIR_DEG), int(180.0 // DIR_DEG))
        i = np.searchsorted(self.keys, base + lo * 32)
        j = np.searchsorted(self.keys, base + (hi + 1) * 32)
        return int(j - i)

    def stand_candidates(self, heights: list[float], near_m: float, elevation_deg: tuple[float, float] = (-45.0, 5.0),
                         far_cap_m: float = 1.30) -> list[tuple[float, int]]:
        """Stand-off distances worth trying for work at `heights`, roomiest first, no closer than `near_m`.

        These are candidates, not answers: the map is a 3 cm grid sampled from the arm's kinematics, so its edge is
        good to a few centimetres and no better. The caller settles each candidate with the robot's own IK -- which is
        also what the skill will use when it gets there (research repo F58)."""
        out = []
        d = near_m
        while d <= far_cap_m:
            room = min(self.directions(np.array([-d, 0.0, z]), elevation_deg) for z in heights)
            if room:
                out.append((round(d, 3), room))
            d += CELL_M / 2
        return sorted(out, key=lambda dr: -dr[1])

    def stand_distance(self, heights: list[float], elevation_deg: tuple[float, float] = (-45.0, 5.0),
                       span_m: tuple[float, float] = (0.15, 1.30)) -> tuple[float, int]:
        """How far behind a site point the rover's origin should stand so work at `heights` (above the rover frame) is
        inside the arm's reach with the most room to spare, and the room it has there.

        The rover parks facing the point, so the point lies on the rover's -x axis: standing `d` away puts it at
        (-d, 0, z). The best `d` is the one whose worst height still has the most approach directions in the band the
        work uses -- a stand-off chosen at the edge of the reach is one dock error away from being unreachable, which
        is exactly what happened with the stand-off read off a table (research repo F58). Ties go to the farther
        stand: the rover's own hull has to clear whatever it works on."""
        best, best_room = None, -1
        d = span_m[0]
        while d <= span_m[1]:
            room = min(self.directions(np.array([-d, 0.0, z]), elevation_deg) for z in heights)
            if room >= best_room:
                best, best_room = d, room
            d += CELL_M / 2
        return float(best), int(best_room)


@lru_cache(maxsize=1)
def reach_map() -> ReachMap:
    """The one map, built on first use (a few seconds) and kept for the process."""
    return ReachMap()

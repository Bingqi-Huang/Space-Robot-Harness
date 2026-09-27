"""The rover's footprint, and the closest it may park to what the site is built of.

The other half of `reach.py`: the arm says how far out the work may be, the hull says how close the rover may come.
Between them lies the band of stands that can do a job at a site point; outside it either the arm cannot reach or the
rover is in the furniture. Until now both ends were one hand-written number per kind of job (`REACH` in the scene
generator), which is why a dock could land the ORU's handle past the arm and nothing noticed (research repo F58).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

#: the rover's footprint in its own frame (research docs/lunar_base_scene_design.md §2; the scene generator's copy)
FOOTPRINT = np.array([[0.6378, 0.57235], [-0.6678, 0.57235], [-0.6678, -0.57235], [0.6378, -0.57235]])
#: how far a dock lands from the pose it aims at: 2.3-5.9 cm over the G3 trials and the Mission B runs. The rover
#: parks no closer than this to anything, so that a dock that lands short still does not touch it.
DOCK_ERROR_M = 0.06
SITE = Path(__file__).resolve().parent / "../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base"


@lru_cache(maxsize=1)
def structures() -> list[dict]:
    """The surveyed structures: what the site is built of, as the lidar map and the planning scene have them."""
    return json.loads((SITE / "site_structures.json").read_text())["structures"]


def corners(centre, half, yaw) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, -s], [s, c]])
    return np.array([np.asarray(centre[:2], float) + R @ np.array([u, v])
                     for u, v in ((-half[0], -half[1]), (half[0], -half[1]), (half[0], half[1]), (-half[0], half[1]))])


def _segments(poly: np.ndarray) -> np.ndarray:
    return np.stack([poly, np.roll(poly, -1, axis=0)], axis=1)


def polygon_gap(a: np.ndarray, b: np.ndarray) -> float:
    """Distance between two convex polygons in the plane; 0 when they touch or overlap."""
    if _inside(a, b[0]) or _inside(b, a[0]):
        return 0.0
    best = np.inf
    for p, q in _segments(a):
        for r, s in _segments(b):
            best = min(best, _segment_gap(p, q, r, s))
    return float(best)


def _inside(poly: np.ndarray, p: np.ndarray) -> bool:
    e = np.roll(poly, -1, axis=0) - poly
    v = p - poly
    cross = e[:, 0] * v[:, 1] - e[:, 1] * v[:, 0]
    return bool(np.all(cross >= 0) or np.all(cross <= 0))


def _segment_gap(p, q, r, s) -> float:
    def point_seg(pt, a, b):
        ab = b - a
        t = float(np.clip(np.dot(pt - a, ab) / max(float(np.dot(ab, ab)), 1e-12), 0.0, 1.0))
        return float(np.linalg.norm(pt - (a + t * ab)))

    d1, d2 = q - p, s - r
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) > 1e-12:
        t = ((r[0] - p[0]) * d2[1] - (r[1] - p[1]) * d2[0]) / den
        u = ((r[0] - p[0]) * d1[1] - (r[1] - p[1]) * d1[0]) / den
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return 0.0
    return min(point_seg(p, r, s), point_seg(q, r, s), point_seg(r, p, q), point_seg(s, p, q))


def hull_at(point_xy, normal, d: float) -> np.ndarray:
    """The rover's footprint in the map when it parks `d` from `point_xy`, facing it along `normal`."""
    n = np.asarray(normal[:2], float)
    n = n / np.linalg.norm(n)
    xy = np.asarray(point_xy[:2], float) + n * d
    yaw = math.atan2(n[1], n[0])
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, -s], [s, c]])
    return (R @ FOOTPRINT.T).T + xy


def clear_distance(point_xy, normal, ignore: tuple[str, ...] = (), step_m: float = 0.01, span_m=(0.30, 1.60)) -> float:
    """The closest the rover can park facing a site point with its footprint clear of every structure by its own
    docking error. Structures the work reaches over (the stand the item is on) are cleared just the same: what the arm
    passes above, the wheels must still stay out of."""
    d = span_m[0]
    keep = [s for s in structures() if s["name"] not in ignore]
    while d <= span_m[1]:
        hull = hull_at(point_xy, normal, d)
        if all(polygon_gap(hull, corners(s["center"], (s["size_xy"][0] / 2, s["size_xy"][1] / 2), s["yaw"])) >= DOCK_ERROR_M
               for s in keep):
            return round(d, 3)
        d += step_m
    return float(span_m[1])


#: the surveyed occupancy map Nav2 localizes and plans on, in the map frame
NAV_MAP = SITE / "nav_map"
#: live lidar returns farther than this are not used to check a drive: the 2D slice meets rising regolith a few metres
#: out, which is ground, not an obstacle (research repo F141)
SCAN_CHECK_RANGE_M = 3.0


@lru_cache(maxsize=1)
def nav_map_occupied() -> np.ndarray:
    """Centres (x, y) in the map frame of the surveyed map's occupied cells."""
    import yaml
    from PIL import Image

    meta = yaml.safe_load((NAV_MAP / "map.yaml").read_text())
    img = np.array(Image.open(NAV_MAP / meta["image"]))
    res, (ox, oy) = float(meta["resolution"]), meta["origin"][:2]
    rows, cols = np.nonzero(img <= 255 * (1.0 - float(meta["occupied_thresh"])))
    return np.stack([ox + (cols + 0.5) * res, oy + (img.shape[0] - 1 - rows + 0.5) * res], axis=1)


def dock_path(start, goal, approach_m: float, corridor_m: float = 0.35, step_m: float = 0.05) -> list[tuple[float, float, float]]:
    """The poses (x, y, yaw) the dock servo (`procedural_move_base_to_pose`) drives the base through from `start` to
    `goal`: inside the goal's corridor straight in at the goal heading, otherwise to the corridor entry `approach_m` in
    front of the goal, turning to the goal heading on the way, then straight in."""
    (x, y, yaw), (tx, ty, tyaw) = start, goal
    d = np.array([math.cos(tyaw), math.sin(tyaw)])
    rel = np.array([x - tx, y - ty])
    along, lat = float(rel @ d), float(d[0] * rel[1] - d[1] * rel[0])
    entry = np.array([tx, ty]) + d * approach_m
    legs = [] if abs(lat) < corridor_m and -0.1 < along < approach_m + 1.0 else [((x, y, yaw), (entry[0], entry[1], tyaw))]
    legs.append((legs[-1][1] if legs else (x, y, tyaw), (tx, ty, tyaw)))
    poses = []
    for (ax, ay, ayaw), (bx, by, byaw) in legs:
        n = max(1, int(math.hypot(bx - ax, by - ay) / step_m))
        dyaw = (byaw - ayaw + math.pi) % (2 * math.pi) - math.pi
        poses += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n, ayaw + dyaw * k / n) for k in range(n + 1)]
    return poses


def swept_hits(poses, points: np.ndarray, inset_m: float = 0.05) -> np.ndarray:
    """The points (same frame as the poses) that the rover's footprint covers anywhere along `poses` and not already
    where it stands at the first: what the rover stands next to now is not in its way (docked, the hull is a few
    centimetres from the surveyed cells of what it works at). The footprint is taken `inset_m` in from its edges, one
    cell of the surveyed map: a cell grazed by a corner is the map's quantization, not a structure in the way (a sideways
    move off PDU-1's shelf clipped two cells of the next housing and touched nothing, ours_l4_pdu1_r2)."""
    if len(points) == 0:
        return points
    lo, hi = FOOTPRINT.min(axis=0) + inset_m, FOOTPRINT.max(axis=0) - inset_m
    xs = np.array([p[:2] for p in poses])
    near = points[np.linalg.norm(points[:, None, :] - xs[None, :, :], axis=2).min(axis=1) < 1.0] if len(points) < 20000 else \
        points[(points[:, 0] > xs[:, 0].min() - 1) & (points[:, 0] < xs[:, 0].max() + 1) & (points[:, 1] > xs[:, 1].min() - 1) & (points[:, 1] < xs[:, 1].max() + 1)]
    hit = np.zeros(len(near), bool)
    under = None
    for x, y, yaw in poses:
        c, s = math.cos(yaw), math.sin(yaw)
        q = (near - [x, y]) @ np.array([[c, -s], [s, c]])  # into the rover frame at that pose
        inside = (q[:, 0] >= lo[0]) & (q[:, 0] <= hi[0]) & (q[:, 1] >= lo[1]) & (q[:, 1] <= hi[1])
        under = inside if under is None else under
        hit |= inside
    return near[hit & ~under]

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

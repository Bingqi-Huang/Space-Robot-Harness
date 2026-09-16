"""Phase D0 held-out capability check: `route_block` (execution_plan §6.4 "known route obstruction").

The route_block scenery bakes a parked crew rover across the depot loop's west leg at (5.0, -2.25) (F48). The
surveyed localization map is the base without it, so AMCL also meets an unmapped obstacle. Nav2 drives dock ->
(4, 1.5) -> (6, -6); the straight line of the second leg runs through the rover, so reaching the goal means Nav2
routed round it. Run with D0_SCENERY=lunar_base_route_block. Helpers and readiness: d0_common.py.
"""
from d0_common import *  # noqa: F401,F403

for i, (xy, yaw) in enumerate((((4.0, 1.5), 0.0), ((6.0, -6.0), -1.33))):
    run(f"nav leg {i + 1}", lambda xy=xy, yaw=yaw: {**nav(xy, yaw), **base_err(xy, yaw)})
log("RESULT", mission=dict(mission))

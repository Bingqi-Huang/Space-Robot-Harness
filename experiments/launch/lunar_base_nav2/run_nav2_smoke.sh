#!/bin/bash
# Live Nav2 smoke test on the lunar base (F47): boots `openral deploy sim` with
# scenes/deploy/srb_lunar_base.yaml (SRB + sensor bridge + Nav2 + kernel + HAL + reasoner),
# waits for bt_navigator ACTIVE and the map->odom->chassis_base_link TF, then sends two
# NavigateToPose goals along the PDU aisle and reports the reached odometry.
#
#   [NAV2_SCENE=scenes/deploy/srb_lunar_base_route_block.yaml NAV2_GOALS="4,1.5;6,-6"] \
#   experiments/launch/lunar_base_nav2/run_nav2_smoke.sh <log_dir>
#
# Launch it detached (setsid nohup ... &): this tool's background tasks get killed as
# "low memory" around Isaac Sim (F46 §8). Shuts the whole deploy process group down at the end.
# (no `set -u`: ROS setup.bash reads unset variables)
LOG=${1:?log dir}
mkdir -p "$LOG"
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE/../../../openral"
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
setsid .venv/bin/openral deploy sim --config "${NAV2_SCENE:-scenes/deploy/srb_lunar_base.yaml}" --no-enable-octomap --no-object-detector > "$LOG/deploy.log" 2>&1 &
DEPLOY=$!
sleep 30
timeout 2700 .venv/bin/python "$HERE/nav2_goal_check.py" > "$LOG/goal.log" 2>&1
echo "CHECK_EXIT $?" >> "$LOG/goal.log"
kill -INT -- -$DEPLOY; sleep 45; kill -TERM -- -$DEPLOY 2>/dev/null; sleep 15; kill -9 -- -$DEPLOY 2>/dev/null
# python nodes that ignore SIGINT/SIGTERM survive the group kill (seen with the Nav2 relay/scan filter)
for p in $(ps -eo pid,args | grep -E "[o]penral/install/lib/openral_nav2_bringup" | awk '{print $1}'); do kill -9 "$p"; done
echo done > "$LOG/done"

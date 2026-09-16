#!/bin/bash
# Phase D0 live check: boots `openral deploy sim` on a Mission A/B scene (reasoner off) and runs
# the capability-path check against it, then tears the whole graph down.
#
#   [D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml] [D0_CHECK=d0_mission_b_check.py] [D0_STEPS=1,2] \
#   experiments/launch/lunar_base_d0/run_d0.sh <log_dir>
#
# Launch detached (setsid nohup ... &): this tool's background tasks get killed as "low memory"
# around Isaac Sim (F46 §8). (no `set -u`: ROS setup.bash reads unset variables)
LOG=${1:?log dir}
mkdir -p "$LOG"
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE/../../../openral"
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=${D0_DOMAIN:-77} ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST  # D0_DOMAIN=78 for a second graph on GPU 1
setsid .venv/bin/openral deploy sim --config "${D0_SCENE:-scenes/deploy/srb_lunar_base_mission_b.yaml}" --no-enable-octomap --no-object-detector > "$LOG/deploy.log" 2>&1 &
DEPLOY=$!
echo "DEPLOY_PID $DEPLOY sid $(ps -o sid= -p $DEPLOY)" > "$LOG/deploy.pid"
sleep 30
# the CLI setsid()s its `ros2 launch` child: a second session that neither the group kill nor a
# session kill on $DEPLOY reaches (stale launch trees survived runs 3-7 that way)
LAUNCH=$(pgrep -P "$DEPLOY" | head -1)
echo "LAUNCH_PID $LAUNCH sid $(ps -o sid= -p "$LAUNCH")" >> "$LOG/deploy.pid"
timeout 3000 .venv/bin/python "$HERE/${D0_CHECK:-d0_mission_b_check.py}" > "$LOG/check.log" 2>&1
echo "CHECK_EXIT $?" >> "$LOG/check.log"
# every descendant of the deploy CLI, collected while the tree is intact: the CLI, its `ros2 launch`
# and SRB's Isaac process each sit in their own session, so neither a group nor a session kill reaches
# the whole tree (run 8's Isaac outlived its teardown by 10 min). Never kill by name pattern: another
# graph may be running on the other GPU.
descendants() { for c in $(ps -o pid= --ppid "$1"); do echo "$c"; descendants "$c"; done; }
TREE=$(descendants "$DEPLOY")
echo "TREE $(echo $TREE | wc -w) pids" >> "$LOG/deploy.pid"
kill -INT -- -$DEPLOY; sleep 45; kill -TERM -- -$DEPLOY 2>/dev/null; sleep 15
kill -9 $DEPLOY $TREE 2>/dev/null; sleep 2
echo "LEFT $(for p in $TREE; do [ -d /proc/$p ] && echo $p; done | wc -l) of the tree still alive" >> "$LOG/deploy.pid"
echo done > "$LOG/done"

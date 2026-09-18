#!/bin/bash
# Step-wise development on a held graph (run_d0.sh with D0_HOLD=1): run another check against the live simulation in the
# state the last one left it, instead of booting a new one. For Ours: put the simulation back to before the failed step
# (the snapshot the earlier check saved) and continue the earlier record from there:
#
#   [D0_RESTART_BOUNDARY=1] D0_CHECK=ours_mission_check.py OURS_MISSION=b OURS_STOP_ON_FAILURE=1 \
#   OURS_RESUME_FROM=<earlier log> OURS_RESUME_BEFORE_STEP=<n> \
#   experiments/launch/lunar_base_d0/attach_d0.sh <graph log> <new log>
#
# D0_RESTART_BOUNDARY=1 restarts the capability server first (its code changed). The graph keeps its own run tag, so
# teardown_d0.sh <graph log> takes down everything started here too. Launch detached like run_d0.sh.
GRAPH=${1:?graph log dir}
LOG=${2:?new log dir}
mkdir -p "$LOG"
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE/../../../openral"
source /opt/ros/humble/setup.bash
source install/setup.bash
source ../ros/install/setup.bash
export ROS_DOMAIN_ID=${D0_DOMAIN:-77} ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
# camera images need large shared-memory segments, or most frames are lost in transport (fastdds_large_shm.xml)
export FASTRTPS_DEFAULT_PROFILES_FILE="$HERE/fastdds_large_shm.xml"
SPACE_LLM_API_KEY=$(grep -o 'sk-[A-Za-z0-9_-]*' "$HERE/../../../AGENT/VLM_provider.md" | head -1) && export SPACE_LLM_API_KEY
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
if [ -n "$D0_RESTART_BOUNDARY" ]; then
  for e in /proc/[0-9]*/environ; do
    p=${e#/proc/}; p=${p%/environ}
    grep -qzx "D0_RUN_TAG=$GRAPH" "$e" 2>/dev/null && tr '\0' ' ' < "/proc/$p/cmdline" | grep -q "capability_server/node.py" && kill -9 "$p"
  done
  D0_LOG="$LOG" D0_RUN_TAG="$GRAPH" setsid .venv/bin/python ../openral_ext/capability_server/node.py > "$LOG/capability_server.log" 2>&1 &
  sleep 20
fi
D0_ATTACH=1 D0_GRAPH_LOG="$GRAPH" D0_LOG="$LOG" timeout 14400 .venv/bin/python "$HERE/${D0_CHECK:-ours_mission_check.py}" > "$LOG/check.log" 2>&1
echo "CHECK_EXIT $?" >> "$LOG/check.log"
echo done > "$LOG/done"

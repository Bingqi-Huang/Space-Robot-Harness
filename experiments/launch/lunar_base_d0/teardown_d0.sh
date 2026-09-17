#!/bin/bash
# Take down a D0 graph (run_d0.sh, or one held with D0_HOLD=1) by its run tag.
#   experiments/launch/lunar_base_d0/teardown_d0.sh <log_dir>
LOG=${1:?log dir}
# Teardown by run tag: the CLI, its `ros2 launch` and SRB's Isaac process each sit in their own session, and
# `setsid` from a group leader forks, so neither a group kill nor a walk of $DEPLOY's children reaches the whole
# graph (run a3 left Isaac alive). Every process of the deploy carries D0_RUN_TAG=$LOG in its environment (set on that command only, so
# this script and its subshells do not); a graph
# on the other GPU carries its own. Never kill by name pattern.
tagged() { for e in /proc/[0-9]*/environ; do grep -qzx "D0_RUN_TAG=$LOG" "$e" 2>/dev/null && p=${e#/proc/} && echo "${p%/environ}"; done; }
TREE=$(tagged)
echo "TREE $(echo $TREE | wc -w) pids" >> "$LOG/deploy.pid"
kill -INT $TREE 2>/dev/null; sleep 45; kill -TERM $(tagged) 2>/dev/null; sleep 15
kill -9 $(tagged) 2>/dev/null; sleep 2
echo "LEFT $(tagged | wc -l) tagged processes still alive" >> "$LOG/deploy.pid"
if [ -n "$D0_VIDEO" ]; then
  # the teardown's SIGINT reaches ffmpeg mid-fragment: keep every complete fragment in a clean MP4
  ffmpeg -loglevel quiet -y -err_detect ignore_err -i "$D0_VIDEO" -c copy "$LOG/video_clean.mp4" && mv -f "$LOG/video_clean.mp4" "$D0_VIDEO"
fi

#!/bin/bash
# Run a list of D0 jobs on the run farm, one container per GPU at a time (docs/heldout_design.md §11). Start it inside
# tmux so it outlives the session that launched it:
#
#   tmux new-session -d -s <name> "experiments/launch/lunar_base_d0/farm_queue.sh <jobs file> <run root> [gpus]"
#
# A jobs line is `<run name> <env assignments...>` ('#' starts a comment); every GPU's worker takes the next line not yet
# taken, runs it as <run root>/<run name> through docker/runfarm/runfarm.sh and waits for its container to exit.
# <run root>/queue.log has one line per start and end (with the run's CHECK_EXIT).
JOBS=$(realpath "${1:?jobs file}")
ROOT=$(realpath -m "${2:?run root}")
GPUS=${3:-0 1 2 3 4 5}
HERE=$(cd "$(dirname "$0")" && pwd)
R=$(cd "$HERE/../../.." && pwd)
mkdir -p "$ROOT"
echo 0 > "$ROOT/.next"

claim() {
  exec 9> "$ROOT/.lock"
  flock 9
  n=$(cat "$ROOT/.next")
  echo $((n + 1)) > "$ROOT/.next"
  flock -u 9
  grep -v '^[[:space:]]*#' "$JOBS" | grep -v '^[[:space:]]*$' | sed -n "$((n + 1))p"
}

worker() {
  g=$1
  while line=$(claim) && [ -n "$line" ]; do
    name=${line%% *}
    envs=${line#* }
    echo "$(date '+%F %T') gpu$g start $name" >> "$ROOT/queue.log"
    "$R/docker/runfarm/runfarm.sh" "$g" "rf-$name" "$envs $HERE/run_d0.sh $ROOT/$name" > /dev/null
    docker wait "rf-$name" > /dev/null
    echo "$(date '+%F %T') gpu$g end $name $(grep -h '^CHECK_EXIT' "$ROOT/$name/check.log" 2>/dev/null)" >> "$ROOT/queue.log"
  done
}

for g in $GPUS; do worker "$g" & done
wait
echo "$(date '+%F %T') queue done" >> "$ROOT/queue.log"

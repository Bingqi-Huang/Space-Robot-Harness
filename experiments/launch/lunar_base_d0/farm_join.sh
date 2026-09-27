#!/bin/bash
# Add one GPU's worker to a farm_queue.sh batch already running: same jobs file, same run root, same claim counter
# (farm_queue.sh resets .next when it starts, so a second farm_queue.sh would restart the batch).
#   tmux new-session -d -s <name> "experiments/launch/lunar_base_d0/farm_join.sh <jobs file> <run root> <gpu>"
JOBS=$(realpath "${1:?jobs file}")
ROOT=$(realpath "${2:?run root}")
g=${3:?gpu}
HERE=$(cd "$(dirname "$0")" && pwd)
R=$(cd "$HERE/../../.." && pwd)
claim() {
  exec 9> "$ROOT/.lock"
  flock 9
  n=$(cat "$ROOT/.next")
  echo $((n + 1)) > "$ROOT/.next"
  flock -u 9
  grep -v '^[[:space:]]*#' "$JOBS" | grep -v '^[[:space:]]*$' | sed -n "$((n + 1))p"
}
while line=$(claim) && [ -n "$line" ]; do
  name=${line%% *}
  envs=${line#* }
  echo "$(date '+%F %T') gpu$g start $name" >> "$ROOT/queue.log"
  "$R/docker/runfarm/runfarm.sh" "$g" "rf-$name" "$envs $HERE/run_d0.sh $ROOT/$name" > /dev/null
  docker wait "rf-$name" > /dev/null
  echo "$(date '+%F %T') gpu$g end $name $(grep -h '^CHECK_EXIT' "$ROOT/$name/check.log" 2>/dev/null)" >> "$ROOT/queue.log"
done

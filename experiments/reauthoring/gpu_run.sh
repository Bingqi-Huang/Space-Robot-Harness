#!/bin/bash
# Run a farm queue on one GPU once that GPU is ours: several users (the re-authoring engineers, the ablation's live
# runs) share GPUs 0-5 through one lock per GPU, held for the whole queue; inside the lock it also waits until no
# container still holds the GPU (one simulation per GPU, also while a previous one tears down). Returns at once: the
# queue runs in tmux session <name>; its <run root>/queue.log gets a "start" line when it actually begins.
#
#   experiments/reauthoring/gpu_run.sh <gpu> <tmux session name> <jobs file> <run root> [<checkout>]
G=${1:?gpu}
NAME=${2:?session name}
JOBS=$(realpath "${3:?jobs file}")
ROOT=$(realpath -m "${4:?run root}")
W=$(realpath "${5:-$(pwd)}")
R=/mnt/SharedData/Research/Space_Robot_Harness
tmux new-session -d -s "$NAME" "flock $R/artifacts/runs/gpu_locks/gpu$G.lock bash -c 'until [ \"\$($R/experiments/reauthoring/gpu_free.sh $G)\" = free ]; do sleep 10; done; $W/experiments/launch/lunar_base_d0/farm_queue.sh $JOBS $ROOT $G'"
echo "queued on GPU $G as tmux session $NAME; watch $ROOT/queue.log"

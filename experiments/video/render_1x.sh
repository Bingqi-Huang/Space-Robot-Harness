#!/bin/bash
# Experiment I mission videos at 1x simulated time (10 frames per simulated second), Ours, one run per instance.
# One worker per GPU: experiments/video/render_1x.sh <gpu>. Workers share the run list (each run claimed once) and
# take the GPU through the farm's lock, so a worker waits for any run on its GPU (one Isaac instance per GPU).
# The replay runs from .worktree/ablation, whose SRB is pinned to exp1b (main's scene has items added later, F144).
G=${1:?gpu}
R=/mnt/SharedData/Research/Space_Robot_Harness; V=$R/artifacts/figures/exp1b/video_1x; E=$R/artifacts/runs/exp1b
LIST=$V/runs.txt
title() {
  case $1 in
    ours_a_pdu2) echo "Mission A, PDU-2 trips: reset (L0)";;
    ours_b_oru_pdu3) echo "Mission B, spare ORU to PDU-3 (L0)";;
    ours_a_bess) echo "Mission A, BESS trips: reset (L1)";;
    ours_a_isru) echo "Mission A, ISRU plant trips: reset (L1)";;
    ours_b_bat_bess) echo "Mission B, spare battery module to BESS (L1)";;
    ours_b_cons_habitat) echo "Mission B, consumables container to habitat (L1)";;
    ours_a_misreport) echo "Mission A, report names PDU-2, BESS tripped (L1)";;
    ours_l2a_pdu1_*) echo "Mission A, PDU-1 radiator shutter drawn (L2-A)";;
    ours_l2a_bess_*) echo "Mission A, BESS HVAC shutter drawn (L2-A)";;
    ours_l2b_habitat_*) echo "Mission B, destination occupied (L2-B)";;
    ours_l3_bess_*) echo "Mission A, BESS battery module failed (L3)";;
    ours_l3_isru_*) echo "Mission A, ISRU filter cartridge clogged (L3)";;
    ours_l4_pdu1_*) echo "Mission A, spare failed: cannibalize (L4)";;
  esac
}
while true; do
  run=$(flock "$LIST.lock" bash -c "head -1 $LIST; sed -i 1d $LIST")
  [ -z "$run" ] && break
  echo "$(date '+%F %T') gpu$G start $run" >> $V/render.log
  (
    flock 9
    until [ "$($R/experiments/reauthoring/gpu_free.sh $G)" = free ]; do sleep 10; done
    $R/docker/runfarm/runfarm.sh $G vid-$run "/home/bingqi/Programs/isaac-sim/python.sh $R/.worktree/ablation/experiments/video/replay_render.py $E/$run $V/replay/$run --fps 10 > $V/replay/$run.log 2>&1" > /dev/null
    docker wait vid-$run > /dev/null
  ) 9> $R/artifacts/runs/gpu_locks/gpu$G.lock
  docker run --rm --cpuset-cpus 30,31,62,63 -v /mnt/SharedData:/mnt/SharedData runfarm:22.04 bash -lc \
    "source /opt/ros/humble/setup.bash && nice -n 19 $R/openral/.venv/bin/python $R/experiments/video/track_from_bag.py $E/$run/bag $V/$run.track.json" > $V/$run.track.log 2>&1
  nice -n 19 taskset -c 30,31,62,63 python3 $R/experiments/video/mission_video.py $V/replay/$run $E/$run/ours/events.jsonl \
    $V/$run.mp4 --track $V/$run.track.json --fps 10 --title "Ours (agent harness) — $(title $run)" > $V/$run.compose.log 2>&1
  echo "$(date '+%F %T') gpu$G done $run $(ls $V/replay/$run | wc -l) frames, $(tail -1 $V/$run.compose.log)" >> $V/render.log
done
echo "$(date '+%F %T') gpu$G worker done" >> $V/render.log

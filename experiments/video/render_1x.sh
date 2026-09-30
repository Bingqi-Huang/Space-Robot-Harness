#!/bin/bash
# Experiment I mission videos at 1x simulated time (10 frames per simulated second), Ours, one run per instance.
# Chunked: `plan_chunks.py` writes $V/chunks.txt ("<run> <a> <b>"); each worker claims one chunk at a time and renders
# it (replay_render.py --only a,b) in its own container. A replay uses ~1.6 cores and a quarter of a GPU and no ROS, so
# several workers share one GPU (user 2026-09-30): experiments/video/render_1x.sh <gpu> <slot>, one tmux session each,
# only on GPUs with no simulation run. The worker whose chunk completes a run's frames (no other chunk of it still
# rendering) tracks and composes that run's video on its own GPU's cores.
# The replay runs from .worktree/ablation, whose SRB is pinned to exp1b (main's scene has items added later, F144).
G=${1:?gpu}
S=${2:?slot}
R=/mnt/SharedData/Research/Space_Robot_Harness; V=$R/artifacts/figures/exp1b/video_1x; E=$R/artifacts/runs/exp1b
LIST=$V/chunks.txt
# LunarBot's USD names its body textures by an absolute path on the development machine; on pro6000 they live in
# /mnt/SharedData/Research/lunarbot_textures and are mounted at that path in the render container only (the scored runs
# never had them). Without the mount the robot renders untextured (happened twice: 2026-09-27, 2026-09-30).
export RUNFARM_ARGS="-v /mnt/SharedData/Research/lunarbot_textures/textures:/home/bingqi/SharedData/Research/LunarSim/assets/USD_Assets/robots/lunarbot/configuration/materials/textures:ro"
BASE=$((32 * (G / 3) + 10 * (G % 3))); CPUS=$BASE-$((BASE + 9)),$((BASE + 64))-$((BASE + 73))
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
  read -r run lo hi <<< "$(flock "$LIST.lock" bash -c "head -1 $LIST; sed -i 1d $LIST")"
  [ -z "$run" ] && break
  c=vid-$run-${lo/./_}
  echo "$(date '+%F %T') gpu$G.$S start $run $lo-$hi" >> $V/render.log
  $R/docker/runfarm/runfarm.sh $G $c "/home/bingqi/Programs/isaac-sim/python.sh $R/.worktree/ablation/experiments/video/replay_render.py $E/$run $V/replay/$run --fps 10 --only $lo,$hi > $V/replay/$run.$lo.log 2>&1" > /dev/null
  docker wait $c > /dev/null
  echo "$(date '+%F %T') gpu$G.$S end $run $lo-$hi $(tail -1 $V/replay/$run.$lo.log)" >> $V/render.log
  expected=$(grep -m1 -o '^[0-9]* frames' $V/replay/$run.$lo.log | cut -d' ' -f1)
  [ "$(ls $V/replay/$run | wc -l)" = "$expected" ] || continue
  [ -z "$(docker ps -q --filter name=vid-$run-)" ] || continue
  mkdir $V/replay/$run.composing 2> /dev/null || continue
  docker run --rm --cpuset-cpus $CPUS -v /mnt/SharedData:/mnt/SharedData runfarm:22.04 bash -lc \
    "source /opt/ros/humble/setup.bash && nice -n 19 $R/openral/.venv/bin/python $R/experiments/video/track_from_bag.py $E/$run/bag $V/$run.track.json" > $V/$run.track.log 2>&1
  nice -n 19 taskset -c $CPUS python3 $R/experiments/video/mission_video.py $V/replay/$run $E/$run/ours/events.jsonl \
    $V/$run.mp4 --track $V/$run.track.json --fps 10 --title "Ours (agent harness) — $(title $run)" > $V/$run.compose.log 2>&1
  echo "$(date '+%F %T') gpu$G.$S done $run $expected frames, $(tail -1 $V/$run.compose.log)" >> $V/render.log
done
echo "$(date '+%F %T') gpu$G.$S worker done" >> $V/render.log

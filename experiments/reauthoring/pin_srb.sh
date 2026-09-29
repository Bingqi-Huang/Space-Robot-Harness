#!/bin/bash
# An exp1b-based checkout must simulate its own SRB, not the main checkout's: openral's deploy configs name the main
# checkout's SRB by absolute path (the simulator's cwd and the nav map), and `srb` imports the package the Isaac python
# has installed (the main checkout's). Point the configs at this checkout's SRB and put it first on the simulator's
# PYTHONPATH. Local to the checkout's openral worktree (not committed there).
#
#   experiments/reauthoring/pin_srb.sh <checkout>
set -e
W=$(realpath "${1:?checkout}")
M=/mnt/SharedData/Research/Space_Robot_Harness/space_robotics_bench
for f in "$W"/openral/scenes/deploy/srb_*.yaml; do
  sed -i "s#$M#$W/space_robotics_bench#g" "$f"
  grep -q "PYTHONPATH: \"$W/space_robotics_bench\"" "$f" || \
    sed -i "s#^  env_set:\$#  env_set:\n    PYTHONPATH: \"$W/space_robotics_bench\"#" "$f"
done
grep -h "cwd:\|PYTHONPATH\|memory_dir" "$W"/openral/scenes/deploy/srb_lunar_base_mission_a.yaml

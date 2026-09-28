#!/bin/bash
# An extension engineer's own checkout (docs/exp2/extension_spec.md §5): branch exp2/<method> from <base ref> in
# .worktree/exp2-<method>, so the engineer's edits and validation runs never touch the main checkout, from which the
# hidden cases run. The submodules are worktrees of the main checkout's own submodule repositories (shared objects and
# LFS store: nothing is downloaded); the untracked pieces a run needs are linked from the main checkout (the openral
# venv, the provider key file) or built here (ros/: the PLEXIL adapter may be rebuilt by the engineer).
#
#   experiments/exp2/make_worktree.sh <ours|plexil|europa_plexil> <base ref>
set -e
M=${1:?method}
BASE=${2:?base ref}
R=$(cd "$(dirname "$0")/../.." && pwd)
W=$R/.worktree/exp2-$M
git -C "$R" worktree add "$W" -b "exp2/$M" "$BASE"
for sub in openral space_robotics_bench; do
  commit=$(git -C "$W" ls-tree HEAD "$sub" | awk '{print $3}')
  rmdir "$W/$sub"
  git -C "$R/$sub" worktree add --detach "$W/$sub" "$commit"
done
# read-only at run time: openral's venv and ROS install (engineers do not change openral), the SPICE kernels, the key
for p in openral/.venv openral/install openral/build space_context/kernels AGENT/VLM_provider.md; do ln -s "$R/$p" "$W/$p"; done
# the EUROPA planner and dispatch-plan builds are copied: an engineer may rebuild them here
for p in baselines/europa/planner/build baselines/europa/plexil/build baselines/europa/plexil/plans/ActivityDispatch.plx; do
  cp -a "$R/$p" "$W/$p"
done
# the interface packages and the PLEXIL adapter, built from this checkout's sources in a pinned throwaway container
nice -n 19 docker run --rm --cpuset-cpus 30,31,62,63 -v /mnt/SharedData:/mnt/SharedData runfarm:22.04 bash -lc \
  "export PLEXIL_HOME=\$HOME/Programs/plexil && source /opt/ros/humble/setup.bash && cd $W/ros && colcon build --merge-install > build.log 2>&1; tail -3 build.log"
git -C "$W" status --short

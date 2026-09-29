#!/bin/bash
# A re-authoring engineer's own checkout (docs/reauthoring/spec.md): branch reauth/<baseline>-<case> from the Experiment I
# freeze (tag exp1b) in .worktree/reauth-<baseline>-<case>, built as experiments/exp2/make_worktree.sh builds Experiment
# II's (submodules as worktrees of the main checkout's own repositories; venv, install, kernels and key linked; ros/ and
# the EUROPA builds made or copied here, so the engineer may rebuild them).
#
#   experiments/reauthoring/make_worktree.sh <plexil|europa> <l2a|l2b|l3|l4>
set -e
B=${1:?baseline}
C=${2:?case}
R=$(cd "$(dirname "$0")/../.." && pwd)
W=$R/.worktree/reauth-$B-$C
git -C "$R" worktree add "$W" -b "reauth/$B-$C" exp1b
for sub in openral space_robotics_bench; do
  commit=$(git -C "$W" ls-tree HEAD "$sub" | awk '{print $3}')
  rmdir "${W:?}/${sub:?}"
  git -C "$R/$sub" worktree add --detach "$W/$sub" "$commit"
done
for repo in . openral space_robotics_bench; do
  git -C "$R/$repo" ls-files | while IFS= read -r f; do
    if [ -x "$R/$repo/$f" ] && [ -f "$W/$repo/$f" ] && [ ! -x "$W/$repo/$f" ]; then chmod +x "$W/$repo/$f"; fi
  done
done
for p in openral/.venv openral/install openral/build space_context/kernels AGENT/VLM_provider.md; do ln -s "$R/$p" "$W/$p"; done
for p in baselines/europa/planner/build baselines/europa/plexil/build baselines/europa/plexil/plans/ActivityDispatch.plx; do
  cp -a "$R/$p" "$W/$p"
done
nice -n 19 docker run --rm --cpuset-cpus 30,31,62,63 -v /mnt/SharedData:/mnt/SharedData -v "$HOME/Programs:$HOME/Programs" runfarm:22.04 bash -lc \
  "export PLEXIL_HOME=\$HOME/Programs/plexil && source /opt/ros/humble/setup.bash && source $W/openral/install/setup.bash && cd $W/ros && mkdir -p log && colcon build --merge-install > log/make_worktree_build.log 2>&1; tail -1 log/make_worktree_build.log"

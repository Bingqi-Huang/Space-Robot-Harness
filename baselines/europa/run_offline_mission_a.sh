#!/usr/bin/env bash
# Offline end-to-end check of the EUROPA->PLEXIL machinery on Mission A (execution_plan §21.6): same chain as
# run_offline.sh, the one domain (domain/lunar-base-model.nddl) and Mission A's goals -- every serviced unit restored,
# arm stowed, base at dock. Which unit is tripped comes from telemetry only (sim_boundary.py --tripped UNIT); press's
# own preconditions make the solver derive navigate_to_feature/dock_at_feature/press on that unit itself.
#   run_offline_mission_a.sh <run_dir> --tripped UNIT [--no-hold] [--fail CAP:N[:far] ...]
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${REPO:-$(cd $HERE/../.. && pwd)}
RUN=$1; shift
mkdir -p $RUN
export ROS_DOMAIN_ID=92 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PLEXIL_HOME=$HOME/Programs/plexil
export PATH=$PLEXIL_HOME/scripts:/usr/bin:/bin
source /opt/ros/humble/setup.bash
source $REPO/openral/install/setup.bash
source $REPO/ros/install/local_setup.bash
export LD_LIBRARY_PATH=$REPO/ros/install/lib:$HERE/plexil/build:$PLEXIL_HOME/lib:$LD_LIBRARY_PATH
(cd $HERE/plexil/plans && plexilc ActivityDispatch.ple > /dev/null)

python3 $HERE/sim_boundary.py "$@" > $RUN/boundary.log 2>&1 &
BOUNDARY=$!
python3 $HERE/host.py --run-dir $RUN --goal restored --goal stowed --final dock \
  > $RUN/host.log 2>&1 &
HOST=$!
sleep 2
$PLEXIL_HOME/bin/universalExec -c $HERE/plexil/interface-config.xml -p $HERE/plexil/plans/ActivityDispatch.plx \
  > $RUN/exec.log 2>&1 &
EXEC=$!
trap 'kill $BOUNDARY $HOST $EXEC 2>/dev/null' EXIT
wait $HOST $EXEC
cat $RUN/host.log

#!/usr/bin/env bash
# Offline end-to-end check of the EUROPA->PLEXIL machinery: sim_boundary.py stands in for the capability server, the
# real chain runs above it -- host.py (EUROPA) -> HostLink -> PLEXIL universalExec (ActivityDispatch.plx) ->
# ros/plexil_capability_adapter -> /space/capability/execute. Isolated graph, never the simulation's.
#   run_offline.sh <run_dir> [--fail CAP:N[:far] ...]
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${REPO:-$(cd $HERE/../.. && pwd)}   # the colcon install with the capability adapter and messages
RUN=$1; shift
mkdir -p $RUN
export ROS_DOMAIN_ID=92 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PLEXIL_HOME=$HOME/Programs/plexil
export PATH=$PLEXIL_HOME/scripts:/usr/bin:/bin   # no conda: ROS Humble's python 3.10
source /opt/ros/humble/setup.bash
source $REPO/openral/install/setup.bash   # openral_msgs (host.py's operator-console PromptStamped)
source $REPO/ros/install/local_setup.bash
export LD_LIBRARY_PATH=$REPO/ros/install/lib:$HERE/plexil/build:$PLEXIL_HOME/lib:$LD_LIBRARY_PATH
(cd $HERE/plexil/plans && plexilc ActivityDispatch.ple > /dev/null)

python3 $HERE/sim_boundary.py "$@" > $RUN/boundary.log 2>&1 &
BOUNDARY=$!
python3 $HERE/host.py --run-dir $RUN --goal depot_stand/slot_0@work --final dock > $RUN/host.log 2>&1 &
HOST=$!
sleep 2
$PLEXIL_HOME/bin/universalExec -c $HERE/plexil/interface-config.xml -p $HERE/plexil/plans/ActivityDispatch.plx \
  > $RUN/exec.log 2>&1 &
EXEC=$!
trap 'kill $BOUNDARY $HOST $EXEC 2>/dev/null' EXIT
wait $HOST $EXEC
cat $RUN/host.log

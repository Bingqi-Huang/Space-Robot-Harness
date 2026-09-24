#!/bin/bash
# Inside a ptrace-capable run container: every 20 s measure how far the costmap footprints / AMCL lag the sim clock
# (footprint_age.py); on a lag > 10 s, dump every thread's stack of controller_server, planner_server and amcl with gdb.
R=/mnt/SharedData/Research/Space_Robot_Harness; OUT=$1
cd $R/openral && source install/setup.bash
export FASTRTPS_DEFAULT_PROFILES_FILE=$R/experiments/launch/lunar_base_d0/fastdds_large_shm.xml
until grep -q LOCALIZED $OUT/check.log 2>/dev/null; do sleep 10; done
while true; do
  line=$(timeout 40 python3 $R/experiments/analysis/footprint_age.py 2>/dev/null | tail -1)
  echo "$(date +%T) $line" >> $OUT/freeze_watch.log
  if echo "$line" | python3 -c "import sys,ast; d=ast.literal_eval(sys.stdin.read().split(' clock')[0]); sys.exit(0 if any(v > 10 for v in d.values()) else 1)" 2>/dev/null; then
    for name in controller_server planner_server amcl; do
      for p in $(pgrep -x $name); do gdb -p $p -batch -ex "thread apply all bt" > $OUT/gdb_${name}_$p.txt 2>&1; done
    done
    echo "$(date +%T) DUMPED" >> $OUT/freeze_watch.log; exit 0
  fi
  sleep 20
done

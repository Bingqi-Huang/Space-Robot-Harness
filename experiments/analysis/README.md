# Analysis tools (post-hoc; simulator truth only for evaluation)

Run inside the run-farm image, pinned to the host cores, e.g.
`docker run --rm --user $(id -u):$(id -g) --cpuset-cpus 30,31,62,63 -v /mnt/SharedData:/mnt/SharedData runfarm:22.04
bash -lc "source /opt/ros/humble/setup.bash && nice -n 19 python3 experiments/analysis/<tool>.py <run>/bag"`
(`replay_pick_find.py` needs openral's venv: `cd openral && .venv/bin/python ...`).

- `bag_loc_error.py` -- localization error over a run (truth `srb/env0/robot` vs `map->odom->chassis_base_link`).
- `bag_freeze_scan.py` -- intervals where the local / global costmap footprint or AMCL's map->odom stops following
  the sim clock (the F112 §3 freeze).
- `bag_plan_lag.py` -- global plan start vs the rover's pose.
- `bag_tf_freshness.py` -- first / last stamp per /tf edge.
- `freeze_probe.py` -- live: costmap footprint vs a fresh TF lookup; dumps thread states on a freeze.
- `grab_costmap.py` -- live: one global costmap + AMCL pose to JSON.
- `replay_pick_find.py` -- replays every recorded pick `find` stage against the current interface fit.

Runs need `D0_BAG="<topics>"` to have a bag.

# experiments/evaluator_recorder

`recorder.py` -- see `docs/evaluator_violations.md` for the four violation classes this feeds and what
it does and does not subscribe. Method-independent (same topics regardless of which of PLEXIL,
EUROPA->PLEXIL or Ours is driving the run). Logs to `<run_dir>/evaluator/events.jsonl`.

```bash
source /opt/ros/humble/setup.bash && source <openral>/install/setup.bash && source <ros>/install/setup.bash
ROS_DOMAIN_ID=96 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    python3 experiments/evaluator_recorder/recorder.py --run-dir <run_dir> --selftest   # proves the mechanism, no simulation

# real use (against a live graph a session is actually running):
ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    python3 experiments/evaluator_recorder/recorder.py --run-dir <run_dir>
```

Never run with `ROS_DOMAIN_ID=77` except against a live graph a session is actually running -- the
`--selftest` path always uses 96.

`evaluation/violations.py` counts from this file (plus the already-existing `capability_server.log` and,
when present, the `robot_motion` rosbag) into `evaluation/rows.py`'s `evaluator_*_count` fields.

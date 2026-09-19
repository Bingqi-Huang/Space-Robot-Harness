# experiments/operator_console

`console.py` -- see `docs/operator_console.md` for what exists, what this builds, and
what `space_runtime/`/`ros/plexil_capability_adapter` would still need (not built
here, owned elsewhere). Logs to `<run_dir>/operator/events.jsonl`.

```bash
source /opt/ros/humble/setup.bash && source <openral>/install/setup.bash
ROS_DOMAIN_ID=94 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    python3 experiments/operator_console/console.py --run-dir <run_dir> --selftest   # proves the mechanism, no simulation

# real use (once space_runtime actually publishes PromptStamped -- see docs/operator_console.md):
ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    python3 experiments/operator_console/console.py --run-dir <run_dir>

# operator-initiated event with no agent message to reply to:
python3 experiments/operator_console/console.py --run-dir <run_dir> \
    --log-event escalation_request --authority-level tactical_goal --text "abort current attempt"
```

Never run with `ROS_DOMAIN_ID=77` except against a live graph a Session M session is
actually running -- the `--selftest` path always uses 94.

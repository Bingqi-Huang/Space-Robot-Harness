# experiments/operator_console

`console.py` -- see `docs/operator_console.md` for the full mechanism: Ours (`space_runtime/agent.py`),
the PLEXIL adapter (`ros/plexil_capability_adapter`'s `RequestOperator` Command) and the EUROPA host
(`baselines/europa/host.py`) all publish a request on `/space/operator/request` (or a report on
`/space/operator/report`) and this console replies on `/space/operator/reply`, matched by the
`request_id` the caller minted. Logs to `<run_dir>/operator/events.jsonl`.

```bash
source /opt/ros/humble/setup.bash && source <openral>/install/setup.bash
ROS_DOMAIN_ID=94 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    python3 experiments/operator_console/console.py --run-dir <run_dir> --selftest   # proves the mechanism, no simulation

# development: canned answers instead of stdin (one per line, consumed in order)
python3 experiments/operator_console/console.py --run-dir <run_dir> --answers-file answers.txt

# real use, against whichever domain the caller (Ours/PLEXIL/EUROPA) is actually running on:
ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    python3 experiments/operator_console/console.py --run-dir <run_dir>

# operator-initiated event with no agent message to reply to:
python3 experiments/operator_console/console.py --run-dir <run_dir> \
    --log-event escalation_request --authority-level tactical_goal --text "abort current attempt"
```

Never run with `ROS_DOMAIN_ID=77` except against a live graph a Session M session is
actually running -- the `--selftest` path always uses 94.

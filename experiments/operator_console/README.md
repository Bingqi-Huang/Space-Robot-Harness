# experiments/operator_console

`console.py` is mission control behind the Direct-with-Earth link, one for all three methods: Ours
(`space_runtime/agent.py`), the PLEXIL adapter (`RequestOperator` Command) and the EUROPA host publish on
`/space/operator/request` or `/space/operator/report`; the console answers on `/space/operator/reply`, matched by
`request_id`. The protocol is scripted and published (research repo `docs/heldout_design.md` §8): 300 s decision
time, flight-rule grant table for held approvals, "hold in a safe state" for any other request (ground re-authoring
required), reports acknowledged; the SPICE link gates delivery (`space_context/link.py`). Logs to
`<run_dir>/operator/events.jsonl` with wall and mission time and the ALFUS level of every answer.

```bash
source /opt/ros/humble/setup.bash && source <openral>/install/setup.bash
ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    python3 experiments/operator_console/console.py --run-dir <run_dir>            # scripted protocol (experiments)
python3 experiments/operator_console/console.py --run-dir <run_dir> --manual      # a person answers (demonstration only)
```

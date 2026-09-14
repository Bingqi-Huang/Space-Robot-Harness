# Handoff

State as of 2026-09-14 (late evening). **Phase A + Phase B both complete.**
Phase C in progress (scene half done, mission-logic half not started).
Task list: `todo.md`. Findings: `docs/research_findings.md` (F1–F39).

## Where things stand

openral `master` and SRB `main` both have the full Phase B2 stack merged
(9 numbered items + 2 cross-cutting reliability fixes + B3's reasoning-level
pass), all local commits, **not pushed to origin**. No open feature branches
— everything gets a fresh branch/worktree off `master`/`main` from here.
`space_robotics_bench` `main` also has `panel_remount_v2`'s scene merged
(Phase C).

## Next — Phase C mission-logic (not started)

`panel_remount_v2`'s SCENE is done and live-verified (F39): 2 decoy
pedestals, ~3.5 m real approach, terrain-safe. What's NOT built yet, per
§6.4:
- Covered examples (visible during authoring): the known displaced panel +
  remount sequence (already works, inherited from v1), a predefined
  retry/failure branch, a route-obstruction-with-alternate-route case.
- Held-out examples (hidden until freeze): access blocked by a movable
  object (inspect→diagnose→relocate→re-access→restore→verify), a
  semantically-inconsistent observed state needing closer inspection, a
  missing-preferred-capability case solvable via composition.
- The actual "inspection" mechanic — right now the two decoys are just
  *present*, nothing distinguishes "which site is the real fault" except
  hardcoded position. Needs a real observable signal (visual difference,
  a queryable state) the reasoner can act on, not a hidden coordinate.
- Perturbation switches (covered/held-out toggle) — none exist yet.
- §8.2's rule still applies: no scenario-specific decision rules baked into
  the harness/guard — the *scene* can encode fixed facts (which pedestal is
  real), but *what to do about it* must stay the reasoner's call.

Do not start Mission B until this is done and Mission A's real
orchestration needs are clear (§6.5, explicit ordering).

## Environment reference (reusable, don't rediscover)

- Both ROS setup.bash files (`/opt/ros/humble/setup.bash` +
  `install/setup.bash`) + `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=
  LOCALHOST` needed in *every* shell that touches this graph — a fresh Bash
  call starts with none of it.
- `openral deploy sim --config scenes/deploy/srb_panel_remount.yaml` brings
  up kernel+HAL+SRB+Nav2+reasoner. **Sensor bridge is a separate process**
  (`python3 install/lib/openral_hal_lunar_bot/sensor_bridge_node.py
  --ros-args -p robot_yaml:=... -p use_sim_time:=true` — not `ros2 run`,
  lacks structlog) and **must start within seconds of the graph coming up**
  or Nav2's `bt_navigator` lifecycle wedges waiting on `/odom` (F37, real,
  root-caused, deferred — fix is wiring the bridge into
  `deploy_e2e.launch.py`, not yet done).
- A reasoner started standalone (bypassing its normal launch tree, e.g. to
  inject an env var fix) comes up `unconfigured` — drive it through
  `configure` (id=1) then `activate` (id=3) via `lifecycle_msgs/srv/
  ChangeState` before it will tick (F38). `ros2 lifecycle`/`node list`
  don't enumerate by name on this host — use the service calls directly
  (F14).
- Readiness is **not** `ros2 topic list | grep <topic>` — false-positives
  right after a teardown/relaunch. Use a real functional check (an actual
  TF lookup, an actual dispatch, `ros2 topic hz` actually reporting a rate).
- **Never `pkill -f`** on this host — it has silently failed to signal real
  processes more than once this session (explicit-PID `kill -9` always
  worked). Re-`pgrep`/`ps` for the exact current PID before signaling —
  don't reuse one echoed by an earlier command.
- `srb agent rand --help`'s env-choices list is generated pre-boot and does
  **not** reflect a newly-added task — real registration only happens once
  Isaac Sim initializes (`srb/tasks/__init__.py` gates on
  `is_isaacsim_initialized()`). Don't chase this as a bug (F39) — just
  launch the real env by name and check the boot log for spawn errors.
- `srb`'s CLI resolves through Isaac Sim's own Python (`~/.local/bin/srb`
  → `isaac-sim/python.sh`), which is an editable install pointed at the
  **main checkout**, not whatever worktree you're sitting in — merge before
  live-testing a worktree's SRB task changes, not after.
- For a quick visual check of a scene: `srb agent rand -e <task>_visual
  env.robot=lunar_bot --headless --video`; the video lands under
  `logs/<task>/rand/<ts>/videos/.../episode-0.mp4` (gitignored) even if the
  process has to be force-killed rather than SIGINT'd cleanly. Extract
  frames with `ffmpeg -i <mp4> -vf "select=eq(n\,N)" -vframes 1 out.png`.
- GPU is a shared, singleton resource on this host — one live Isaac Sim
  instance at a time, always `nvidia-smi`/`ps aux` before launching, always
  verify clean teardown after (the wrapper's own SIGINT/SIGTERM often
  doesn't reach the actual `kit/python` child — check for it explicitly and
  `kill -9` directly if it's still there).

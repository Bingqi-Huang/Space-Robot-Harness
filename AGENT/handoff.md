# Handoff

State as of 2026-09-15. **Phase A + Phase B complete. Phase C mission-logic
(execution_plan §6.4) implemented + live-verified this session.**
Task list: `todo.md`. Findings: `docs/research_findings.md` (F1–F40).

## Where things stand

openral `master` unchanged this session. SRB `main` and this repo's `main`
both need `feat/panel-remount-v2-mission-logic` merged (this session's work:
scene changes in `panel_remount_v2/task.py`, `mission_verifier` updates,
`docs/panel_remount_v2_mission_logic_plan.md`, F40). No other open feature
branches — everything gets a fresh branch/worktree off `master`/`main`.

## Next — Phase C remainder

Mission-logic mechanism (scenario_variant switch, covered discrimination
signal, both held-out perturbations) is done and live-verified — see
`docs/panel_remount_v2_mission_logic_plan.md` (status: implemented) and
`docs/research_findings.md` F40. What's NOT done:

- §5's open question (mount-compatibility query capability) — deferred to
  Phase E's baseline-adapter work, not required for the mechanism itself.
- Covered-case route obstruction (plan doc §1, optional) — not started.
- Full end-to-end reasoner run through the held-out variants — gated on
  F37 (Nav2 lifecycle wedge / sensor-bridge launch wiring), not attempted
  this session; the verification done was scene-level only (`srb agent
  rand`/`zero`, no kernel/reasoner graph).
- Mission B — explicitly after Mission A's orchestration needs are clear
  (§6.5).

## F40, briefly (full writeup in research_findings.md)

The panel's spawn position had silently drifted ~2.8 m from its documented
offset since v1: Isaac Lab's `reset_root_state_uniform` **adds**
`pose_range` to the asset's default root state, it is not an absolute
pose — v1's `EventCfg` was written as if it were absolute. Fixed; also
moved `_ROCK_BLOCKING_POS` (held-out A) since the corrected panel jitter
range is now closer to it than before. Caught via a temporary debug print
of simulator ground truth in `_reset_idx` (removed after use) — pixel-
level video inspection alone did not catch this; the camera framing in
`panel_remount_v2_visual`'s recordings does not clearly resolve which
on-screen shape is which scene object at this zoom level, so treat that
video as a stability/crash check, not a precise-position check. For exact
poses, read simulator state directly (a temporary print, removed after).

## Environment reference (reusable, don't rediscover)

- Both ROS setup.bash files (`/opt/ros/humble/setup.bash` +
  `install/setup.bash`) + `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=
  LOCALHOST` needed in *every* shell that touches the openral/ROS graph —
  a fresh Bash call starts with none of it. Pure-`srb` scene checks
  (`agent rand`/`agent zero`, no `--interface ros`) don't need this.
- `openral deploy sim --config scenes/deploy/srb_panel_remount.yaml` brings
  up kernel+HAL+SRB+Nav2+reasoner. **Sensor bridge is a separate process**
  and **must start within seconds of the graph coming up** or Nav2's
  `bt_navigator` lifecycle wedges waiting on `/odom` (F37, deferred).
- A reasoner started standalone comes up `unconfigured` — drive it through
  `configure`(id=1)/`activate`(id=3) via `lifecycle_msgs/srv/ChangeState`
  (F38). `ros2 lifecycle`/`node list` don't enumerate by name on this host.
- Readiness is **not** `ros2 topic list | grep <topic>` — use a real
  functional check.
- **Process hygiene, hard-won this session**: never `pkill -f`. But also
  don't fully trust `pgrep -f <pattern>` right after backgrounding a
  `srb`/Isaac Sim launch — it can match a short-lived transient helper
  fork instead of the real `kit/python` process, and killing that "PID"
  is a silent no-op while the real instance keeps running. This session
  leaked 4 orphaned instances this way before catching it via `nvidia-smi`
  showing load with no tracked PID left. Correct pattern: capture `$!`
  from the backgrounded wrapper, `ps --ppid $!` a few seconds later for
  the real child, and always `ps aux | grep kit/python` + `nvidia-smi`
  before AND after every launch/kill to confirm exactly one (or zero)
  instance — don't trust a `kill`'s silence as proof it worked.
- `srb agent rand --video` / `agent zero` **never stop on their own** —
  no duration flag. `SIGINT` after a bounded wait (~150-170s wall time
  for a 60s-episode video: boot + episode + mux margin), poll for exit,
  `kill -9` if still alive after ~60s more. Waiting for natural exit
  hangs indefinitely.
- `srb agent rand --help`'s env-choices list is generated pre-boot and
  does **not** reflect a newly-added task (`srb/tasks/__init__.py` gates
  registration on `is_isaacsim_initialized()`) — not a bug, just launch
  the real env by name.
- `srb`'s CLI resolves through Isaac Sim's own Python, an editable
  install pointed at the **main checkout**, not whatever worktree/branch
  you're sitting in if that's a separate directory — a same-directory
  `git checkout -b` (no `git worktree add`) does not have this problem.
- Quick scene check: `srb agent rand -e <task>_visual env.robot=lunar_bot
  --headless --video`; video lands under `logs/<task>/rand/<ts>/videos/
  .../episode-0.mp4` (gitignored). `ffprobe`/`ffmpeg -vf "select=eq(n\,N)"
  -vframes 1` to extract frames — but see F40: this camera framing does
  not clearly resolve object identity/position, only stability/crashes.
- GPU is a shared, singleton resource — one live Isaac Sim instance at a
  time, always verify before AND after.

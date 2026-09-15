# Handoff

State as of 2026-09-15 (late night). **Phase A + B complete. Phase C: C1 merged,
C2 built + verified; C3 interaction layer done (F44); C4 Mission A done (F45); C5 Mission B done (F46), next C6.**
Task list: `todo.md`. Findings: `docs/research_findings.md` (F1–F47).

## Where things stand

- Branches (user rule: only trunk + the working dev branch): SRB `main` + dev
  branch `feat/lunar-base-scene` (6c04598, all Phase C work continues here);
  openral `master` only (a253ef3, includes the 0.6 m/s bound); research `main`.
  Pushed 2026-09-15: SRB now lives in **git@github.com:DsslRobot/srb_assets.git**
  (`origin`; non-fork because GitHub refuses LFS uploads to public forks),
  `main` + `feat/lunar-base-scene`; the old fork is remote `fork` (only its stale
  `main` left), `upstream` = AndrejOrsula. openral `master` pushed, old remote
  branches deleted. `.gitmodules` points SRB at srb_assets (branch = dev branch).
- Review page: https://claude.ai/artifact/KAmnfrHaxBom4RnRNLUwMA (rev 2, pre-F43
  layout changes).
- LunarBot conventions now (F43): REP-103 base twist (+v toward the camera end,
  +ω CCW); keyboard teleop base mode W/S drive, A/D and C/V yaw; kernel bound
  0.6 m/s / 0.5 rad/s, Nav2 caps 0.57 / 0.47; Mid-360 inverted (F42).
- PhysX `omni.physx.plugin` warnings are hidden by SRB (wheel-cylinder log flood);
  `SRB_PHYSX_WARNINGS=1` to see them.

## C2 — what was built (all in `space_robotics_bench/assets/lunar_base/`)

Pipeline, rerun top to bottom after any layout edit:
`python3 scene/build_terrain.py && python3 scene/build_scene.py`
(build_scene calls `bake_albedo.py` and Blender's pxr via `usd_writer.py`;
prints placement problems and <2 m clearances — both must be empty).
- `scene/layout.yaml` — DEM window (Site01 row 1950 col 1970), noise/craters,
  albedo bake, sun (12° elev, bearing 200°), 7 pads, 7 roads, 23 placements.
- Terrain: one world-space surface (DEM + noise lattices + power-law craters)
  sampled by near 200 m @0.4 m (collider; graded core platform, flat pads,
  ship pad NW at +1.64 m), mid 600 m ring @2 m (up-facing vertex normals +
  baked 8192 normal/albedo maps) and far 6 km @20 m; coarser fields sink
  under finer ones and match on borders. Near albedo 8150² (roads, wheel
  tracks, sintered pads); 1 240 OmniLRS rocks (instanceable).
- USD prim order: `/lunar_base/lidar` (terrain + one box per structure,
  invisible, no collider) is the first Mesh on purpose (F41); `terrain`
  carries the collider; assets referenced with their own convex hulls.
- SRB: `srb/assets/scenery/lunar_base.py` (`LunarBase`, Moon, fixed sun, no
  sun randomization, env_spacing 200) and task `lunar_base` (+`_visual`),
  LunarBot fixed on the dock (zero pose_range deltas, F40).
- Checks: `scene/render_review.py <out> [views]` (standalone RTX, no physics);
  `scene/srb_scene_check.py <out>` (real SRB env: settle, drive, lidar
  diagnostics, renders); `srb_drive_check.py` (open-loop moves + first
  reference route, ~2 min); `srb_teleop_check.py` (keyboard + cmd_vel signs,
  ~1 min). Keep checks short; do not run long open-loop drives.
- Processing fixes this round: fake glTF alpha dropped; `material_overrides`
  in processing.yaml (PV cell sheet push + PV glass look); PDU yaw −90 so
  the switch panel faces the sun/roads.

## C3 — interaction layer (done, F44)

- Props authored by `assets/lunar_base/process/author_props.py` (CC0) and processed like any
  asset (`keep_origin`, `source_root: authored`): staging_stand, pdu_service_panel (button z 0.78,
  StatusLamp z 1.02, cover ledge), pdu_service_shelf (z 0.50, 1.05 m beside the panel),
  service_cover (dynamic 0.5 kg).
- `layout.yaml` props / dynamic_objects / inspection_points → `scene/interaction.py` →
  `usd/scene/lunar_base/interaction.json` (frames, object spawns, work + view poses) and
  `/lunar_base/interaction/*` prims. `srb.assets.scenery.lunar_base`: objects spawned as
  `lb_<name>` with fixed reset events (`events.reset_lb_<name>`, pose_range = delta, F40);
  `set_status_lamp(env_ids, "pdu_2_panel", rgb)`.
- Checks: `scene/srb_settle_check.py` (settle ×3, shelves, lamps, renders; ~6 min) PASS.

## C4 — Mission A (done, F45)

- Task `lunar_base_mission_a` (`srb/tasks/mobile_manipulation/lunar_base_mission_a/task.py`):
  `scenario` covered | heldout_cover_obstruction | heldout_status_mismatch, `faulted_pdu`,
  `reported_pdu` (auto), `terminate_on_success`; `mission_state()` = verifier truth,
  `cover_blocks()` = button inside the cover plate footprint.
- Oracle + recorder: `~/Programs/isaac-sim/python.sh assets/lunar_base/scene/srb_mission_a_run.py
  <out> --scenario <s> [--no-video] [--arm-only]` (`--arm-only` teleports to the press work pose to
  debug arm steps in ~2 min). No-video run 3–5 min wall; with video 8–13 min. Run ≤2 recorders at once
  (3 crashed one with Vulkan DEVICE_LOST and it hung).
- Arm: `scene/rm75_ik.py` (URDF chain, mount calibrated in sim, DLS with limit clamping) → joint
  targets → residual correction. READY = (0, −1.0, 0, −1.4, 0, 1.2, 0), tool point 0.45 m past the
  −X hull edge. Handle grasp: TCP 35 mm past the bar centre (cage).
- Videos: `assets/lunar_base/review/mission_a/mission_a_<scenario>.mp4` + `.json` phases.

## C5 — Mission B (done, F46)

- Task `lunar_base_mission_b`: `scenario` covered | heldout_destination_occupied | heldout_spare_swapped,
  `destination` (pdu_1), `terminate_on_success`; `where_is(object)` / `on_support()` = verifier truth.
- `~/Programs/isaac-sim/python.sh assets/lunar_base/scene/srb_mission_b_run.py <out> --scenario <s> [--no-video]
  [--arm-only --object spare_crate --place-on depot_stand/slot_1]` (arm-only teleports to the pick pose; ~5 min).
  Full runs: 400–690 s sim, 17–28 min wall with video.
- Shared primitives: `scene/lunar_oracle.py` (`Oracle`: base, IK arm, hook_pick/hook_place, carry rate limits,
  follow camera, `snapshot()` close-ups). Mission A script uses it too (regression PASS).
- Spares: `processing.yaml top_handle` (bar 0.16 m, standoff 0.10 m). Grasp = hook: base reverses 0.22 m to slide
  the flat closed gripper under the bar, arm lifts; EG2 pinch/cage slips (F46 §3). Don't pinch 1 kg objects.
- Depot stand is 1.30 m wide now (slots ±0.32); scene rebuilt (`build_scene.py`, 30 s).
- Launch long Isaac batches with `setsid nohup` — the tool's background tasks were killed as "low memory" with
  237 GB free (F46 §7).

## Next — C6 verification + wrap-up

Done: settle re-check PASS; Nav2 on the lunar base live (F47, openral 60345fd). Open: Nav2 along-track overshoot
(~0.8 m at rest from 0.57 m/s; lateral drift fixed), route-block/loop-road variants, retire `panel_remount_v2`; then Phase D/E per
execution plan (space_context, harness-driven Mission A/B through the OpenRAL graph instead of the oracle).

## Lessons from the rejected scene (F40 addendum, F41)

- `reset_root_state_uniform` pose_range is a delta on the default root
  state, not an absolute pose.
- Spawning a body overlapping a collider produces a silent PhysX launch
  over ~20 ticks — no log warning. Check spawn overlaps offline, trace
  pose/velocity per tick to sleep, cap `max_depenetration_velocity`.
- `panel_remount_v2_visual`'s recording camera can't resolve object
  identity or ground contact. "Works" requires multi-angle views + a user
  look, not a clean log and a few top-down frames.

## Environment reference (reusable, don't rediscover)

- Both ROS setup.bash files (`/opt/ros/humble/setup.bash` +
  `install/setup.bash`) + `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=
  LOCALHOST` needed in *every* shell that touches the openral/ROS graph —
  a fresh Bash call starts with none of it. Pure-`srb` scene checks
  (`agent rand`/`agent zero`, no `--interface ros`) don't need this.
- `openral deploy sim --config scenes/deploy/srb_lunar_base.yaml` (or
  `srb_panel_remount.yaml`) brings up kernel+HAL+SRB+sensor bridge+Nav2+reasoner;
  the bridge is declared under `simulator.bridges` and Nav2 waits for it (F47).
  Live smoke: `experiments/launch/lunar_base_nav2/run_nav2_smoke.sh <logdir>`
  (launch detached). Kill leftover `openral_nav2_bringup` python nodes after runs.
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

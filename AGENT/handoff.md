# Handoff

State as of 2026-09-15 (late night). **Phase A + B complete. Phase C: C1 merged,
C2 built + verified; C3 interaction layer done (F44), next C4 Mission A task.**
Task list: `todo.md`. Findings: `docs/research_findings.md` (F1–F43).

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

## Next — C4 Mission A task

Scenario block on the lunar_base task: faulty PDU (lamp red), covered case = walk up, inspect,
press; held-out = cover leaning on the faulty panel's button, lamp/physical mismatch. Verifier
truth: TCP within tolerance of `<pdu>_panel/press` + lamp state set by the task. Then §8.4
manipulation feasibility with the Phase B procedural skills (press, pick cover, place) and
§8.5 Nav2 (F37 still open).

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

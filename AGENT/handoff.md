# Handoff

State as of 2026-09-15 (evening). **Phase A + B complete. Phase C restarted:
the user rejected `panel_remount_v2` outright; a full lunar-base scene
redesign is proposed and awaiting user decisions.**
Task list: `todo.md`. Findings: `docs/research_findings.md` (F1–F41).

## Where things stand

- openral `master`, SRB `main`, research `main` all merged, no open branches.
  `panel_remount_v2` + its mission-logic code remain in SRB `main` as a
  superseded reference; do not build on it.
- User's rejection (multi-angle GUI inspection): too simple, SRB-assets
  only, a solar panel sitting on a pedestal top is nonsense, a pedestal
  floats above terrain, the panel is out of arm reach, the panel still
  tumbles off. Wants a good-looking lunar base with real buildings and
  diverse operable assets, built from experiment needs first; internet and
  Isaac assets allowed. Memory: `feedback-scene-quality-bar`.
- This round was planning-only (docs + research, no code, no sim runs).

## Next — C2 terrain + layout blockout

Design: `docs/lunar_base_scene_design.md` (read the scope-correction box at the
top first: no fine articulation; maintenance = touch waypoints / dummy button).
Evidence: `docs/lunar_base_research/`.

All simulation work lives in the SRB fork (user convention). C1 is done and
merged into SRB `main`: `space_robotics_bench/assets/lunar_base/`
- `manifest.yaml` + `fetch_assets.py` — 81 sources; `raw/` git-ignored (3.6 GB+).
  19 Sketchfab items need a token; only the 8 the user approved were fetched
  with it (user's account has a 10-download quota — never re-run those).
- `processing.yaml` + `process/process.py` (Blender 4.5 headless, one run per
  output) → `usd/<category>/<name>/` (git LFS) + git-ignored `previews/`.
  20 assets, user approved the look (rev 2), gallery
  https://claude.ai/artifact/EjraQQQRg3251eNQpUnF9U.
- Pipeline gotchas found: Blender bound_box is stale after mesh.transform until
  `view_layer.update()`; Blender's USD exporter drops textures unless the
  material is a Principled BSDF graph (glTF unlit materials rebuilt first);
  collapse-decimation of unwelded meshes throws spikes (weld first); Isaac
  Lab's `UsdFileCfg` only modifies existing collision/rigid APIs, so colliders,
  physics material and mass are authored in the USD.

C2 steps: load the batch in Isaac Sim once the GPU is free (the user had an
Isaac GUI instance open) → merge many-mesh statics → LOLA Site01 DEM terrain
with graded pads + roads → place zones per design §4 → bake terrain + static
exteriors into the scenery's single lidar mesh → multi-angle renders + GUI
walkthrough → user layout approval.

Key constraints the new scene must respect (F41): no infrastructure at
fixed z on procedural relief (it is not flat); lidar/Nav2 only see the
scenery's first Mesh child; grasp features at z 0.45–1.00 m, 0.05–0.35 m
beyond the arm-end (−X) hull edge, 15–45 mm wide, ≤~1 kg; ≥2 m aisles;
sim ≈12 Hz so keep the core compact and dynamic bodies few.

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

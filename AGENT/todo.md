# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

A0–A4 done. See `docs/research_findings.md` before designing any mechanism.

---

## Phase B: Generic OpenRAL on SRB — ✅ COMPLETE (2026-09-14)

Per execution_plan.md §18. Embodiment: **LunarBot** (user directive).

### Slices 1–3 + `panel_remount` v1 — ✅ (2026-09-13)

Full records: `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_procedural_kind.md`,
`docs/phase_b_lunar_bot_arm_gripper.md`, `docs/mission_a_panel_remount.md`.
All verified live through the real candidate_action→kernel→safe_action→
HAL→SRB path. **F11/F12/F15/F16/F17/F18** — see `docs/research_findings.md`.

### Phase B2 — LunarBot capability set (execution_plan §8.3) — ✅ ALL 9 ITEMS + B3

Design: `docs/lunar_bot_capability_set_plan.md`. Merged into openral `master`
(`ec95fe8`+) and SRB `main` (`6d8a388`+); not pushed to origin. Every item
verified live, most with real bugs found+fixed along the way — full detail
in `docs/research_findings.md` F19–F38, this is the compressed index:

- [x] 1. RM-75 limits (F22). [x] 2/2b. Sensor bridge + SRB deploy backend
      (F25–F29) — sensor bridge still standalone, not in
      `deploy_e2e.launch.py`. [x] 2c. RTX Lidar parked (F24, upstream bug).
- [x] 3/4. Five procedural rSkills + F19 steer-before-drive fix (F30).
      `move_ee_to_pose` has a residual precision gap, well inside
      panel_remount's tolerance.
- [x] 5. Nav2 — kernel-checked `/cmd_vel` relay, live-verified moving the
      robot (F32/F33/F36). **Open (F37, deferred, root-caused)**:
      `bt_navigator` needs `sensor_bridge_node` running before Nav2's
      lifecycle bringup starts, or it wedges — fix is the same
      "wire sensor_bridge into deploy_e2e.launch.py" item as #2.
- [x] 6. MoveIt for RM-75 — `ros2_rm_robot` vendored per user decision
      overriding CLAUDE.md §1.9 (F31, license was undeclared upstream).
      F33's kernel rejection fully root-caused + fixed (F36): a units
      mismatch, not a bad waypoint. `move_group.launch.py` still standalone.
- [x] 7. Mission verifier (`openral_ext/mission_verifier/`), live-verified,
      merged into research-repo `main`.
- [x] 8. §19 run-manifest writer (`openral_ext/run_manifest/`), merged —
      writes what's real, honestly omits what has no source yet.
- [x] 9. Kernel magnitude checks, all 4 remaining modes (F35), 245/245
      kernel tests. Found+deferred: dormant OOB-stride risk in 3
      pre-existing modes (needs `horizon>1`, nothing sends that today).
- [x] Two cross-cutting reliability bugs found+fixed (F34): resident-skill
      cache ignored `goal_params_json`; e-stop recovery didn't reach the
      HAL/runner latches without a second broadcast.
- [~] B3: reasoner-in-the-loop, real LLM (DeepSeek-V4.1-Flash via
      user-supplied gateway, F38). **Reasoning exit condition MET** — 60+
      ticks correctly decomposed a 2-step instruction, picked a real skill
      with sound rationale, never double-dispatched. 2 bugs found+fixed
      (gateway needs `tool_choice="auto"` → new `OPENRAL_REASONER_TOOL_CHOICE`
      env; host SOCKS proxy crashed the client). **Physical two-step
      completion not reached this session** — the chosen skill's one-time
      VLA cold-start download (11+ GB, still going after ~15 min) was
      deliberately torn down to free the shared GPU for Phase C's
      visual-check pass rather than left contending for it — not a
      defect, not reattempted; next attempt starts warmer (venv cached).

**F20** (JOINT_* wire row full-width) found+fixed during item-3 prep.

---

## Phase C: Long-horizon mission construction (execution_plan §6.4) — RESTARTED

**`panel_remount_v2` rejected by the user 2026-09-15** (too simple, SRB-assets
only, panel on a pedestal top, pedestal floating, panel out of reach, panel
still tumbling). Not patched — the whole scene is being redesigned. Its code
(F39/F40 fixes, `scenario_variant`) stays in git history as reference only.

- [x] Research (4 surveys) — `docs/lunar_base_research/`: NVIDIA/SimReady
      assets, NASA/internet assets + licenses, lunar sims (OmniLRS), SRB
      integration + LunarBot manipulation envelope. F41.
- [x] Redesign proposal — `docs/lunar_base_scene_design.md`: "Connecting
      Ridge Outpost" (habitat, power field, comm station, landing pad + cargo
      depot, ISRU yard, rover dock), zone→case mapping, verification protocol.
- [x] User decisions: real LOLA DEM + procedural detail; ~50×50 m core; bake
      statics into the single lidar mesh. **Scope correction**: no fine
      articulation — good-looking downloaded assets, maintenance = touch
      waypoints / dummy button (memory `feedback-scope-no-fine-manipulation`).
- [x] Asset round 2 + 66-item shortlist; all sim assets live in the SRB fork
      (`space_robotics_bench/assets/lunar_base/`, branch `feat/lunar-base-assets`):
      manifest (81 sources) + fetcher; 68 free downloads + 8 Sketchfab-token picks.
- [~] C1 asset processing — Blender pipeline (`processing.yaml`, `process/`),
      batch 1 = 20 real-scale USDs with colliders, pxr structure check all OK,
      gallery https://claude.ai/artifact/EjraQQQRg3251eNQpUnF9U.
      **Waiting on user look review.** Not yet loaded in Isaac Sim (user's GUI
      instance held the GPU). Static assets with many meshes (battery container
      1451, Starship 127) need meshes merged before scene use.
- [ ] C2 terrain + blockout → user layout approval. [ ] C3 interaction points
      (touch waypoints / dummy buttons) + settle checks. [ ] C4 Mission A task.
      [ ] C5 Mission B task. [ ] C6 full §8 verification + docs.
- Carried over, still open: mount/semantic query capability for perception
  (Phase E); full reasoner run through held-out cases gated on F37.

---

## Rules

- Branch or worktree per task; delete after **merge** (AGENT.md §1).
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3). Pure-Python logic
  smoke checks (no ROS/simulator) before a live test are fine and cheap —
  do them first, then one decisive live pass, not exhaustive repeated runs.
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code until Phase B observes real
  failures calling for it** (plan §21.6–7) — Phase B is now done; revisit
  this gate if Phase E work starts needing it.
- On this shared host, kill only exact PIDs, never a pattern — `pkill -f`
  has silently failed to signal real processes on this host more than
  once this session; explicit-PID `kill -9` has always worked (F10/F30/F38).
  `pgrep -f <pattern>` right after backgrounding a `srb`/`isaac-sim` launch
  can also match a wrong/transient PID (a short-lived helper fork) instead
  of the real long-running `kit/python` process — this session leaked 4
  orphaned Isaac Sim instances this way before catching it. Prefer `$!`
  from the backgrounded wrapper, then `ps --ppid $!` after a few seconds
  to get the real child; always `ps aux | grep kit/python` before AND
  after every launch/kill to confirm exactly one (or zero) instance.
- `srb agent rand --video`/`agent zero` do **not** stop on their own —
  there is no duration flag; they run until signaled. Send `SIGINT` after
  a bounded wait (a 60s-episode video needs ~150-170s wall time: boot +
  the episode + mux margin), then poll for exit, `kill -9` if still alive
  after ~60s. Waiting for natural exit hangs indefinitely (this session's
  first attempt waited 9 minutes before realizing this).
- `ros2 lifecycle`/`node list` don't work on this host — use direct
  `lifecycle_msgs/srv/ChangeState`/`GetState` service calls (F14). A node
  started standalone (bypassing its normal launch tree) comes up
  `unconfigured` and needs manual configure+activate calls (F38).
- Any shell running `ros2`/`srb`/`openral` CLI commands needs **both**
  `/opt/ros/humble/setup.bash` **and** `install/setup.bash` sourced (openral)
  every time — a fresh Bash call starts with neither.
- `srb agent rand --help`'s env-choices list is generated pre-boot and does
  NOT reflect newly-added tasks — registration only happens once Isaac Sim
  is actually initialized (`srb/tasks/__init__.py`); don't chase this as a
  registration bug (F39).
- A `ros2 topic list` presence check is **not** a reliable readiness signal
  right after a teardown/relaunch — use a real functional check (F30).

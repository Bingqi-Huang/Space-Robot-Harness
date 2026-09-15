# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

A0–A4 done. See `docs/research_findings.md` before designing any mechanism.

---

## Phase B: Generic OpenRAL on SRB — ✅ COMPLETE (2026-09-14)

Embodiment **LunarBot**. Records: `docs/phase_b_*.md`, `docs/lunar_bot_capability_set_plan.md`,
findings F11–F38 (+F47 for Nav2). B1 HAL/procedural kind/panel_remount v1; B2 items 1–9 all live-verified
(RM-75 limits, sensor bridge + SRB deploy backend, 5 procedural rSkills, Nav2 relay — **F37 closed by F47**,
MoveIt (`move_group.launch.py` still standalone), mission verifier, run manifest, kernel checks).
- [~] B3 reasoner-in-the-loop with a real LLM (F38): reasoning exit condition met; physical two-step completion
      not reached (VLA cold download torn down to free the GPU). Needs the gateway env from `AGENT/VLM_provider.md`.

---

## Phase C: Long-horizon mission construction (execution_plan §6.4) — RESTARTED

**`panel_remount_v2` rejected 2026-09-15** → scene redesigned; v2 task retired in C6 (F48).

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
- [x] C1 asset processing — Blender pipeline (`processing.yaml`, `process/`),
      20 real-scale USDs, user approved look 2026-09-15 after rev 2 (PV arrays
      ×0.63, MMSEV/ExoMars at LunarBot size, crate + ORU 1 kg (user), friction
      0.8/0.6 + restitution 0.05 on all colliders). Merged into SRB `main`.
      Gallery https://claude.ai/artifact/EjraQQQRg3251eNQpUnF9U.
- [x] C2 terrain + blockout — SRB dev branch `feat/lunar-base-scene` (6c04598); mission
      sites moved closer per user; drivable road network + clearance checks;
      landing pad cut to platform level. F42 lidar + F43 base twist/teleop/log
      fixes and 0.6 m/s bound (openral master a253ef3) verified in SRB.
- [x] C3 interaction layer (SRB fd3dbc3, F44): PDU service panels (reset button,
      status lamp, cover ledge), spares shelves, depot staging stand, spare ORU +
      crate + service cover, interaction.json (frames, work/view poses); §8.1
      offline checks + §8.2 settle PASS.
- [x] C4 Mission A task (F45): `lunar_base_mission_a` (covered /
      heldout_cover_obstruction / heldout_status_mismatch; verifier = press
      truth + lamps + cover-over-button + dock + stow). Scripted oracle
      `scene/srb_mission_a_run.py` completes all three with verifier success;
      follow-camera videos in `assets/lunar_base/review/mission_a/`. REACH
      press/grasp corrected to 0.45 m (work poses regenerated).
- [x] C5 Mission B task (F46): `lunar_base_mission_b` (covered /
      heldout_destination_occupied / heldout_spare_swapped). Spares got bail
      handles and are hooked (EG2 pinch slips); shared oracle
      `scene/lunar_oracle.py`; depot stand widened to 1.30 m. All three cases
      verifier success; videos in `assets/lunar_base/review/mission_b/`.
- [x] C6 wrap-up (F47–F48): settle re-check PASS; Nav2 drives LunarBot on the lunar
      base through `openral deploy sim`; route-block variant detoured; `panel_remount_v2`
      retired. Open (tuning): ~0.8 m along-track Nav2 overshoot.
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

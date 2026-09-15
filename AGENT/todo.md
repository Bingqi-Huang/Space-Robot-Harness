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

## Phase C: Long-horizon mission construction (execution_plan §6.4) — IN PROGRESS

Mission A v2 = `panel_remount_v2`. Scope split: **scene** (this session) vs.
**mission logic** (covered/held-out cases, inspection semantics, perturbation
switches — explicit follow-on, not started, per §8.2's "no scenario-specific
decision rules" rule).

- [x] Scene half — `space_robotics_bench` `srb/tasks/mobile_manipulation/
      panel_remount_v2/`, merged into `main` (F39). Real SRB assets only
      (`industrial_pedestal_{25,50,100}cm.usdz`, `solar_panel.usdz` — no
      internet/Isaac-Sim-library asset needed). 2 decoy pedestals at
      separate bearings (multiple distinguishable components); target
      cluster moved to ~3.5 m out (real navigable approach, was ~1.5 m in
      v1); `env_spacing` 32→160 grows the safe flat-terrain radius
      ~2.1m→~4.85m via `env_cfg.py`'s own existing formula (not a new
      mechanism) so every object sits inside it with real margin.
      Reward/termination unchanged from v1 (mission logic is follow-on).
      **Live-verified, not just offline-computed**: `srb agent rand -e
      panel_remount_v2_visual`, 6+ min stable physics, real rendered
      frames inspected (no floating/clipping, sane scale, matches offline
      Blender-derived geometry).
- [ ] Mission logic — design done (2026-09-15), not yet coded. Full spec:
      `docs/panel_remount_v2_mission_logic_plan.md`. User decisions: (1)
      covered-case true/decoy discrimination needs a real inspect step,
      not a geometric shortcut; (2) held-out categories = movable-object
      access block + semantically-inconsistent state (not
      capability-substitution). 8-step ordered checklist in the plan doc,
      starting with fixing mission_verifier's stale v1 target constants.
- [ ] Mission B — explicitly after Mission A's orchestration needs are clear.
- [ ] Simulator-truth exposure for independent verification beyond what
      item 7's verifier already does for v1's single pair.

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

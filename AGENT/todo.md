# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

A0–A4 done. See `docs/research_findings.md` before designing any mechanism.

---

## Phase B: Generic OpenRAL on SRB — in progress

Per execution_plan.md §18 Phase B. Embodiment: **LunarBot** (user directive).

### Slice 1 — LunarBot BODY_TWIST through the real safety chain ✅

`docs/phase_b_lunar_bot_hal.md`. New HAL (`LunarBotSRBHAL` +
`openral_hal_lunar_bot`) bridges candidate_action → C++ safety kernel →
safe_action → SRB's `cmd_vel`. Verified live.

### Slice 2 — `kind: "procedural"` rSkill + F11 resolved ✅ (2026-09-13)

openral branch `feat/lunar-bot-hal` (`f47e966`, pushed, **not yet merged**).
Full record: `docs/phase_b_procedural_kind.md`.

Added a genuine, permanent `RSkillKind` — deterministic/non-learned
actuators, needed anyway for Baseline A (§5.2). `ProceduralBodyTwistRskill`
verified live through the **real** `ExecuteRskill` action server (not
`ROSPublishingHAL` called directly): `ros2 action send_goal` → resolver →
skill → candidate_action → kernel → safe_action → HAL → SRB → robot moved.

**New finding while proving this (F15, not a defect in the new kind):** the
3s dispatch aborted at ~2.7s on a safety-status staleness watchdog —
`rskill_runner_node` hardcodes a 3.0s liveness check on
`/openral/safety_status`, but the C++ kernel only publishes it on activation
and on state *changes*, never on a heartbeat. Would hit any rSkill kind's
dispatch lasting >3s without a kernel-side state change, not specific to
`procedural`. Not chased down yet.

**What remains open:**

- [ ] **F15** — diagnose the safety-status staleness watchdog before trusting
      any dispatch longer than a few seconds not to self-abort. Worth doing
      before Mission A, since an unexplained mid-mission e-stop would confound
      every trace collected.
- [ ] **F12** — characterize whether the kernel actually enforces
      `max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` (deliberately
      exceed it, confirm rejection or its absence).
- [ ] Arm (CARTESIAN_TWIST) / gripper (GRIPPER_BINARY) wiring on the HAL —
      same pattern as BODY_TWIST, deferred until the above are settled.

### Then, per plan §21 items 5–6 (not started)

- [ ] Define Mission A as a plain instruction (no space constraints).
- [ ] Run generic OpenRAL against it; save traces; document real failure
      modes — this is what should motivate `space_runtime`'s first schemas,
      not intuition.

---

## Rules

- Branch or worktree per task; delete after **merge** (AGENT.md §1) —
  `feat/lunar-bot-hal` stays open; Phase B is still landing on it.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3).
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code until Phase B observes real
  failures calling for it** (plan §21.6–7).
- `space_robotics_bench/` stays untouched — another agent owns it. On this
  shared host, kill only exact PIDs you launched yourself, never a pattern
  (`docs/research_findings.md` F10).
- `ros2 lifecycle`/`node list` don't work on this host — use direct
  `lifecycle_msgs/srv/ChangeState`/`GetState` service calls (F14).
- Any shell running `ros2 action send_goal`/`topic echo` on an
  `openral_msgs`-typed interface needs **both**
  `/opt/ros/humble/setup.bash` **and** `install/setup.bash` sourced, every
  time — a fresh Bash call starts with neither.

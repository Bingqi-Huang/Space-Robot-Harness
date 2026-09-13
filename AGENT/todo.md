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

**F15 — investigated 2026-09-13, RESOLVED as a false alarm.** The 3s
dispatch aborted at ~2.7s on a safety-status staleness watchdog. First read
concluded the kernel never heartbeats `/openral/safety_status` — wrong. It
does, at a clean 1.000 Hz (`publish_diagnostics`'s wall timer ends with an
unconditional `publish_safety_status_now()`, verified live with
`ros2 topic hz`). The earlier "zero messages" reading was a shell-piping
artifact (`timeout ... | tail` loses output when SIGTERM lands mid-print).
The one abort was very likely a single missed/delayed heartbeat under a
busier multi-participant DDS graph — the mechanism is deliberately
conservative by design, so an occasional trip under load is it working as
intended, not a bug. **Do not spend more effort on this** — treat an
occasional safety-stale abort as expected, and note it's exactly the class
of event execution_plan.md §5.4.4/§13.6 already want to study, not a
nuisance. Full record: `docs/research_findings.md` F15.

**F12 — investigated 2026-09-13, CONFIRMED as a real upstream gap (needs a
user decision, not a silent patch).** `max_base_linear_speed_m_s`/
`max_base_angular_speed_rad_s` (and the equivalent bounds for
`kJointTrajectory`/`kCartesianDelta`/`kGripperBinary`/`kGripperPosition`/
`kCompositeMode`) are enforced by **nothing** today. Root-caused in the C++
source: the kernel's `validate()` explicitly delegates these bounds to the
Python `openral_safety/supervisor_node.py` — whose own docstring says it's a
Day-1 stub waiting for the C++ kernel to implement them. Each side names the
other as responsible; neither does it. Also confirmed
`kernel_params_from_envelope()` doesn't even forward
`max_base_linear_speed_m_s` into the kernel's ROS parameters — there's
nowhere for it to land. **Verified live**: commanded `lunar_bot` at 6.0 m/s
(20× the declared 0.3 m/s bound) for 3s through the real safety-checked
path — zero rejection, no warning, robot moved the full distance. This is
upstream OpenRAL's actual current behavior for every robot using these
control modes, not a mistake in our config. Per CLAUDE.md §3 (touching the
safety kernel/supervisor needs a safety-WG reviewer + hazard-log entry),
**we should not silently patch this** — it's the user's call whether to (a)
report it as a known upstream limitation and scope trustworthiness claims
around it, or (b) treat implementing the missing check as real, reviewable
future work. Full record: `docs/research_findings.md` F12.

**What remains open:**

- [ ] Arm (CARTESIAN_TWIST) / gripper (GRIPPER_BINARY) wiring on the HAL —
      same pattern as BODY_TWIST.

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

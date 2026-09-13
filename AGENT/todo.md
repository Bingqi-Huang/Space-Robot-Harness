# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

A0–A4 all done. OpenRAL fork on Python 3.10/Humble, execution paths of both
OpenRAL and SRB mapped, both alive together and cross-readable. See
`docs/research_findings.md` F1–F10 before designing any mechanism — several
things plan §4 asks for already exist upstream in partial form.

---

## Phase B: Generic OpenRAL on SRB — in progress

Per execution_plan.md §18 Phase B. Embodiment: **LunarBot** (user directive).

### Slice 1 — LunarBot BODY_TWIST through the real safety chain ✅ (2026-09-13)

openral branch `feat/lunar-bot-hal` (`af61568`, pushed, **not yet merged** —
Phase B continues on it). Full record: `docs/phase_b_lunar_bot_hal.md`.

Built (all new, nothing upstream modified): `robots/lunar_bot/robot.yaml`
(real joint/actuator data sourced from SRB's asset definition, cited
in-file — not invented); `LunarBotSRBHAL` (mirrors `RosControlHAL`'s
transport-attach shape); `packages/openral_hal_lunar_bot/` (subclasses
`ManifestHALLifecycleNode`, overrides only `on_configure_post_hal`).

**Verified live against a running SRB instance**: a scripted BODY_TWIST
published via the existing `ROSPublishingHAL` (the same wire path a real
rSkill uses) went through `candidate_action` → C++ safety kernel →
`safe_action` → the new HAL → SRB's `cmd_vel`, and the robot moved a
measured distance with zero rejections. This is the actual mechanism the
user asked for (full safety chain, not a bypass).

**What remains open, not silently skipped** (see `docs/research_findings.md`
F11–F14 for the reasoning behind each):

- [ ] Decide how a scripted (non-learned) test rSkill gets registered so this
      path can be driven by `rskill_runner_node` and the reasoner, not just
      `ROSPublishingHAL` directly. No existing `RSkillKind` cleanly fits —
      this needs its own decision (F11).
- [ ] Characterize whether the C++ kernel actually enforces
      `max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` (deliberately
      exceed it and confirm rejection) before relying on that bound for
      anything (F12).
- [ ] Arm (CARTESIAN_TWIST, SRB's `differential_inverse_kinematics`) and
      gripper (GRIPPER_BINARY, SRB's `binary_joint_position`) — deferred
      until slice 1 was proven; same HAL, same pattern.

### Then, per plan §21 items 5–6 (not started)

- [ ] Define Mission A as a plain instruction (no space constraints).
- [ ] Run generic OpenRAL against it once the rSkill-registration question
      above is settled; save traces; document real failure modes — this is
      what should motivate `space_runtime`'s first schemas, not intuition.

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

# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

Scope was `execution_plan.md` §18 Phase A + §5.1/§5.2 + §6.1 + §21.1–21.3.
Exit condition met: the actual upstream execution path of both OpenRAL and
SRB runs on this machine, and the real APIs/topics of the pinned revisions
are written down.

| Task | State | Record |
|---|---|---|
| A0 — research repo skeleton | ✅ | commit `baa2799` |
| A1 — OpenRAL fork → Python 3.10/Humble | ✅ | openral `4c1867c` (pushed); `docs/upstream_pins.md`, `docs/openral_py310_patch.md` |
| A2 — map OpenRAL execution path | ✅ | `docs/openral_integration_notes.md` |
| A3 — map SRB execution path (LunarBot) | ✅ | `docs/srb_integration_notes.md` |
| A4 — OpenRAL + SRB alive together, cross-read | ✅ | OpenRAL's own 3.10 venv/rclpy read live `/srb/env0/robot/joint_states` + `/tf` off the shared DDS bus |
| Findings seeded | ✅ | `docs/research_findings.md` (F1–F10) |

Embodiment for Phase B: **LunarBot** (user directive). Already integrated
into SRB; teleop/self-collision continue as separate, non-blocking work by
another agent.

**Read `docs/research_findings.md` before designing any Phase B mechanism** —
several things plan §4 asks for already exist upstream in some form (F1, F2,
F7) and should be extended, not rebuilt from scratch.

---

## Phase B: Generic OpenRAL on SRB — not started

Per execution_plan.md §18 Phase B: connect OpenRAL to the SRB
`_ground_manipulation`/`lunar_bot` environment, execute simple capability
calls through the full reasoner/rSkill/safety/ROS path, collect traces.
Exit condition: a minimal multi-step robot mission executed and observed
end-to-end using upstream mechanisms alone — no `space_runtime`/`space_context`
code yet (plan §21.5–7: mechanisms follow observed failures).

Not yet planned in detail. First concrete steps once started:

- [ ] Inventory which rSkill(s) can actually drive `lunar_bot` through the
      F7 topics (`cmd_vel`/`differential_inverse_kinematics`/
      `binary_joint_position`/`four_wheel_steer`) — likely a `kind: ros_action`
      or `ros_service` wrapper per `openral_integration_notes.md` §1.3, not a
      new rSkill from scratch.
- [ ] Define Mission A (plain instruction, no space constraints yet) per
      plan §21.5.
- [ ] Run unmodified/generic OpenRAL against it; save traces; document actual
      failure modes — this is what should motivate `space_runtime`'s first
      schemas, not intuition.

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1).
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3).
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code until Phase B observes real
  failures calling for it** (plan §21.6–7).
- Upstream OpenRAL modifications confined to `docs/openral_py310_patch.md`.
- `space_robotics_bench/` stays untouched — another agent owns it. On this
  shared host, kill only exact PIDs you launched yourself, never a pattern
  (see `docs/research_findings.md` F10).

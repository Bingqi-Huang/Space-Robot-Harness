# TODO — Phase A: Upstream Verification

Scope: `execution_plan.md` §18 Phase A + §5.1/§5.2 + §6.1 + §21.1–21.3.
Exit condition: the actual upstream execution path of OpenRAL and SRB runs on
this machine, and the real APIs/topics of the pinned revisions are written down.
No performance threshold required.

**Do not start Phase B (OpenRAL↔SRB control loop) until A4 passes.**

## Decision D1 — Humble + Python 3.10, fully native ✅ verified

Every machine and every real-robot repo in this lab is Ubuntu 22.04 + Humble.
Rather than split the reasoner (3.12) from the ROS nodes (3.10) across
processes — which would mean rewriting `reasoner_node.py`, 5115 lines, against
plan §0.2/§0.3 — the fork is downgraded to 3.10. Evidence:
`docs/upstream_pins.md`. Every source deviation: `docs/openral_py310_patch.md`.

---

## A0 — Research repo skeleton ✅ (commit `baa2799`)

`git init`; §2 skeleton; `openral/` submodule; `space_robotics_bench/`
deliberately untracked (another agent owns it — **do not touch, do not
commit, do not branch**).

## A1 — OpenRAL fork → Python 3.10 on Humble ✅ (openral `4c1867c`, pushed)

Branch `feat/py310-humble`, two commits pushed to the fork, submodule pinned.

- `uv lock`/`uv sync` resolve at 3.10; rclpy loads from the 3.10 venv and
  creates a live node; 9 ROS packages build (incl. the C++ safety kernel,
  which runs and registers as `/openral_safety_kernel`); `openral doctor`
  reports Python 3.10.12 and ROS 2 distro humble as ok.
- Two host-environment traps found and documented with fixes: Humble's
  `rosidl` needs `PYTHON_EXECUTABLE` (not just `Python3_EXECUTABLE`); active
  miniconda `base` shadows system libcurl and breaks the kernel's link — strip
  `CONDA_*`/miniconda from `PATH` when building C++ packages.
- **Test suite: 5236 passed, 4 failed, 120 skipped, 2 errors** (from 0 useful
  signal on the first run). Fixed: `datetime.UTC`/`tomllib` (3.11+, 2
  genuine production-code gaps + several test files), 7 lerobot-import test
  files missing the `importorskip` guard, 2 doctest targets that can't import
  without lerobot, `docs/methods/` line-marker refresh. The 4 remaining
  failures are verified pre-existing/orthogonal to the Python-version target
  (see `docs/openral_py310_patch.md` §6) — not fixed, by design.

## A2 — Map the pinned OpenRAL revision ✅ (`docs/openral_integration_notes.md`)

Traced `ReasonerCore.tick` → `ReasonerToolCall` (13-variant union) →
`_dispatch` → `_dispatch_execute_rskill` (which already refuses collective
targets, busy-goal double-dispatch, and VLA/VRAM-unfit pairs — pre-existing
mission-invalidity gates, relevant to plan §5.4.5) → `/openral/execute_rskill`
→ rSkill step loop → `/openral/candidate_action` → safety → `/openral/safe_action`
→ HAL. Mapped `MissionState`/`evaluate_task_verdict` (reward-gated
verification, already substantial — not to be rebuilt), the existing
crash-resume ladder-state persistence (file-based, single-process, no space
context — what `space_runtime` extends), `WorldState`'s one resource field
(`battery_pct` — confirming space-context is genuinely absent, nothing to
duplicate), the `ReasonerModel`/`REASONER_MODELS` distributed-endpoint
registry, and the OTel span surface.

**Shipped vs planned, verified in code:**
- Safety: **C++ kernel is shipped** (force/workspace/controller/collision,
  fail-closed on stale/unknown state) and more capable than the Python
  passthrough (n_dof + joint-limit only, explicitly a "Day-1... stub").
  Build against the C++ kernel.
- Replanning ladder: retry-cap, attempts-cap→abandon, and subdivide-depth→
  handoff are code-enforced; "param-tweak"/"substitute-skill" are prompt-only
  LLM guidance, not separate coded rungs.
- WAM: Protocol + `NullWorldModel` stub only — no concrete adapter exists.
  Planned, not shipped.
- `ReloadGstPipelineTool`: dispatch is a log-and-acknowledge stub (GH-126).

**Insertion point decided (plan §3.2): tool-dispatch wrapper (option 2).**
`_dispatch` is a plain method call with no ROS indirection and no existing
hook; a subclass of `ReasonerNode` overriding only `_dispatch_execute_rskill`
(and optionally `_dispatch_lifecycle_transition`) inserts mission-level
admissibility with **zero upstream source modification** — `reasoner_node.main()`
is trivially reimplemented to spin our subclass instead. Caveat: this is a
private method surface, not a public contract; re-verify after every rebase.

## A3 — Map the pinned SRB revision  (§6.1, §21.3) — not started

Produce `docs/srb_integration_notes.md`. **Read-only — another agent is
working in that repo. Do not edit, commit, or branch anything under it.**

- [ ] `srb ls`; run one existing manipulation task headless; run
      `_ground_manipulation` with a supported mobile manipulator.
- [ ] Launch the ROS interface passive and active; record **actual**
      topic/service/action names, types, QoS.
- [ ] Confirm RGB/depth + robot state + tf publish, and that a control command
      moves the robot.
- [ ] Note the first-run shader-compile cost (minutes, `enable_cameras=True`).
- [ ] Decide the Phase-B embodiment; least integration work wins (§6.2).
      LunarBot is not a prerequisite.

## A4 — Phase A exit demonstration — not started

- [ ] SRB `_ground_manipulation` running with its ROS interface live, while
      the OpenRAL graph is up.
- [ ] One SRB topic readable from the OpenRAL side. Isaac bundles its own
      cpython-311 rclpy for both distros, so keep SRB on `distro="humble"`.
      Clear stale `/dev/shm/fastrtps_*` first.
- [ ] `docs/srb_integration_notes.md` committed.
- [ ] Seed `docs/research_findings.md` (§21.10).

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1).
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3).
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code in Phase A** — only read, run,
  document. Mechanisms follow observed failures (§21.6–7).
- Upstream modifications are confined to what `docs/openral_py310_patch.md`
  records. `space_robotics_bench/` stays untouched.

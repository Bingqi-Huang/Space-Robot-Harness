# TODO — Phase A: Upstream Verification

Scope: `execution_plan.md` §18 Phase A + §5.1/§5.2 + §6.1 + §21.1–21.3.
Exit condition: the actual upstream execution path of OpenRAL and SRB runs on
this machine, and the real APIs/topics of the pinned revisions are written down.
No performance threshold required.

**Do not start Phase B (OpenRAL↔SRB control loop) until A4 passes.**

## Decision D1 — Humble + Python 3.10, fully native ✅ verified

Every machine and every real-robot repo in this lab is Ubuntu 22.04 + Humble.
`rclpy` is a compiled C extension bound to one Python per distro (Humble→3.10,
Jazzy→3.12), and upstream OpenRAL is written for Jazzy. Rather than split the
reasoner from the ROS nodes across processes — which would mean rewriting
`reasoner_node.py`, 5115 lines, against plan §0.2/§0.3 — the fork is downgraded
to 3.10. Evidence and dependency floors: `docs/upstream_pins.md`.
Every deviation: `docs/openral_py310_patch.md`.

---

## A0 — Research repo skeleton ✅ (commit `baa2799`)

`git init` at the project root; §2 directory skeleton; `openral/` as a submodule
pinned at `4700c7a`; `space_robotics_bench/` deliberately untracked (another
agent owns it — do not touch, do not commit, do not branch).

## A1 — OpenRAL fork → Python 3.10 on Humble ✅ (openral `fa7f445`)

Branch `feat/py310-humble`. `uv lock` resolves at `==3.10.*` (236 packages);
`uv sync --all-packages` installs; **rclpy loads from the 3.10 venv and creates a
live node**; 9 ROS packages build; `openral doctor` reports Python 3.10.12 and
ROS 2 distro humble as ok; the C++ safety kernel runs and registers as
`/openral_safety_kernel`.

Two host-environment traps found, both documented with fixes:
- Humble's `rosidl` reads the legacy `PYTHON_EXECUTABLE`, not
  `Python3_EXECUTABLE` — pass both or CMake picks its own interpreter.
- miniconda `base` is active in every login shell and shadows system libcurl
  (its `libcurl.so.4.8.0` carries zero `CURL_OPENSSL_4` symbols); strip
  `CONDA_*` and miniconda from `PATH` when building C++ packages.

### A1 remainder (needs sudo — ask the user to run with `!`)

- [ ] `sudo apt-get install -y ros-humble-foxglove-bridge ros-humble-octomap-server ros-humble-nav2-bringup ros-humble-nav2-msgs ros-humble-slam-toolbox`
      — runtime `exec_depend`s of `openral_rskill_ros`, plus Nav2/SLAM which
      navigation will need (§8.1 capability inventory).
- [ ] `sudo apt-get install -y just` — every upstream doc drives through it.
- [ ] Run OpenRAL's own test suite once on 3.10; record pass/fail.
- [ ] Push `feat/py310-humble` to the fork and bump the submodule pointer.

## A2 — Map the pinned OpenRAL revision  (§5.1, §5.2, §21.2)

Read the checked-out code, not the docs prose. Produce
`docs/openral_integration_notes.md` with exact source paths + signatures for:

- [ ] `ReasonerCore.tick` → `ReasonerToolCall` → ROS dispatch in `reasoner_node.py`.
- [ ] `ExecuteRskillTool` → `/openral/execute_rskill` → skill runner → safety path.
- [ ] `MissionState` + `DecomposeMissionTool`; where the task ledger is mutated
      (`python/reasoner/mission.py`).
- [ ] `WorldStateAggregator` snapshot/staleness API (`python/world_state/`).
- [ ] Read-only query tools: `QueryScene` / `LocateInView` / `QueryTaskProgress` srv.
- [ ] Reasoner provider/model interface. `openral doctor` reports
      `OPENRAL_REASONER_MODEL` unset; curated ids are `claude-opus-4-8`,
      `cosmos3-edge`, `gpt-5.5`, `gpt-5.6`. Needed later for §4.5.
- [ ] OTel spans emitted per reasoner tick (`python/observability/`).
- [ ] **Shipped vs planned audit**: safety kernel, collision/freshness checks,
      replanning ladder, WAM. Verify in code; mark shipped/partial/planned.
- [ ] Pick the least invasive insertion point of §3.2's three, with evidence.
      Do not implement.

## A3 — Map the pinned SRB revision  (§6.1, §21.3)

Produce `docs/srb_integration_notes.md`. **Read-only — another agent is working
in that repo. Do not edit, commit, or branch anything under it.**

- [ ] `srb ls`; run one existing manipulation task headless; run
      `_ground_manipulation` with a supported mobile manipulator.
- [ ] Launch the ROS interface passive and active; record **actual**
      topic/service/action names, types, QoS.
- [ ] Confirm RGB/depth + robot state + tf publish, and that a control command
      moves the robot.
- [ ] Note the first-run shader-compile cost (minutes, `enable_cameras=True`) so
      timeouts are not misdiagnosed.
- [ ] Decide the Phase-B embodiment; least integration work wins (§6.2).
      LunarBot is not a prerequisite.

## A4 — Phase A exit demonstration

- [ ] SRB `_ground_manipulation` running with its ROS interface live, while the
      OpenRAL graph is up.
- [ ] One SRB topic readable from the OpenRAL side. Isaac bundles its own
      cpython-311 rclpy for both distros, so keep SRB on `distro="humble"` to
      match the wire format. Clear stale `/dev/shm/fastrtps_*` first.
- [ ] `docs/` notes committed.
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

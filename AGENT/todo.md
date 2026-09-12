# TODO — Phase A: Upstream Verification

Scope: `execution_plan.md` §18 Phase A + §5.1/§5.2 + §6.1 + §21.1–21.3.
Exit condition: the actual upstream execution path of OpenRAL and SRB runs on
this machine, and the real APIs/topics of the pinned revisions are written down.
No performance threshold required.

**Do not start Phase B (OpenRAL↔SRB control loop) until A4 passes.**

---

## Current state (verified 2026-09-12)

| Item | State |
|---|---|
| SRB fork | `DsslRobot/space_robotics_bench` @ `7528ff8` (v0.0.6). Native install on Isaac Sim 5.1 verified working. |
| SRB local WIP | **uncommitted**: LunarBot asset + `wheeled_manipulator` + `_ground_manipulation` env/visual_ext edits. Commit before pinning. |
| OpenRAL fork | `DsslRobot/openral` @ `4700c7a`. **Not installed yet.** |
| Research repo | does not exist yet |
| Host | Ubuntu 22.04 + ROS 2 Humble (apt, 395 pkgs), python3.10. No python3.12. |

## Decision D1 — target Python/ROS: **Humble + Python 3.10, fully native**

Rationale (all machines and all real-robot repos are 22.04/Humble; §16 LunarBot
transfer must reuse the real stack unchanged):

- `rclpy` is a compiled C extension bound to one Python per distro. Humble ships
  `_rclpy_pybind11.cpython-310-*.so` → 3.10 only. Jazzy → 3.12.
- OpenRAL pins `requires-python = ">=3.12,<3.13"` and `just ros2-build` forces
  `-DPython3_EXECUTABLE=.venv/bin/python`, i.e. it is written for Jazzy.
- Its Humble branch exists (`bootstrap_ubuntu.sh:18`, `22.04) ROS_DISTRO="humble"`)
  but `test-ros2.yml` runs Jazzy only — **the Humble path is unverified upstream.**
- Splitting brain (3.12) from ROS (3.10) across processes would mean rewriting
  `reasoner_node.py` (5115 lines) — violates plan §0.2/§0.3 "reuse before implementing".
- ⇒ downgrade our OpenRAL fork to 3.10 instead. Source risk measured as ~zero:
  no PEP 695 / `typing.override` / `Self` / `tomllib` / `except*` / `TaskGroup`;
  only 2 `StrEnum` uses, both in `openral_hal` (unused in sim).

Facts behind this (verified against PyPI, not assumed):
`torch 2.14 >=3.10`, `transformers 5.17 >=3.10`, `accelerate >=3.10`,
`bitsandbytes >=3.10`, `pydantic >=3.9` — all fine.
**`lerobot` is >=3.12 in every version (0.5.1/0.6.0/0.6.1)** — the one hard blocker.
`numpy` must stay ≤2.2.x (2.3+ needs 3.11).

Consequence for VLA: in-process lerobot adapters (`smolvla`/`pi05`/`xvla`/`act`/
`diffusion`) are unavailable on 3.10 — **but they are equally unavailable on the
real LunarBot (Humble/3.10)**, so any VLA must be an out-of-process sidecar
anyway. OpenRAL already ships that pattern (`sidecar-wire` group = pyzmq+msgpack;
`tools/rldx_sidecar.py` runs in its own venv). Sim and real then match exactly.
Per §8.1, no VLA is selected unless it earns its place.

Also established: SRB never uses the host ROS. Isaac Sim 5.1 bundles **both**
`humble/` and `jazzy/` rclpy, each rebuilt for **cpython-311**. So SRB is
distro-selectable via one argument and permanently on Python 3.11 — irrelevant,
since SRB and OpenRAL are separate processes meeting only on the DDS bus.
Keep SRB on `distro="humble"` to match.

---

## A0 — Research repo skeleton  (§2, §21.1)

- [ ] Commit SRB LunarBot WIP on branch `feat/lunarbot-asset` in the SRB fork; push to `origin`.
- [ ] `git init` at `/mnt/SharedData/Research/Space_Robot_Harness` as `space_robotics_agent_harness`.
- [ ] Add `openral/` and `space_robotics_bench/` as **submodules** pinned to the fork commits; keep `AGENT/` tracked.
- [ ] Create the §2 skeleton: `configs/ missions/ space_runtime/ space_context/ openral_ext/ srb_ext/ network/ experiments/ evaluation/ scripts/ docs/ artifacts/` + `README.md` + `pyproject.toml`.
- [ ] `.gitignore`: `artifacts/`, Isaac logs, rosbags, `__pycache__`.
- [ ] `docs/upstream_pins.md` with both commits + D1.

## A1 — Execute D1: OpenRAL fork → Python 3.10 on Humble  (blocks A2/A4)

Branch `feat/py310-humble` in the openral fork. Stop and re-evaluate if step 2 fails.

- [ ] 1. Change `requires-python` to `>=3.10,<3.11` in root `pyproject.toml` + all `python/*/pyproject.toml`.
- [ ] 2. **Decisive test:** `uv lock` with `dataset` and `hal` excluded from the workspace sync set. If the tree resolves, D1 is confirmed; if not, record exactly which package blocks and re-open the decision.
- [ ] 3. Drop `lerobot` from `python/dataset` and `python/hal` (neither is used: no imitation-learning datasets, no real-robot HAL in sim), or exclude both from the sync set.
- [ ] 4. `StrEnum` → `class X(str, Enum)` in `openral_hal/protocol.py`, `openral_hal/ros_control.py`.
- [ ] 5. `source /opt/ros/humble/setup.bash` → `just ros2-build`, narrowed to the packages we need (`openral_msgs`, `openral_reasoner_ros`, `openral_rskill_ros`, `openral_world_state`, `openral_safety`, `openral_safety_kernel`, `openral_perception_ros`) — **not** all 28; the 13 HAL packages are for robots we don't have.
- [ ] 6. `uv run openral doctor` → capture verbatim.
- [ ] 7. Record every deviation from upstream in `docs/openral_py310_patch.md` so rebases are mechanical.

## A2 — Map the pinned OpenRAL revision  (§5.1, §5.2, §21.2)

Read the checked-out code, not the docs prose. Produce `docs/openral_integration_notes.md`
with exact source paths + signatures for:

- [ ] `ReasonerCore.tick` → `ReasonerToolCall` → ROS dispatch in `reasoner_node.py`.
- [ ] `ExecuteRskillTool` → `/openral/execute_rskill` → skill runner → safety path.
- [ ] `MissionState` + `DecomposeMissionTool`; where the task ledger is mutated (`python/reasoner/mission.py`).
- [ ] `WorldStateAggregator` snapshot/staleness API (`python/world_state/`).
- [ ] Read-only query tools: `QueryScene` / `LocateInView` / `QueryTaskProgress` srv.
- [ ] Reasoner provider/model interface (needed later for §4.5 distributed reasoning).
- [ ] OTel spans emitted per reasoner tick (`python/observability/`).
- [ ] **Shipped vs planned audit**: C++ safety kernel, collision/freshness checks, replanning ladder, WAM. Verify in code; mark shipped/partial/planned.
- [ ] Pick the least invasive insertion point of §3.2's three, with evidence. Do not implement.
- [ ] Run OpenRAL's test suite once on 3.10; record pass/fail.

## A3 — Map the pinned SRB revision  (§6.1, §21.3)

Produce `docs/srb_integration_notes.md`:

- [ ] `srb ls`; confirm env registration survives the LunarBot edits.
- [ ] Re-verify one existing manipulation task headless post-pin.
- [ ] Run `_ground_manipulation` with a supported mobile manipulator; record command + config.
- [ ] Launch the ROS interface passive and active; record **actual** topic/service/action names, types, QoS.
- [ ] Confirm RGB/depth + robot state + tf publish, and that a control command moves the robot.
- [ ] Note the first-run shader-compile cost (minutes, `enable_cameras=True`) so timeouts are not misdiagnosed.
- [ ] Decide the Phase-B embodiment: LunarBot WIP vs a stock SRB mobile manipulator. Least integration work wins (§6.2) — LunarBot is not a prerequisite.

## A4 — Phase A exit demonstration

- [ ] OpenRAL runtime starts on Humble/3.10 and passes `openral doctor`.
- [ ] SRB `_ground_manipulation` runs with its ROS interface live.
- [ ] Both alive at once; one SRB topic readable from the OpenRAL side. Check
      Isaac's bundled-rclpy DDS meets host Humble on the same bus (clear stale
      `/dev/shm/fastrtps_*` first — upstream hit this).
- [ ] `docs/` notes above committed.
- [ ] Seed `docs/research_findings.md` (§21.10).

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1).
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3).
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code in Phase A** — only read, run, document.
  Mechanisms come after observed failures (§21.6–7).
- A1 is the only permitted upstream modification, and only as recorded in
  `docs/openral_py310_patch.md`.

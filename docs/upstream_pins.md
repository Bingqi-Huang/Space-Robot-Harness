# Upstream pins and the Python/ROS target

Recorded 2026-09-12. Execution plan §2 requires upstream to be version-pinned
and every experimental campaign to name the exact commits it ran against.

## Pinned revisions

| Project | Fork | Branch | Commit | Upstream | Tracking |
|---|---|---|---|---|---|
| OpenRAL | `DsslRobot/openral` | `master` | `ec95fe8` | `OpenRAL/openral` @ `4700c7a` | git submodule at `openral/` |
| Space Robotics Bench | `DsslRobot/space_robotics_bench` | `main` | `6d8a388` | `AndrejOrsula/space_robotics_bench` | git submodule at `space_robotics_bench/` |

OpenRAL's pin has moved to `ec95fe8` (2026-09-14): the Phase B2
`feat/lunar-bot-capability-set` stack (execution_plan.md §8.3 items 1-6 —
RM-75 limits, sensor bridge, the SRB deploy-sim backend, five procedural
rSkills, the F19 steer-before-drive fix, the Nav2 `/cmd_vel` kernel relay,
and MoveIt for the RM-75) merged into `master` via `--no-ff`, superseding
the eight intermediate pins recorded previously
(`fa7f445`/`4c1867c`/`af61568`/`f47e966`/`fabe588`/`1a6139f`/`af8fba2`/
`a785b88`/`f7b5ccd` — all now reachable from `master` through this merge).
Local branches for the whole stack were deleted after merging, per this
project's own convention; nothing was pushed to `origin` — that pin move
is local until pushed. Full rationale: `docs/research_findings.md`
F22/F25-F33.

Space Robotics Bench's pin moved to `6d8a388` (2026-09-14) the same way:
the `feat/four-wheel-steer-alignment` stack (`panel_remount` task,
`SwitchableArmAction`, the Mid-360 RayCaster lidar, the idle-CPU/rosidl
perf fixes, the `map_cmd_to_action` angular.z bug, and the F19
steer-before-drive fix) merged into `main`, superseding the two
intermediate pins recorded previously (`b3e8d92`/`90f9d5e` — both now
reachable from `main`). Local branches deleted after merging; not pushed.
Every experimental run manifest (§19) should still record the exact
commit it ran against — the submodule pin makes that commit
reconstructible from this repo alone, it doesn't replace per-run
provenance.

## Decision D1 — Humble + Python 3.10, fully native

Every machine and every real-robot (LunarBot) repository in this lab is
Ubuntu 22.04 + ROS 2 Humble. That is a hard constraint, not a preference.

`rclpy` is a compiled C extension bound to one Python per distro:

```
/opt/ros/humble/local/lib/python3.10/dist-packages/rclpy/
    _rclpy_pybind11.cpython-310-x86_64-linux-gnu.so
```

Humble is 3.10-only; Jazzy is 3.12. OpenRAL pins `requires-python = ">=3.12,<3.13"`
across all 13 `python/*` packages, and `just ros2-build` forces
`-DPython3_EXECUTABLE=.venv/bin/python` — it is written for Jazzy. A Humble
branch exists (`bootstrap_ubuntu.sh:18`) but `.github/workflows/test-ros2.yml`
runs Jazzy only, so the Humble path is unverified upstream. (`tests/README.md`
claims humble+jazzy; that is stale.)

**Resolution: downgrade the fork to 3.10 and stay native on Humble.**

Splitting a 3.12 reasoner from 3.10 ROS nodes across processes was rejected:
`openral_core`, `openral_reasoner` and `openral_world_state` are genuinely
rclpy-free, but `packages/openral_reasoner_ros/reasoner_node.py` is 5115 lines
of ROS integration. Bridging around it means rewriting it, against plan
§0.2/§0.3 ("reuse before implementing", "do not duplicate OpenRAL features").

Source-level risk measured, not assumed: no PEP 695 generics, `typing.override`,
`typing.Self`, `tomllib`, `except*` or `asyncio.TaskGroup` anywhere in `python/`.
Only two `StrEnum` uses, both in `openral_hal` — unused in simulation.

### Dependency floors (verified against PyPI)

| Package | requires-python | On 3.10 |
|---|---|---|
| torch 2.14 | `>=3.10` | ok |
| transformers 5.17 | `>=3.10.0` | ok |
| accelerate 1.15 | `>=3.10.0` | ok |
| bitsandbytes 0.50 | `>=3.10` | ok |
| pydantic 2.13 | `>=3.9` | ok |
| numpy | `>=3.10` at 2.2.x, `>=3.11` from 2.3 | pin ≤2.2.x |
| **lerobot (all versions)** | **`>=3.12`** | **blocker** |

torch is not a problem — it drops old Pythons over time (3.9 went in 2.8) but
3.10 remains its floor. `lerobot` is the only hard blocker. It is not a base
dependency; it enters through `python/dataset` (rosbag2 ↔ LeRobotDataset),
`python/hal` (`lerobot[feetech]`), and the opt-in sim/VLA groups. This project
needs none of them.

### Consequence for learned policies

In-process lerobot adapters (`smolvla`, `pi05`, `xvla`, `act`, `diffusion`) are
unavailable on 3.10 — but equally impossible on the real LunarBot, which is also
Humble/3.10. Any VLA must therefore be an out-of-process sidecar regardless of
what we choose here, and OpenRAL already ships that pattern: the `sidecar-wire`
dependency group (pyzmq + msgpack, "the model/simulator side runs in its own
venv") and `tools/rldx_sidecar.py`, which runs in its own separate venv.
Choosing 3.10 makes simulation and hardware identical rather than growing a
simulation-only habit. Per plan §8.1, no VLA is adopted unless it earns its place.

## Space Robotics Bench is orthogonal

Isaac Sim 5.1 bundles **both** ROS distros' client libraries, each rebuilt by
NVIDIA against Isaac's own interpreter:

```
exts/isaacsim.ros2.bridge/humble/rclpy/rclpy/_rclpy_pybind11.cpython-311-*.so
exts/isaacsim.ros2.bridge/jazzy/rclpy/rclpy/_rclpy_pybind11.cpython-311-*.so
```

So SRB never touches `/opt/ros/*`, selects its distro through one argument
(`enable_ros2_bridge(distro=...)` in `srb/utils/ros.py`), and is permanently on
Python 3.11. Keep it on `distro="humble"` to match the OpenRAL side. The two run
as separate processes and meet only on the DDS bus, so their interpreters never
have to agree.

## Timeline

Ubuntu 22.04 standard support ends 2027-04 (ESM to 2032); ROS 2 Humble reaches
EOL 2027-05. Both are well past this study's horizon, so the constraint costs
nothing on the relevant timescale.

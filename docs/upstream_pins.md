# Upstream pins and the Python/ROS target

Recorded 2026-09-12. Execution plan §2 requires upstream to be version-pinned
and every experimental campaign to name the exact commits it ran against.

## Pinned revisions

| Project | Fork | Branch | Commit | Upstream | Tracking |
|---|---|---|---|---|---|
| OpenRAL | `DsslRobot/openral` | `feat/lunar-bot-arm-gripper` | `af8fba2` | `OpenRAL/openral` @ `4700c7a` | git submodule at `openral/` |
| Space Robotics Bench | `DsslRobot/space_robotics_bench` | — | `7528ff8` (v0.0.6) | `AndrejOrsula/space_robotics_bench` | **not a submodule** — externally managed, see below |

OpenRAL's pin has moved six times since the initial `4700c7a`:
`fa7f445`/`4c1867c` (Python 3.10/Humble downgrade,
`docs/openral_py310_patch.md`), `af61568` (the `lunar_bot` HAL,
`docs/phase_b_lunar_bot_hal.md`), `f47e966` (the `procedural` rSkill kind,
`docs/phase_b_procedural_kind.md`), `fabe588` (BODY_TWIST base-speed envelope
enforcement, `docs/f12_body_twist_envelope_fix.md`), `1a6139f` (CARTESIAN_TWIST
angular-speed enforcement, F16), `af8fba2` (arm + gripper unified into the
LunarBot HAL, `docs/phase_b_lunar_bot_arm_gripper.md`) — the current commit is
on branch `feat/lunar-bot-arm-gripper`, built on top of
`fix/body-twist-speed-envelope` → `feat/lunar-bot-hal` → `feat/py310-humble`,
not yet merged (Phase B work continues on it).

Space Robotics Bench is developed independently of this repository and is
excluded via `.gitignore`. Record its commit in each run manifest (§19) rather
than tracking it here.

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

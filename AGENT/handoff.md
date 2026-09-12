# Handoff

State as of 2026-09-12. Phase A (upstream verification).
Task list: `todo.md`. Decision record: `docs/upstream_pins.md`.
Fork patch record: `docs/openral_py310_patch.md`.

## Done

### A0 — research repo ✅ commit `baa2799`

`git init` at `/mnt/SharedData/Research/Space_Robot_Harness`, branch `main`.
Execution-plan §2 skeleton, `README.md`, `pyproject.toml` (py3.10),
`docs/upstream_pins.md`. `openral/` is a submodule pinned at `4700c7a`.

**`space_robotics_bench/` is not tracked** — another agent owns that repo. It is
in `.gitignore`. Do not edit, commit, branch, or record anything under it. Its
revision goes in each run manifest instead.

### A1 — OpenRAL fork → Python 3.10 ✅ openral commit `fa7f445`

Branch `feat/py310-humble` off `4700c7a`, committed, **not yet pushed**.

Verified end to end:

| Check | Result |
|---|---|
| `uv lock` | resolves at `==3.10.*`, 236 packages |
| `uv sync --all-packages` | ok, venv is Python 3.10.12 |
| **rclpy from the 3.10 venv** | **loads Humble's `cpython-310` binary and creates a live node** |
| pure-python imports | `openral_core` / `reasoner` / `world_state` / `hal` ok |
| rclpy chain | `rskill_ros → runner → hal` ok; `reasoner_node` (5115 lines) imports |
| colcon | 9 packages built (msgs, foxglove_bringup, world_state, reasoner_ros, rskill_ros, safety, perception_ros, otel_cpp_vendor, safety_kernel) |
| `openral doctor` | Python 3.10.12 ok · ROS 2 distro **humble** ok · colcon ok · 2× RTX 5090 · cuMotion ok |
| C++ safety kernel | runs, registers as `/openral_safety_kernel` lifecycle node |

Source changes: `requires-python` → `>=3.10,<3.11` (15 files); every `lerobot`
requirement removed (base deps, two extras, nine dependency groups, the
libero↔robocasa conflicts pair); `so100_sim` behind a PEP 562 `__getattr__`;
`StrEnum` → `(str, Enum)`; `typing.Self` → `typing_extensions.Self`.
Only `numpy` moves versus upstream (2.2.6).

## Two host traps — read before any colcon build

1. **Humble's `rosidl` reads `PYTHON_EXECUTABLE`, not `Python3_EXECUTABLE`.**
   Upstream's `just ros2-build` sets only the latter, so CMake picks its own
   interpreter. The failure surfaces as
   `ImportError: cannot import name 'generate_py' from 'rosidl_generator_py'`,
   because `rosidl_generator_py/__init__.py` swallows the real cause in a bare
   `except ImportError`. Pass **both** variables.
2. **miniconda `base` is active in every login shell here.** It shadows system
   libraries. Its `libcurl.so.4.8.0` has zero `CURL_OPENSSL_4` symbols while
   Ubuntu's `4.7.0` has 88, so `openral_safety_kernel` fails to link against
   `libopentelemetry_http_client_curl.so` with a wall of
   `undefined reference to 'curl_*@CURL_OPENSSL_4'`. Strip `CONDA_*` and
   miniconda from `PATH` when building C++ packages — the exact `env -u ...`
   invocation is in `docs/openral_py310_patch.md`. Isaac Sim's `python.sh` warns
   about the same condition.

Both discoveries came from the Humble path being CI-unverified upstream
(`test-ros2.yml` runs Jazzy only; `tests/README.md`'s humble+jazzy claim is
stale).

## Next

1. Two apt installs — needs the user (`!` prefix):
   `ros-humble-foxglove-bridge ros-humble-octomap-server ros-humble-nav2-bringup
   ros-humble-nav2-msgs ros-humble-slam-toolbox`, and `just`.
   The first two are `exec_depend`s of `openral_rskill_ros`; Nav2/SLAM are what
   navigation will need (§8.1). `just` is warned about by `openral doctor`.
2. Run OpenRAL's own test suite once on 3.10; record pass/fail.
3. Push `feat/py310-humble`; bump the submodule pointer in the research repo.
4. A2 — trace the OpenRAL execution path into `docs/openral_integration_notes.md`.
5. A3 — map SRB **read-only**.

## Watch out

- Upstream `CLAUDE.md` says "Python 3.12 only". The deviation is deliberate and
  fully recorded so rebases stay mechanical. Re-run the AST scan for 3.11+
  `typing` names after any rebase — a line-oriented grep misses the multi-line
  `from typing import (...)` form, which is how `Self` was missed the first time.
- `OPENRAL_REASONER_MODEL` is unset; curated ids are `claude-opus-4-8`,
  `cosmos3-edge`, `gpt-5.5`, `gpt-5.6`. Configure in Phase B, not now.
- No `space_runtime` / `space_context` code until Phase A is finished —
  mechanisms follow observed failures (plan §21.6–7).

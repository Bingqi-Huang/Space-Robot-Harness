# OpenRAL fork patch — Python 3.10 / ROS 2 Humble

Branch `feat/py310-humble` in `DsslRobot/openral`, on top of `4700c7a`.
Rationale and evidence: `docs/upstream_pins.md` (decision D1).

Upstream's `CLAUDE.md` §2 states "Python 3.12 only". This fork deviates
deliberately, because the interpreter is not a preference here — ROS 2 Humble's
`rclpy` is a `cpython-310` binary and every machine and real robot in this lab
runs it. Keep every deviation in this file so rebases stay mechanical.

## Changes

### 1. Interpreter pin (15 files)

`requires-python = ">=3.12,<3.13"` → `">=3.10,<3.11"` in the root
`pyproject.toml` and all 14 `python/*/pyproject.toml`.

### 2. Remove every `lerobot` requirement

`lerobot` declares `requires-python >= 3.12` in every published version
(0.5.1 / 0.6.0 / 0.6.1 all checked), so it cannot resolve at 3.10. `uv lock`
resolves **all dependency groups and all extras of all workspace members**, so
each of these blocks the entire solve even when nothing installs it:

| Location | Removed | Why it is safe here |
|---|---|---|
| `python/hal` base deps | `lerobot[feetech]>=0.6.0` | SO-100/SO-101 servo bus only; we have no such arm |
| `python/hal` extras | the whole `so100` extra | same, and it carried only that one line |
| `python/dataset` extras | the whole `lerobot` extra | `LeRobotDatasetSink`; `RolloutRecorder` + `Rosbag2Sink` remain and are what we record with |
| root `[dependency-groups]` | `dataset`, `sim`, `libero`, `metaworld`, `maniskill3`, `simpler-env`, `robocasa`, `gr00t`, `lowering` | alternative simulators, the imitation-learning dataset bridge, and in-process VLA policies. This project runs on Space Robotics Bench |
| root `[tool.uv]` | the `libero` ↔ `robocasa` `conflicts` pair | both groups are gone |

**Untouched and still resolving:** `sidecar-wire`, `rldx`, `behavior-groot`,
`isaacsim`, `robotwin`, `rlbench`, `lingbot`, `locateanything`, `qwen-vlm`.
Every one of them reaches its model out-of-process and carries only
`pyzmq` + `msgpack` on this side of the wire, so the entire out-of-process VLA
path survives at 3.10 — which is also the only path the real robot can use.

### 3. `openral_hal/__init__.py` — lazy SO-100 digital twin

`so100_sim.py` is the only module in the package that imports `lerobot` at
module scope, and `__init__.py` imported it eagerly. That made
`import openral_hal` fail outright, which would take down `openral_runner` and
therefore `openral_rskill_ros` — the `/openral/execute_rskill` action server we
depend on. Replaced with a PEP 562 module `__getattr__` that imports
`so100_sim` on attribute access. `__all__` is unchanged, so the public surface
is identical.

### 4. `enum.StrEnum` → `(str, Enum)`

`StrEnum` is 3.11+. Two occurrences, both in `openral_hal`:
`protocol.py` (`EStopRecovery`), `ros_control.py` (`ControllerKind`).
Behaviourally identical for this use.

### 5. `typing.Self` → `typing_extensions.Self`

One site: `openral_core/schemas.py`. `typing.Self` is 3.11+.
`typing-extensions>=4.10` is now declared explicitly in `python/core` (it was
already present transitively via pydantic).

Found by AST scan, not grep — the import is a multi-line parenthesised
`from typing import (...)`, which a line-oriented pattern misses. Re-run the
scan after any rebase:

```python
import ast, pathlib, typing
for root in ("python", "packages", "tools", "scripts"):
    for p in pathlib.Path(root).rglob("*.py"):
        for n in ast.walk(ast.parse(p.read_text(), filename=str(p))):
            if isinstance(n, ast.ImportFrom) and n.module == "typing":
                for a in n.names:
                    if a.name != "*" and not hasattr(typing, a.name):
                        print(f"{p}:{n.lineno}: {a.name}")
```

Run it with `/usr/bin/python3.10`, so `hasattr(typing, ...)` reflects the target
interpreter. A full-tree `ast.parse` under 3.10 also reports **zero** syntax
errors across `python/` and `packages/`.

### 5. `uv.lock` regenerated

`requires-python = "==3.10.*"`; 236 packages (upstream: 364 — the difference is
the removed simulator/VLA groups).

Resolved versions match upstream where it matters: `torch` 2.9.1 / 2.10.0 /
2.13.0+cu130, `transformers` 5.5.4, `pydantic` 2.13.3, `torchcodec` 0.9.1,
`pyzmq` 27.1.0. Only `numpy` moves — 2.2.6 instead of a 2.3.x, because numpy
raised its floor to 3.11 at 2.3.

## Building the ROS packages on Humble — `PYTHON_EXECUTABLE`

This is a build-invocation difference, not a source patch, but it must be
carried in every colcon command.

`just ros2-build` passes only `-DPython3_EXECUTABLE=$(pwd)/.venv/bin/python`.
That is the modern CMake spelling Jazzy's `rosidl` uses. **Humble's
`rosidl_generator_py` still reads the legacy `PYTHON_EXECUTABLE`**, so on Humble
CMake auto-detects an interpreter instead — here it picked up
`/home/bingqi/miniconda3/bin/python3` (3.13, first on `PATH`). The generator then
fails to import its own backend, and `rosidl_generator_py/__init__.py` swallows
the real cause in a bare `except ImportError`, surfacing only:

```
ImportError: cannot import name 'generate_py' from 'rosidl_generator_py'
```

Pass **both** variables:

```bash
source /opt/ros/humble/setup.bash
colcon build --merge-install --symlink-install \
  --base-paths packages cpp \
  --packages-select openral_msgs openral_foxglove_bringup openral_world_state \
                    openral_reasoner_ros openral_rskill_ros openral_safety \
                    openral_perception_ros opentelemetry_cpp_vendor \
                    openral_safety_kernel \
  --cmake-args -DPython3_EXECUTABLE="$(pwd)/.venv/bin/python" \
               -DPYTHON_EXECUTABLE="$(pwd)/.venv/bin/python" \
               -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++
```

Notes on that package list:

- It is deliberately narrow. Upstream builds 28 packages; 13 of them are
  `openral_hal_*` for robots this lab does not have.
- `openral_foxglove_bringup` is not optional — `openral_rskill_ros` declares it
  as an `exec_depend`, and colcon fails without it.
- `CMAKE_POLICY_VERSION_MINIMUM=3.10` from the upstream recipe is a Jazzy-only
  workaround (its bundled `gtest_vendor`); on Humble it is merely unused noise.
- Pure-Python ament packages warn that `PYTHON_EXECUTABLE` was unused. Harmless
  — only `rosidl` consumes it.
- `octomap_server` and `foxglove_bridge` are `exec_depend`s satisfied by apt
  (`ros-humble-octomap-server`, `ros-humble-foxglove-bridge`); they are needed at
  runtime, not to build.

### Strip conda from the build environment

Not a fork patch — a property of this host, but it breaks the build every time.
This machine activates miniconda `base` in every login shell (`CONDA_PREFIX` set,
`~/miniconda3/bin` and `condabin` on `PATH`). CMake then prefers conda's copies
of things over the system ones, in at least two places:

1. **Python.** `PYTHON_EXECUTABLE` auto-detected as `~/miniconda3/bin/python3`
   (3.13) — the failure described above. Passing the variable explicitly fixes
   this one regardless of conda.
2. **libcurl.** Conda ships `libcurl.so.4.8.0` built *without* symbol
   versioning; Ubuntu's `libcurl.so.4.7.0` carries 88 `CURL_OPENSSL_4` symbols.
   `opentelemetry_cpp_vendor` compiles `libopentelemetry_http_client_curl.so`
   against the system headers, so its references are versioned — and the final
   link of `openral_safety_kernel` then resolves against conda's unversioned
   library and fails with a wall of
   `undefined reference to 'curl_*@CURL_OPENSSL_4'`.

Build the C++ packages with conda removed from the environment:

```bash
env -u CONDA_PREFIX -u CONDA_EXE -u CONDA_PYTHON_EXE -u CONDA_DEFAULT_ENV \
    -u CONDA_SHLVL -u CONDA_PROMPT_MODIFIER \
    PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniconda3 | paste -sd:)" \
    bash -c 'source /opt/ros/humble/setup.bash && colcon build ...'
```

Isaac Sim's `python.sh` warns about the same condition
("running in conda env, please deactivate"), so this is not specific to OpenRAL.

## What this fork gives up

- In-process lerobot VLA adapters (`smolvla`, `pi05`, `xvla`, `act`,
  `diffusion`) and the GR00T in-process path.
- The LIBERO / RoboCasa / MetaWorld / ManiSkill3 / SimplerEnv simulator
  adapters and `openral benchmark` runs that depend on them.
- `LeRobotDatasetSink` (rosbag2 → LeRobotDataset v3 export).
- Driving a real SO-100/SO-101 arm.

None of these are on this project's path, and the first is equally unavailable
on the real LunarBot, which is also Humble/3.10.

## 6. Test suite — `just test` on this fork (commit `4c1867c`)

`5236 passed, 4 failed, 120 skipped, 2 errors` (up from 0 useful signal on the
first run — a mass collection failure). Every fix that follows was a genuine
Python 3.10 gap found by actually running the suite, not predicted in advance;
the earlier grep/AST scans (§5) only covered `python/` and `packages/`, missing
`tools/` and `tests/` entirely.

### Two production-code gaps (not test-only)

- **`datetime.UTC` (3.11+)**, 7 sites / 5 files: `openral_cli/check.py`,
  `openral_detect/detect.py` + `compatibility.py` (×2),
  `openral_reasoner_ros/reasoner_node.py`'s `_memory_now` (on our critical
  path — reasoner memory-archive timestamps), and `tools/validation_matrix.py`
  (×2). All replaced with `datetime.timezone.utc` (identical value, present
  since 3.2).
- **`tools/select_tests.py`**: bare `import tomllib`. Given the same
  stdlib-first fallback as the test files below; `tomli` is now an explicit
  `dev`-group dependency (`pyproject.toml`) rather than riding in
  transitively via mypy's `toml` extra.

### Test-only fixes (mirror a convention this suite already uses elsewhere)

- `import tomllib` → stdlib-first `tomli` fallback in 5 files:
  `test_install_command.py`, `test_lockstep_versions.py`,
  `test_omdet_turbo_detector.py`, `test_locateanything_detector.py`,
  `test_qwen_scene_vlm.py`.
- `pytest.importorskip("lerobot", ...)` added to 5 files that import
  `openral_hal.so100_sim`/`so100_follower` without the guard every other
  lerobot-dependent test already carries: `test_so100_follower_hal.py`,
  `test_thumbnail_throttle.py`, `test_deploy_runner.py`,
  `test_deploy_runner_dataset_recording.py`,
  `test_deploy_runner_observability.py`. Two more converted to a
  whole-module skip (every test in the file needs lerobot):
  `test_vla_core_rtc.py`, `test_chunked_executor_rtc.py`.
- `test_doctest_runner.py`'s curated `DOCTEST_TARGETS`: `so100_sim.py`
  (imports lerobot at module scope — unimportable by path even with the
  `openral_hal.__getattr__` lazy shim, which only helps attribute access
  *through* the package) and `so100_follower.py` (its own docstring example
  imports `so100_sim`) commented out in place, not deleted, so a rebase onto
  a 3.12 target restores both trivially.
- `docs/methods/*.md` `(LNN)` markers refreshed via
  `tools/refresh_methods_linenos.py` (CLAUDE.md's documented remedy) after
  the line-shifting edits above. **Re-run this after any further edit** —
  editing `tools/validation_matrix.py` and `tools/select_tests.py` a second
  time re-drifted `docs/methods/10-tools.md` before I caught it.

### Left deliberately unfixed — verified orthogonal to the 3.10/Humble target

Each of these would fail identically on Jazzy in the same environment; fixing
them would mean editing a further subsystem this patch has no reason to touch.

- `test_install_command.py::test_groups_mirror_workspace_root_pyproject` —
  checks that `openral_cli.install._GROUPS` (the standalone curl-bash Tier-0
  installer's own copy of the dependency-groups table) mirrors the workspace
  root `pyproject.toml`. It now legitimately doesn't, since the lerobot-only
  groups were removed from the latter and `openral install <group>` is not
  part of this project's workflow.
- `test_runtime.py::test_load_safetensors_*` (2) and
  `test_quantize_rskill_auto_map.py` / `test_quantize_rskill_remote_code_gate.py`
  (2, collection errors) — `safetensors` resolves in `uv.lock` (a transitive
  dependency of several optional VLA/HF groups) but is not installed by a bare
  `uv sync --all-packages`, on any Python version. `test_runtime.py`'s own
  module docstring promises "marked with `pytest.importorskip` inside each
  test method"; these two specific tests never got it — a pre-existing gap in
  the test file itself.
- `test_sensor_ros_publisher.py::test_camera_info_intrinsics_scale_with_a_downscaled_image`
  — passes `stamp=None` into a real `std_msgs/Header.stamp` setter, which
  asserts the value is a `builtin_interfaces/Time`. A pre-existing test bug.

## Rebasing onto upstream

Re-apply in this order; nothing here depends on upstream internals beyond the
lines it touches:

1. `sed -i 's/^requires-python = ">=3.12,<3.13"$/requires-python = ">=3.10,<3.11"/' pyproject.toml python/*/pyproject.toml`
2. Strip every `lerobot` requirement per the table above; check for new ones with
   `grep -rn '"lerobot' pyproject.toml python/*/pyproject.toml`.
3. Re-apply the lazy import and the `StrEnum` replacements if upstream reverted them.
4. `uv lock` — treat a failure as a new 3.12-only dependency and find it in the
   solver output, which names the package and the group that pulled it.
5. Re-run `just test`; re-apply §6's `datetime.UTC`/`tomllib`/`importorskip`/
   `DOCTEST_TARGETS` fixes against whatever grep/AST missed this time, then
   `tools/refresh_methods_linenos.py` last, after every other edit.

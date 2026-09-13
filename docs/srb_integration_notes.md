# Space Robotics Bench integration notes — pinned revision

Traced 2026-09-13 against the SRB working tree at `7528ff8` (v0.0.6) plus
in-progress, uncommitted LunarBot integration work (another agent's WIP —
this session did not edit, commit, or branch anything under
`space_robotics_bench/`; every command below was read/run-only). Source paths
below; re-check after the WIP lands and gets pinned to a commit.

Robot embodiment: **`lunar_bot`** (category `mobile_manipulator`, type
`WheeledManipulator`), per explicit user decision — not chosen by the "least
integration work" heuristic in plan §6.2, since it is already substantially
integrated. Teleop and self-collision are still being worked on by the other
agent at the time of writing; not blocking for what follows.

---

## 1. Registration and a basic run

`srb ls` confirms `lunar_bot` is registered and `_ground_manipulation` (the
mobile-manipulation template, plan §6.3) accepts it via Hydra override:

```
srb agent rand --env _ground_manipulation env.robot=lunar_bot --headless --perf --perf_duration 20
```

Ran clean: 729 steps in 20.02 s (~36.4 steps/s), 500-step / 10 s episodes, exit
0. Robot selection is a plain Hydra dotlist key (`env.robot=...`), documented
inline at `srb/core/env/mobile_manipulation/ground_manipulation/env.py:75`.

## 2. Two host-environment traps — found and fixed, same class as the OpenRAL ones

Both are host-environment pollution, not SRB bugs, and both only surface with
`--interface ros`. Neither should be re-discovered the hard way next time.

### 2.1 The host's default ROS-Humble sourcing breaks Isaac Sim's own rclpy

`~/.bashrc` sources `/opt/ros/humble/setup.bash` in every login shell, putting
the **system** `rclpy` (built for cpython-**310**) on `PYTHONPATH` before
Isaac Sim's kit-python (**3.11**) even starts. `enable_ros2_bridge()`
(`srb/utils/ros.py:9`) does:

```python
if find_spec("rclpy"):      # finds the system package first — short-circuits
    return True              # before appending Isaac Sim's own bundled path
```

So Isaac Sim's 3.11 interpreter tries to import the system package, gets to
`rclpy.impl.implementation_singleton`, and fails:

```
ModuleNotFoundError: No module named 'rclpy._rclpy_pybind11'
The C extension '/opt/ros/humble/lib/python3.10/site-packages/_rclpy_pybind11.cpython-311-...so' isn't present
```

(cpython-311 in that message is Isaac Sim's interpreter tag; the file that
actually exists at that path is built for cpython-310 — the system package,
not Isaac Sim's bundled one.) **Fix: unset `PYTHONPATH` for the SRB launch.**
It is not needed — Isaac Sim resolves its own bundled `humble/`/`jazzy/` rclpy
once `PYTHONPATH` isn't pre-poisoned.

### 2.2 `ISAAC_SIM_PATH` is not set (only `ISAAC_SIM_PYTHON` is)

`get_isaacsim_path()` (`srb/utils/isaacsim.py:8`) reads `ISAAC_SIM_PATH`, falls
back to `$HOME/isaac-sim` (doesn't exist on this machine — the real install is
`~/Programs/isaac-sim`), then falls back to the hardcoded `/root/isaac-sim`
(a Docker-image path this user cannot read):

```
PermissionError: [Errno 13] Permission denied: '/root/isaac-sim/exts/isaacsim.ros2.bridge/humble/lib'
```

**Fix: export `ISAAC_SIM_PATH=~/Programs/isaac-sim`** alongside the existing
`ISAAC_SIM_PYTHON` (see `srb-native-install` memory). Not yet added to
`~/.bashrc` — recommended to the user, not done unilaterally; only set
per-invocation below.

### Working invocation

```bash
env -u CONDA_PREFIX -u CONDA_EXE -u CONDA_PYTHON_EXE -u CONDA_DEFAULT_ENV \
    -u CONDA_SHLVL -u CONDA_PROMPT_MODIFIER -u PYTHONPATH \
    ISAAC_SIM_PATH="$HOME/Programs/isaac-sim" \
    PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniconda3 | paste -sd:)" \
    srb agent <zero|rand|ros> --env _ground_manipulation env.robot=lunar_bot \
    --headless --interface ros
```

`enable_ros2_bridge()` is called with no arguments (`srb/interfaces/interface/ros.py:6`)
→ default `distro="humble"`, matching the OpenRAL side. Isaac Sim bundles its
own cpython-311 rclpy for both `humble/` and `jazzy/` (confirmed in
`docs/upstream_pins.md`), so this is a wire-format choice, not a real
dependency on the host's ROS install.

## 3. Real topics, types, QoS — `_ground_manipulation env.robot=lunar_bot`

### 3.1 Observation topics (present in every `--interface ros` mode)

| Topic | Type | Notes |
|---|---|---|
| `/srb/env0/robot/joint_states` | `sensor_msgs/msg/JointState` | 21 named joints — confirms `WheeledManipulator` structure: `chassis_to_{front,rear}_{left,right}_steering_joint` (4), `*_steering_to_wheel_joint` (4), `joint1`–`joint7` (7-DoF arm), `eg2_joint1`–`eg2_joint6` (6-DoF gripper) |
| `/srb/env0/imu_robot` | `sensor_msgs/msg/Imu` | |
| `/srb/env0/reward` | `std_msgs/msg/Float32` | |
| `/srb/env0/reward/penalty_action_rate` | `std_msgs/msg/Float32` | per-term reward, `_srb_interfaces` "reward_terms" |
| `/srb/env0/reward/penalty_undesired_robot_contacts` | `std_msgs/msg/Float32` | self-collision-adjacent signal — relevant to the other agent's current work |
| `/srb/env0/terminated`, `/srb/env0/truncated` | `std_msgs/msg/Bool` | |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | full scene transform tree, `srb/env0` → `srb/env0/robot` etc. |
| `/clock` | `rosgraph_msgs/msg/Clock` | sim time |

All observed: `Reliability: RELIABLE`, `Durability: VOLATILE`, depth
`UNKNOWN` (rmw doesn't report it back), no deadline/lifespan. Source:
`RosInterface.update()`, `srb/interfaces/interface/ros.py:195-283`.
`ros2 node list` reports nothing — the bridge's DDS participant doesn't
surface node-name info the way a normal rclpy node would (`Node name:
_NODE_NAME_UNKNOWN_` on every `topic info -v`); topics/types/QoS are still
fully queryable and functional despite that.

### 3.2 Action topics — mode-dependent, and this matters

`agent zero`/`agent rand` (SRB generates the action internally) publish one
combined echo, `/srb/env0/action` (`Float32MultiArray`, the full action
vector — 9-dim for lunar_bot, all-zero under `agent zero`) purely for
observability. **This topic does not accept external commands** —
`Subscription count: 0` in every check.

`agent ros` mode calls `RosInterface.setup_action_sub()`
(`srb/interfaces/interface/ros.py:299`), which creates one subscription **per
action term** instead, and the combined echo publisher is skipped once that
happens (`update()`'s guard: `if not hasattr(self, "_sub_action_term") and
action is not None`). This is the actual control surface:

| Topic | Type | Drives |
|---|---|---|
| `/srb/env0/action/cmd_vel` | `geometry_msgs/msg/Twist` | base velocity (high-level convenience surface) |
| `/srb/env0/action/event` | `std_msgs/msg/Bool` | discrete event action |
| `/srb/env0/robot/robot/four_wheel_steer` | `std_msgs/msg/Float32MultiArray` | per-wheel steer/drive, matches the new `four_wheel_steer` action term |
| `/srb/env0/robot/robot/differential_inverse_kinematics` | `geometry_msgs/msg/Twist` | 7-DoF arm, IK-driven |
| `/srb/env0/robot/robot/binary_joint_position` | `std_msgs/msg/Bool` | gripper open/close |

Plus batched `/srb/envs/action/{cmd_vel,event}` and
`/srb/envs/robot/robot/{...}` variants (the `envs/` — plural — prefix subscribes
across all parallel env replicas at once; `env0/` is the per-replica mirror).
Per-term topic naming: `envs/{action_term.cfg.asset_name}/{action_key}` — see
`setup_action_sub()`, `ros.py:299-330`.

### 3.3 Verified: a ROS command actually moves the robot

```bash
ros2 topic pub --rate 10 /srb/env0/action/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.5, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

`srb/env0/robot`'s pose on `/tf`, base translation `x`: **`-0.131 → 0.496`**
over ~4 s of commanding — a real, substantial displacement, not a stub
response. This closes the last open item of plan §6.1/A3 ("verify ROS 2
interface publication/control... in active workflow mode").

## 4. Process hygiene on this shared host — record for every future session

This host runs multiple concurrent Isaac Sim instances across sessions/agents
(GPU has room — 2× RTX 5090, 32 GB each). **Never `pkill -f` against a
pattern that only *resembles* your own process's command line** — `srb agent
zero -e ... env.robot=lunar_bot --headless` (another agent's long-running
debug session) and `srb agent zero --env ... env.robot=lunar_bot --headless
--interface ros` (this session's test) differ only in flag spelling and both
contain "srb agent zero" as a substring. A `pkill -f "srb agent zero"` run
mid-session killed both of the other agent's long-running processes by
accident. **Always resolve the exact PID (`ps aux` / `pgrep -a -f`, read the
full command line, confirm which one is actually yours) and `kill` only that
PID** — including the reparented kit-python child, since killing the
`python.sh` wrapper does not reliably take the child down with it (observed:
wrapper died, kit-python child survived, reparented to `init`).

## 5. Open for A4 / Phase B

- LunarBot's teleop and self-collision work is in progress elsewhere; nothing
  here depends on it being finished.
- The per-term action topics (§3.2) are almost certainly the right OpenRAL↔SRB
  integration surface for Phase B (rather than the combined vector), since
  they carry typed, semantically-named commands (`cmd_vel`, IK twist, gripper
  bool) that map more directly onto rSkill goal parameters than a raw
  9-float vector would.
- `/srb/env0/reward/penalty_undesired_robot_contacts` is a ready-made signal
  worth checking against once self-collision handling stabilizes — it may be
  directly usable evidence for a verification/FDIR mapping later, without
  building a new detector.

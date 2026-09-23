#!/bin/bash
# Phase D0 live check: boots `openral deploy sim` on a Mission A/B scene (reasoner off) and runs
# the capability-path check against it, then tears the whole graph down.
#
#   [D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml] [D0_CHECK=d0_mission_b_check.py] [D0_STEPS=1,2] \
#   experiments/launch/lunar_base_d0/run_d0.sh <log_dir>
#
# Launch detached (setsid nohup ... &): this tool's background tasks get killed as "low memory"
# around Isaac Sim (F46 §8). (no `set -u`: ROS setup.bash reads unset variables)
LOG=${1:?log dir}
mkdir -p "$LOG"
# bash reads a script as it runs: editing this file under a live run made three runners die mid-run on a syntax
# error and skip their teardown (research repo F51). Every run executes its own frozen copy.
if [ -z "$D0_HERE" ]; then
  D0_HERE=$(cd "$(dirname "$0")" && pwd) && export D0_HERE
  cp "$0" "$LOG/run_d0.sh" && exec bash "$LOG/run_d0.sh" "$@"
fi
HERE=$D0_HERE
cd "$HERE/../../../openral"
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=${D0_DOMAIN:-77} ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST  # D0_DOMAIN=78 for a second graph on GPU 1
# camera images need large shared-memory segments, or most frames are lost in transport (fastdds_large_shm.xml)
export FASTRTPS_DEFAULT_PROFILES_FILE="$HERE/fastdds_large_shm.xml"
# Two graphs share this host (GPU 0 / GPU 1): the deploy CLI's argv-signature reaps at start and exit, and its
# Fast-DDS SHM purge, would kill or silence the sibling (research repo F51). This script's own teardown is by run tag.
export OPENRAL_SKIP_ORPHAN_REAP=1
# Both the reasoner and the scene/grasp VLM run on DeepSeek's own endpoint, on its key (the second one in
# AGENT/VLM_provider.md). The shared gateway is no longer used: a `select` request that answered in 2-9 s from a shell
# hung for the full 300 s deadline from inside the runner, run after run (research repo F58). It needs no proxy, and
# the host's SOCKS proxy breaks httpx without socksio (research repo F38).
SPACE_LLM_API_KEY=$(grep -o 'sk-[A-Za-z0-9_-]*' "$HERE/../../../AGENT/VLM_provider.md" | tail -1) && export SPACE_LLM_API_KEY
SPACE_REASONER_API_KEY=$SPACE_LLM_API_KEY && export SPACE_REASONER_API_KEY
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
SCENE=${D0_SCENE:-scenes/deploy/srb_lunar_base_mission_b.yaml}
if [ -n "$D0_VIDEO$D0_GPU$D0_SCENERY$D0_SCENARIO$D0_PROFILE$D0_GPU_PHYSICS" ]; then
  # A copy of the scene, adjusted for this run:
  #   D0_VIDEO=<file.mp4>  SRB streams a robot-following viewer camera to that file (srb/utils/video_stream.py);
  #                        rendering costs wall time, so only for runs already known to pass. D0_VIDEO_RES ("W,H",
  #                        default 960,540), D0_VIDEO_STRIDE (env steps per frame, 5 = 10 fps of sim time) and
  #                        D0_VIDEO_SPEEDUP (1 = played at sim time) go with it. Raise the resolution before the
  #                        frame rate: bv1 rendered enough to drag the sim to 0.06x real time and the arm's hold
  #                        sagged 15 cm until `servo over shelf` stalled -- the render broke the run, not the skill.
  #   D0_GPU=1             SRB on the second GPU (a parallel graph; pair with D0_DOMAIN=78).
  #   D0_SCENERY=<name>    another SRB scenery for the same task (e.g. lunar_base_route_block).
  #   D0_SCENARIO=<name>   the task's env.scenario (e.g. heldout_module_failure).
  #   D0_GPU_PHYSICS=1     GPU PhysX (SRB_SIM_DEVICE=cuda, CCD off) instead of CPU PhysX.
  #   D0_PROFILE=1         SRB's per-tick bucket timing (SRB_ROS_PROFILE, printed every 100 ticks, research repo F28).
  .venv/bin/python - "$SCENE" "$LOG/scene_run.yaml" "$D0_VIDEO" "$D0_GPU" "$D0_SCENERY" "$D0_SCENARIO" "$D0_PROFILE" "$D0_GPU_PHYSICS" <<'PY'
import os, sys, yaml
src, dst, video, gpu, scenery, scenario, profile, gpu_physics = sys.argv[1:]
d = yaml.safe_load(open(src))
argv = d["simulator"]["argv"]
if video:
    argv.insert(argv.index("--env"), "--video")
    d["simulator"].setdefault("env_set", {}).update(SRB_VIDEO_PATH=video, SRB_VIDEO_FOLLOW="robot",
                                                   SRB_VIDEO_STRIDE=os.environ.get("D0_VIDEO_STRIDE", "5"),
                                                   SRB_VIDEO_SPEEDUP=os.environ.get("D0_VIDEO_SPEEDUP", "1"),
                                                   SRB_VIDEO_RES=os.environ.get("D0_VIDEO_RES", "960,540"))
    d["simulator"]["boot_timeout_s"] = 1800.0
if gpu_physics:
    d["simulator"].setdefault("env_set", {})["SRB_SIM_DEVICE"] = "cuda"
if profile:
    d["simulator"].setdefault("env_set", {})["SRB_ROS_PROFILE"] = "1"
if gpu:
    argv[argv.index("--env"):argv.index("--env")] = ["--kit_args", f"--/renderer/activeGpu={gpu} --/physics/cudaDevice={gpu}"]
if scenario:
    argv[:] = [f"env.scenario={scenario}" if a.startswith("env.scenario=") else a for a in argv]
if scenery:
    argv.insert(argv.index("--headless"), f"env.scenery={scenery}")
yaml.safe_dump(d, open(dst, "w"), sort_keys=False)
PY
  SCENE="$LOG/scene_run.yaml"
fi
D0_RUN_TAG="$LOG" setsid .venv/bin/openral deploy sim --config "$SCENE" --no-enable-octomap --no-object-detector > "$LOG/deploy.log" 2>&1 &
DEPLOY=$!
echo "DEPLOY_PID $DEPLOY sid $(ps -o sid= -p $DEPLOY)" > "$LOG/deploy.pid"
sleep 30
# the CLI setsid()s its `ros2 launch` child: a second session that neither the group kill nor a
# session kill on $DEPLOY reaches (stale launch trees survived runs 3-7 that way)
LAUNCH=$(pgrep -P "$DEPLOY" | head -1)
echo "LAUNCH_PID $LAUNCH sid $(ps -o sid= -p "$LAUNCH")" >> "$LOG/deploy.pid"
if [ -n "$D0_CAPABILITY_SERVER" ]; then
  # the common capability boundary (§21.4) for boundary-driven checks; tagged so the teardown takes it down too
  source ../ros/install/setup.bash
  export D0_LOG="$LOG"
  D0_RUN_TAG="$LOG" setsid .venv/bin/python ../openral_ext/capability_server/node.py > "$LOG/capability_server.log" 2>&1 &
fi
# wall-clock cap only against a hung check: every skill and check deadline is on the sim clock, and a rendering
# Mission B at 0.06x needs more than 50 min of wall time (run bv1 was cut at 3000 s)
if [ -n "$D0_PERCEPTION" ]; then
  # relative perception (openral_ext/perception): fiducial targets in the camera images -> carrier poses; needs a scene
  # with cameras; the boundary and the planning scene take their targets from it (no simulator truth); tagged
  D0_RUN_TAG="$LOG" setsid .venv/bin/python ../openral_ext/perception/fiducial_node.py > "$LOG/perception.log" 2>&1 &
fi
if [ "${D0_PLANNING_SCENE:-1}" != 0 ]; then
  # the worksite in MoveIt's planning scene (openral_ext/planning_scene) -- part of the shared stack every method
  # plans in, on by default (D0_PLANNING_SCENE=0 turns it off); tagged for the teardown
  D0_RUN_TAG="$LOG" setsid .venv/bin/python ../openral_ext/planning_scene/node.py > "$LOG/planning_scene.log" 2>&1 &
fi
# The check is an actuator client too. A failed boot must not leave it waiting
# to command a later graph in the same ROS domain after teardown.
D0_RUN_TAG="$LOG" timeout 14400 .venv/bin/python "$HERE/${D0_CHECK:-d0_mission_b_check.py}" > "$LOG/check.log" 2>&1
echo "CHECK_EXIT $?" >> "$LOG/check.log"
if [ -n "$D0_HOLD" ]; then
  # step-wise development: the graph stays up after the check for attach_d0.sh (continue from the failed step);
  # teardown_d0.sh <log> takes it down
  echo held > "$LOG/held"
  exit 0
fi
bash "$HERE/teardown_d0.sh" "$LOG"
echo done > "$LOG/done"

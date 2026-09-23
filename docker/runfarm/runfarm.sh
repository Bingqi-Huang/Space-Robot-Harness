#!/bin/bash
# Run one command in the run-farm image on one GPU (docs/heldout_design.md §11). The container has its own network
# namespace, so two runs' ROS domains and ports (EUROPA's HostLink 47810) cannot collide; the host's home installs,
# caches and the repo are mounted at their own paths, so every path in the code is the development machine's.
#
#   docker/runfarm/runfarm.sh <gpu> <container name> <command...>
#   e.g. docker/runfarm/runfarm.sh 3 rf-plexil-a D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_a_check.py \
#          /mnt/SharedData/Research/Space_Robot_Harness/experiments/launch/lunar_base_d0/run_d0.sh <abs run dir>
# The GPU comes through CDI (Docker 29 resolves `--gpus` through CDI too; the host needs
# `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`, again after a driver upgrade). Inside the container
# the one GPU is device 0: leave D0_GPU unset. A held graph (D0_HOLD=1) ends with the container;
# append `; sleep infinity` to keep it, and `docker stop <name>` takes it down. An interactive shell on one GPU
# (exploration, a held graph to attach to): `runfarm.sh 0 rf-dev-0 sleep infinity`, then `docker exec -it rf-dev-0 bash -l`.
#
# Shader and CUDA kernel caches: Kit's are under ~/.cache/ov, the driver's compute cache under ~/.nv; both are
# mounted, so only the first container on this host compiles them, not every run.
#
# Network: the host reaches the internet through a proxy on its own 127.0.0.1 with fake-IP DNS, neither usable from a
# container; the run needs only the DeepSeek API (LLM + VLM), reachable directly, so the container uses public DNS.
#
# CPU: an Isaac process starts a thread per visible core, and two unpinned graphs on one host ran at 0.05x each
# (F54 §4). Each container therefore gets its own 10 physical cores + their hyperthreads on its GPU's socket
# (pro6000: GPUs 0-2 on socket 0 = cores 0-31, GPUs 3-5 on socket 1 = cores 32-63, siblings at +64); cores 30-31 and
# 62-63 stay for the host. RUNFARM_CPUS overrides it (the development machine: RUNFARM_CPUS=0-23).
GPU=${1:?gpu index}
NAME=${2:?container name}
shift 2
BASE=$((32 * (GPU / 3) + 10 * (GPU % 3)))
CPUS=${RUNFARM_CPUS:-$BASE-$((BASE + 9)),$((BASE + 64))-$((BASE + 73))}
H=/home/bingqi
# ROS: every container gets its own domain. Its own network namespace does not isolate DDS -- the containers share
# the docker bridge, and Humble ignores ROS_AUTOMATIC_DISCOVERY_RANGE (Iron and later), so on one domain two runs
# discovered each other and one run's check commanded the other's robot (navrepro_1-3 against site_check_12).
docker run -d --rm --name "$NAME" --device "nvidia.com/gpu=$GPU" --cpuset-cpus "$CPUS" --shm-size 32g -e D0_DOMAIN=$((77 + GPU)) \
  --ulimit nofile=65536:65536 --dns 223.5.5.5 --dns 119.29.29.29 \
  -v "$H/Programs:$H/Programs" -v "$H/isaaclab:$H/isaaclab" -v "$H/.cache:$H/.cache" \
  -v "$H/.local/share/ov:$H/.local/share/ov" -v "$H/.nvidia-omniverse:$H/.nvidia-omniverse" -v "$H/.nv:$H/.nv" \
  -v /mnt/SharedData:/mnt/SharedData \
  runfarm:22.04 bash -lc "$*"

# Run-farm image (docs/heldout_design.md §11): the development machine's system layer -- Ubuntu 22.04, the same
# `ros-humble-*` package set, the build/runtime libraries PLEXIL, EUROPA and Isaac Sim need. Nothing of the home
# directory is baked in: `~/Programs` (isaac-sim, plexil, europa, europa-deps, blender), `~/isaaclab`, the caches and the
# repo are rsynced to the host at the same paths and bind-mounted (runfarm.sh), so every path in the code is unchanged.
#
#   docker build --network host --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t runfarm:22.04 docker/runfarm
FROM docker.m.daocloud.io/library/ubuntu:22.04

ARG UID=1000
ARG GID=1000
ARG MIRROR=http://mirrors.tuna.tsinghua.edu.cn
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=Asia/Shanghai

RUN sed -i "s|http://archive.ubuntu.com|${MIRROR}|g; s|http://security.ubuntu.com|${MIRROR}|g" /etc/apt/sources.list \
 && apt-get update && apt-get install -y --no-install-recommends ca-certificates gnupg curl \
 && rm -rf /var/lib/apt/lists/*

COPY ros.asc /usr/share/keyrings/ros-archive-keyring.asc
RUN echo "deb [signed-by=/usr/share/keyrings/ros-archive-keyring.asc] ${MIRROR}/ros2/ubuntu jammy main" \
      > /etc/apt/sources.list.d/ros2.list

# the same ROS package set as the development machine (dpkg -l ros-humble-*, 2026-09-23)
COPY ros_humble_packages.txt /tmp/
RUN apt-get update && xargs -a /tmp/ros_humble_packages.txt apt-get install -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

# build tools (colcon for ros/, PLEXIL's javac 11 + the prebuilt ant/gperf in ~/Programs, EUROPA's Boost 1.74),
# the adapter's JSON, the system python the openral .venv points at, Isaac Sim's X/GL/Vulkan runtime libraries,
# and what the launch scripts call (ffmpeg, pgrep, setsid, timeout)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git pkg-config sudo less nano procps psmisc iproute2 iputils-ping rsync sqlite3 ffmpeg \
      python3 python3-pip python3-venv python3-dev python3-numpy python3-yaml python3-opencv \
      python3-colcon-common-extensions python3-rosdep python3-vcstool \
      openjdk-11-jdk-headless libboost-all-dev nlohmann-json3-dev \
      libgl1 libegl1 libglu1-mesa libvulkan1 vulkan-tools libgomp1 libatomic1 libsm6 libice6 libxt6 libxi6 \
      libxrandr2 libxinerama1 libxcursor1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libfreetype6 libxext6 \
      libxrender1 libx11-6 libx11-xcb1 libxcb1 libglib2.0-0 libnss3 libasound2 \
 && rm -rf /var/lib/apt/lists/*

# the NVIDIA driver's Vulkan/EGL entry points are injected by the container toolkit (NVIDIA_DRIVER_CAPABILITIES=all)
ENV NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=all

# the host user, same name, uid/gid and home path as the files it owns
RUN groupadd -g ${GID} bingqi && useradd -m -u ${UID} -g ${GID} -s /bin/bash bingqi \
 && echo "bingqi ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/bingqi \
 && mkdir -p /mnt/SharedData && chown bingqi:bingqi /mnt/SharedData
USER bingqi
WORKDIR /home/bingqi
RUN printf '%s\n' 'source /opt/ros/humble/setup.bash' \
      "export ISAAC_SIM_PYTHON=/home/bingqi/Programs/isaac-sim/python.sh" \
      'export PATH="/home/bingqi/.local/bin:$PATH"' >> /home/bingqi/.bashrc

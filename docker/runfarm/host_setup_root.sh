#!/bin/bash
# One-time root setup of a run-farm host (docs/heldout_design.md §11). Run as: sudo bash host_setup_root.sh
# Does not restart the Docker daemon (the host is shared; `--gpus` works through the toolkit's hook without it).
set -e
USER_NAME=bingqi
# 1. docker without sudo for the run user (takes effect at the next login)
usermod -aG docker "$USER_NAME"
# 2. NVIDIA Container Toolkit, from NVIDIA's apt repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  > /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
apt-get install -y nvidia-container-toolkit
# 3. the repo at the development machine's absolute path, backed by the SSD
mkdir -p /mnt/SharedData
grep -q " /mnt/SharedData " /etc/fstab || echo "/nvme01/$USER_NAME/SharedData /mnt/SharedData none bind 0 0" >> /etc/fstab
mountpoint -q /mnt/SharedData || mount /mnt/SharedData
echo "done: docker group (re-login), nvidia-container-toolkit $(nvidia-ctk --version | head -1), /mnt/SharedData -> /nvme01/$USER_NAME/SharedData"

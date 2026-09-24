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
# the GPUs as CDI devices (runfarm.sh: --device nvidia.com/gpu=N); regenerate after a driver upgrade
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
# 3. the repo at the development machine's absolute path, backed by the SSD /nvme02 (nofail: a missing source must not stop boot)
mkdir -p /mnt/SharedData
grep -q " /mnt/SharedData " /etc/fstab || echo "/nvme02/$USER_NAME/SharedData /mnt/SharedData none bind,nofail 0 0" >> /etc/fstab
mountpoint -q /mnt/SharedData || mount /mnt/SharedData
# 4. socket buffers for DDS inside the containers (not namespaced, so set on the host; F113): a 1.2 MB camera image
#    over UDP needs more than the kernel's 208 kB default per socket (Cyclone's config asks 8 MB). Raises only the
#    per-socket ceiling; persists across reboots.
printf '%s\n' 'net.core.rmem_max = 67108864' 'net.core.wmem_max = 67108864' 'net.core.netdev_max_backlog = 10000' \
  > /etc/sysctl.d/60-runfarm-dds.conf
sysctl -p /etc/sysctl.d/60-runfarm-dds.conf
echo "done: docker group (re-login), nvidia-container-toolkit $(nvidia-ctk --version | head -1), /mnt/SharedData -> /nvme02/$USER_NAME/SharedData"

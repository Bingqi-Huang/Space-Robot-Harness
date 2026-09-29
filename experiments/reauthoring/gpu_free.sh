#!/bin/bash
# Prints `free` when no container (running or still tearing down) holds the given GPU, else the containers that do.
G=${1:?gpu index}
busy=$(docker ps -a --filter status=running --filter status=removing --filter status=restarting -q | xargs -r docker inspect \
  --format '{{.Name}} {{range .HostConfig.Devices}}{{.PathOnHost}} {{end}}{{range .HostConfig.DeviceRequests}}{{.DeviceIDs}}{{end}}' \
  | grep -E "nvidia.com/gpu=$G([^0-9]|$)" | awk '{print $1}')
[ -z "$busy" ] && echo free || echo "busy: $busy"

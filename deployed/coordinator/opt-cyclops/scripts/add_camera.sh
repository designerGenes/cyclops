#!/usr/bin/env bash
# Add a new eye to Cyclops in one command.
#   scripts/add_camera.sh <ssh-host-or-ip> <camera-name> [cyclops-url]
# Requires: pip install pyinfra ; SSH key access to the node.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST="${1:?usage: add_camera.sh <host> <name> [cyclops-url]}"
NAME="${2:?usage: add_camera.sh <host> <name> [cyclops-url]}"
CYCLOPS_URL="${3:-${CYCLOPS_URL:-http://cyclops:8080}}"
TOKEN="${ENROLL_TOKEN:?set ENROLL_TOKEN to match server config.toml}"

pyinfra "$HOST" provision/deploy_camnode.py \
  --data node_name="$NAME" \
  --data cyclops_url="$CYCLOPS_URL" \
  --data enroll_token="$TOKEN" \
  --data advertise_host="$HOST"

echo
echo "Eye '$NAME' provisioned. It will reboot once if the camera overlay"
echo "was newly enabled, then register itself. Watch it appear at the"
echo "bottom of $CYCLOPS_URL/stream"

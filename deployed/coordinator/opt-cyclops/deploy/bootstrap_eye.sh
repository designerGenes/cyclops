#!/usr/bin/env bash
# Provision an already-booted, reachable Eye entirely over SSH.
#
#   deploy/bootstrap_eye.sh --ip <ip> --key <ssh-key> --name <camera-name> \
#       [--cyclops-url http://cyclops:8080] [--user pi] [--token <enroll-token>]
#
# Everything else is automatic: copies the repo, runs the on-device
# installer, reboots if the camera overlay was newly enabled, waits for
# the node to come back, and confirms it registered with Cyclops.
source "$(dirname "$0")/lib.sh"

CYCLOPS_URL="http://cyclops:8080"; NODE_NAME=""; ADVERTISE=""
while [ $# -gt 0 ]; do case "$1" in
  --ip) TARGET_IP="$2"; shift 2;;
  --key) SSH_KEY="$2"; shift 2;;
  --name) NODE_NAME="$2"; shift 2;;
  --cyclops-url) CYCLOPS_URL="$2"; shift 2;;
  --user) SSH_USER="$2"; shift 2;;
  --token) ENROLL_TOKEN="$2"; shift 2;;
  --advertise) ADVERTISE="$2"; shift 2;;
  *) die "unknown arg: $1";;
esac; done

: "${TARGET_IP:?--ip required}"; : "${SSH_KEY:?--key required}"; : "${NODE_NAME:?--name required}"
ENROLL_TOKEN="${ENROLL_TOKEN:-${ENROLL_TOKEN:-}}"
[ -n "${ENROLL_TOKEN:-}" ] || ENROLL_TOKEN="${CYCLOPS_ENROLL_TOKEN:-}"
: "${ENROLL_TOKEN:?set --token or CYCLOPS_ENROLL_TOKEN (must match server config.toml)}"
[ -f "$SSH_KEY" ] || die "ssh key not found: $SSH_KEY"
ADVERTISE="${ADVERTISE:-$NODE_NAME}"
require_cmd ssh; require_cmd rsync

log "checking SSH to ${SSH_USER}@${TARGET_IP}"
rsh true || die "cannot SSH in. Confirm the key, user, and that the device is up."

log "copying Cyclops repo to the node"
rsync -az --delete -e "ssh $(ssh_opts)" \
  --exclude '.git' --exclude '__pycache__' \
  "$REPO_ROOT/" "${SSH_USER}@${TARGET_IP}:/tmp/cyclops/"

log "running on-device installer (sudo)"
rsh "sudo env NODE_NAME='$NODE_NAME' CYCLOPS_URL='$CYCLOPS_URL' \
     ENROLL_TOKEN='$ENROLL_TOKEN' ADVERTISE_HOST='$ADVERTISE' \
     SRC_DIR=/tmp/cyclops bash /tmp/cyclops/provision/install_camnode.sh"

if rsh "test -f /run/cyclops-reboot-needed"; then
  log "camera overlay newly enabled -> rebooting node"
  rsh "sudo reboot" || true
  sleep 8
  wait_for_ssh
fi

log "verifying registration with Cyclops"
for _ in $(seq 1 12); do
  if rsh "curl -fsS --max-time 4 '$CYCLOPS_URL/api/nodes'" 2>/dev/null | grep -q "\"$NODE_NAME\""; then
    log "eye '$NODE_NAME' is registered and streaming. It will appear at ${CYCLOPS_URL}/stream"
    exit 0
  fi
  sleep 5
done
warn "node provisioned but not yet visible in the registry. Check: journalctl -u camnode -f"

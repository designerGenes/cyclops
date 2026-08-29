#!/usr/bin/env bash
# Provision the Cyclops brain (Pi 5 + AI HAT+) entirely over SSH.
#
#   deploy/bootstrap_cyclops.sh --ip <ip> --key <ssh-key> \
#       [--user pi] [--with-hailo] [--hef /path/to/yolov8s_h8l.hef] \
#       [--public-base http://cyclops:8080]
#
# --with-hailo installs the NPU stack (dkms FIRST, then hailo-all) and
# reboots once. Skip it if you've already run that step. Without a HEF,
# detection runs in motion-fallback mode until you drop one in.
source "$(dirname "$0")/lib.sh"

WITH_HAILO=0; HEF=""; PUBLIC_BASE=""
while [ $# -gt 0 ]; do case "$1" in
  --ip) TARGET_IP="$2"; shift 2;;
  --key) SSH_KEY="$2"; shift 2;;
  --user) SSH_USER="$2"; shift 2;;
  --with-hailo) WITH_HAILO=1; shift;;
  --hef) HEF="$2"; shift 2;;
  --public-base) PUBLIC_BASE="$2"; shift 2;;
  *) die "unknown arg: $1";;
esac; done

: "${TARGET_IP:?--ip required}"; : "${SSH_KEY:?--key required}"
[ -f "$SSH_KEY" ] || die "ssh key not found: $SSH_KEY"
require_cmd ssh; require_cmd rsync

log "checking SSH to ${SSH_USER}@${TARGET_IP}"
rsh true || die "cannot SSH in. Confirm the key, user, and that the Pi 5 is up."

log "base system update"
rsh "sudo DEBIAN_FRONTEND=noninteractive apt-get update -y && \
     sudo DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y && \
     sudo rpi-eeprom-update -a >/dev/null 2>&1 || true"

if [ "$WITH_HAILO" = 1 ]; then
  if rsh "command -v hailortcli >/dev/null && hailortcli fw-control identify >/dev/null 2>&1"; then
    log "Hailo NPU already present, skipping install"
  else
    log "installing Hailo stack (dkms FIRST, then hailo-all — order matters on Trixie)"
    rsh "sudo apt-get install -y dkms && sudo apt-get install -y hailo-all"
    log "rebooting Pi 5 to load the Hailo driver"
    rsh "sudo reboot" || true; sleep 8; wait_for_ssh
    rsh "hailortcli fw-control identify" \
      && log "NPU online" \
      || warn "hailortcli did not identify the device; check the HAT seating and 'dmesg | grep -i hailo'"
  fi
fi

log "copying Cyclops repo to the Pi 5"
rsync -az --delete -e "ssh $(ssh_opts)" \
  --exclude '.git' --exclude '__pycache__' \
  "$REPO_ROOT/" "${SSH_USER}@${TARGET_IP}:/tmp/cyclops/"

log "running server installer (MediaMTX + venv + systemd)"
rsh "cd /tmp/cyclops && sudo bash scripts/install_server.sh"

if [ -n "$HEF" ]; then
  [ -f "$HEF" ] || die "HEF not found: $HEF"
  log "uploading detection model"
  rcp "$HEF" "${SSH_USER}@${TARGET_IP}:/tmp/model.hef"
  rsh "sudo install -m 644 /tmp/model.hef /opt/cyclops/models/yolov8s.hef"
fi
if [ -n "$PUBLIC_BASE" ]; then
  rsh "sudo sed -i 's#^public_base = .*#public_base = \"$PUBLIC_BASE\"#' /opt/cyclops/config.toml"
fi

ENROLL=$(rsh "grep -E '^enroll_token' /opt/cyclops/config.toml | head -1 | cut -d'\"' -f2" || true)
rsh "sudo systemctl restart cyclops"
log "Cyclops is up: ${PUBLIC_BASE:-http://<pi5>:8080}/stream"
if [ "$ENROLL" = "CHANGE-ME" ] || [ -z "$ENROLL" ]; then
  warn "Set a real enroll_token + Twilio creds: ssh in and edit /opt/cyclops/config.toml, then 'sudo systemctl restart cyclops'."
  warn "Use that SAME token when adding eyes (--token or CYCLOPS_ENROLL_TOKEN)."
else
  log "enroll_token is set. Add eyes with that token via deploy/bootstrap_eye.sh or deploy/make_eye_sdcard.sh"
fi

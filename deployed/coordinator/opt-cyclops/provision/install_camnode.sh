#!/usr/bin/env bash
# Turn this Raspberry Pi Zero 2 W into a Cyclops eye. Idempotent.
# Reads its settings from the environment (the caller sets them):
#   NODE_NAME       unique camera name / hostname (required)
#   CYCLOPS_URL     e.g. http://cyclops:8080            (required)
#   ENROLL_TOKEN    shared secret matching the server   (required)
#   ADVERTISE_HOST  host Cyclops reaches this node at    (default: NODE_NAME)
#   SRC_DIR         dir holding the camnode payload      (default: script's repo)
# Writes /run/cyclops-reboot-needed if config.txt changed; the CALLER reboots.
set -euo pipefail

: "${NODE_NAME:?NODE_NAME required}"
: "${CYCLOPS_URL:?CYCLOPS_URL required}"
: "${ENROLL_TOKEN:?ENROLL_TOKEN required}"
ADVERTISE_HOST="${ADVERTISE_HOST:-$NODE_NAME}"
SRC_DIR="${SRC_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
BOOT_CFG="/boot/firmware/config.txt"
[ -f "$BOOT_CFG" ] || BOOT_CFG="/boot/config.txt"   # very old layout fallback

say() { printf '[install_camnode] %s\n' "$*"; }

# --- packages (libcamera/rpicam ship with the OS) ---
say "installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends rpicam-apps-lite python3 curl ca-certificates

# --- camera enable: Pi Zero 2 W IMX708 overlay (NO vcm=off,cam0 params) ---
# The IMX708 overlay with vcm=off,cam0 creates an I2C multiplexer that the
# kernel doesn't expose to userspace. Use simple dtoverlay=imx708 instead.
changed=0
if grep -q '^camera_auto_detect=0' "$BOOT_CFG"; then
  sed -i 's/^camera_auto_detect=0/camera_auto_detect=1/' "$BOOT_CFG"; changed=1
elif ! grep -q '^camera_auto_detect=1' "$BOOT_CFG"; then
  printf '\ncamera_auto_detect=1\n' >> "$BOOT_CFG"; changed=1
fi
grep -q '^dtoverlay=imx708$' "$BOOT_CFG" || { printf 'dtoverlay=imx708\n' >> "$BOOT_CFG"; changed=1; }
grep -q '^dtparam=watchdog=on' "$BOOT_CFG" || { printf 'dtparam=watchdog=on\n' >> "$BOOT_CFG"; changed=1; }
grep -q '^dtoverlay=disable-bt' "$BOOT_CFG" || { printf 'dtoverlay=disable-bt\n' >> "$BOOT_CFG"; changed=1; }
[ "$changed" = 1 ] && touch /run/cyclops-reboot-needed && say "config.txt updated; reboot will be needed"

# --- MediaMTX (latest arm64 release) ---
if [ ! -x /opt/mediamtx/mediamtx ]; then
  say "installing MediaMTX"
  mkdir -p /opt/mediamtx
  url=$(curl -fsSL https://api.github.com/repos/bluenviron/mediamtx/releases/latest \
        | grep browser_download_url | grep linux_arm64 | grep -o 'https://[^"]*' | head -1)
  [ -n "$url" ] || { echo "could not resolve MediaMTX download url"; exit 1; }
  curl -fsSL -o /tmp/mediamtx.tgz "$url"
  tar xzf /tmp/mediamtx.tgz -C /opt/mediamtx mediamtx
fi
install -m 644 "$SRC_DIR/provision/files/mediamtx.yml.j2" /opt/mediamtx/mediamtx.yml

# --- camnode agent ---
say "installing camnode agent"
mkdir -p /opt/camnode/camnode
install -m 644 "$SRC_DIR"/node/camnode/*.py /opt/camnode/camnode/
cat > /opt/camnode/camnode.toml <<TOML
name = "${NODE_NAME}"
cyclops_url = "${CYCLOPS_URL}"
enroll_token = "${ENROLL_TOKEN}"
advertise_host = "${ADVERTISE_HOST}"
reboot_after_unreachable_s = 600
TOML
chmod 600 /opt/camnode/camnode.toml

# --- resilience plumbing ---
install -m 644 "$SRC_DIR/provision/files/mediamtx.service"  /etc/systemd/system/mediamtx.service
install -m 644 "$SRC_DIR/provision/files/camnode.service"   /etc/systemd/system/camnode.service
mkdir -p /etc/systemd/system.conf.d /etc/NetworkManager/conf.d
install -m 644 "$SRC_DIR/provision/files/watchdog.conf"     /etc/systemd/system.conf.d/watchdog.conf
install -m 644 "$SRC_DIR/provision/files/wifi-nosleep.conf" /etc/NetworkManager/conf.d/wifi-nosleep.conf

systemctl daemon-reload
systemctl enable mediamtx.service
systemctl enable camnode.service
systemctl restart mediamtx.service
systemctl restart camnode.service
# nudge NetworkManager to drop wifi powersave now (no reboot required for this)
nmcli radio wifi on >/dev/null 2>&1 || true

say "done. eye='${NODE_NAME}' -> ${CYCLOPS_URL} (advertise ${ADVERTISE_HOST})"
[ -f /run/cyclops-reboot-needed ] && say "REBOOT REQUIRED to load camera overlay"
exit 0

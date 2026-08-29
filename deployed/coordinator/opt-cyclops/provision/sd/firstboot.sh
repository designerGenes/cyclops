#!/usr/bin/env bash
# Runs once on the Eye's first boot (invoked by cloud-init runcmd).
# Joins Tailscale, installs the camnode stack, then reboots to load the
# camera overlay. Self-contained: everything it needs is already on the
# boot partition under /boot/firmware/cyclops/.
set -uo pipefail
exec >>/var/log/cyclops-firstboot.log 2>&1
echo "=== cyclops firstboot $(date -Is) ==="

PAYLOAD=/boot/firmware/cyclops
[ -d "$PAYLOAD" ] || PAYLOAD=/boot/cyclops
ENVF="$PAYLOAD/eye.env"
[ -f "$ENVF" ] || { echo "missing $ENVF — aborting"; exit 1; }
# shellcheck disable=SC1090
source "$ENVF"   # NODE_NAME CYCLOPS_URL ENROLL_TOKEN TS_TAGS

SENTINEL=/var/lib/cyclops-provisioned
if [ -f "$SENTINEL" ]; then echo "already provisioned; nothing to do"; exit 0; fi

# --- wait for network (WiFi from network-config) ---
for _ in $(seq 1 60); do
  ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 && break
  sleep 3
done

# --- Tailscale: install + headless join with the baked auth key ---
if [ -f "$PAYLOAD/tailscale.authkey" ]; then
  echo "installing tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
  AUTHKEY="$(cat "$PAYLOAD/tailscale.authkey")"
  echo "joining tailnet as ${NODE_NAME}"
  tailscale up --authkey="$AUTHKEY" --hostname="$NODE_NAME" \
    ${TS_TAGS:+--advertise-tags="$TS_TAGS"} --accept-dns=true || \
    echo "WARNING: tailscale up failed; will rely on LAN reachability"
  # one-time key consumed — remove it from the (FAT32) boot partition
  shred -u "$PAYLOAD/tailscale.authkey" 2>/dev/null || rm -f "$PAYLOAD/tailscale.authkey"
  ADVERTISE_HOST="$NODE_NAME"   # MagicDNS name == hostname
else
  echo "no tailscale.authkey present; using LAN hostname"
  ADVERTISE_HOST="$(hostname).local"
fi

# --- install the camnode stack via the shared installer ---
echo "running install_camnode.sh"
NODE_NAME="$NODE_NAME" CYCLOPS_URL="$CYCLOPS_URL" ENROLL_TOKEN="$ENROLL_TOKEN" \
  ADVERTISE_HOST="$ADVERTISE_HOST" SRC_DIR="$PAYLOAD/repo" \
  bash "$PAYLOAD/repo/provision/install_camnode.sh"

touch "$SENTINEL"
# scrub remaining secrets from the boot partition
shred -u "$ENVF" 2>/dev/null || rm -f "$ENVF"

echo "firstboot complete; rebooting to load camera overlay"
sleep 2
systemctl reboot

#!/bin/sh
# Provision a freshly flashed Cyclops Luckfox eye over ADB.
#
#   provision-eye.sh <node_name> [brain_url] [token]
#
# Writes /oem/etc/cyclops-eye.conf (persists across reboots), optionally
# installs the admin SSH key, and reboots so the eye self-registers.
# The token defaults to reading the brain's shared enroll token over SSH.
set -eu

NAME=${1:?usage: provision-eye.sh <node_name> [brain_url] [token]}
HERE=$(CDPATH= cd "$(dirname "$0")" && pwd)
LOCAL_CONFIG=${CYCLOPS_LOCAL_CONFIG:-$HOME/.config/cyclops/config.toml}
LOCAL_CONFIG_HELPER="${HERE}/../../../ops/deploy/local_config.py"

# Preserve explicit environment overrides while loading private local defaults.
ENV_BRAIN=${BRAIN-}
ENV_BRAIN_SSH=${BRAIN_SSH-}
ENV_TOKEN=${CYCLOPS_ENROLL_TOKEN-}
ENV_PUB=${EYE_SSH_PUB-}
if [ -f "$LOCAL_CONFIG" ]; then
	eval "$(uv run --project "${HERE}/../../.." python "$LOCAL_CONFIG_HELPER" shell --config "$LOCAL_CONFIG")"
	NAME=$(uv run --project "${HERE}/../../.." python "$LOCAL_CONFIG_HELPER" name "$NAME" --config "$LOCAL_CONFIG")
fi
[ -z "$ENV_BRAIN" ] || BRAIN=$ENV_BRAIN
[ -z "$ENV_BRAIN_SSH" ] || BRAIN_SSH=$ENV_BRAIN_SSH
[ -z "$ENV_TOKEN" ] || CYCLOPS_ENROLL_TOKEN=$ENV_TOKEN
[ -z "$ENV_PUB" ] || EYE_SSH_PUB=$ENV_PUB

BRAIN=${2:-${BRAIN:-http://cyclops.local:8080}}
TOKEN=${3:-${CYCLOPS_ENROLL_TOKEN:-}}
BRAIN_SSH=${BRAIN_SSH:-admin@cyclops}

if [ -z "$TOKEN" ]; then
	TOKEN=$(ssh -o ConnectTimeout=8 "$BRAIN_SSH" \
		'sed -n "s/^enroll_token *= *\"\(.*\)\"/\1/p" /opt/cyclops/config.toml')
fi
[ -n "$TOKEN" ] || { echo "could not obtain enroll token" >&2; exit 1; }

adb wait-for-device
adb shell "mkdir -p /oem/etc && printf '%s\n' \
	'node_name=$NAME' \
	'enroll_token=$TOKEN' \
	'cyclops_url=$BRAIN' \
	'advertise_host=' \
	'camera_id=0' \
	'iq_dir=/oem/usr/share/iqfiles' \
	'rtsp_port=8554' \
	'control_port=8800' \
	'heartbeat_seconds=15' \
	'thermal_poll_seconds=5' \
	'reboot_after_unreachable_seconds=65535' \
	> /oem/etc/cyclops-eye.conf && chmod 600 /oem/etc/cyclops-eye.conf"
echo "[provision] wrote /oem/etc/cyclops-eye.conf for $NAME"

# Optional: install the admin SSH public key (root's home is /root).
PUB=${EYE_SSH_PUB:-$HOME/.ssh/cyclops_eye.pub}
if [ -f "$PUB" ]; then
	adb push "$PUB" /tmp/eye.pub >/dev/null
	adb shell 'chown root:root /root /root/.ssh 2>/dev/null || true; mkdir -p /root/.ssh; chmod 700 /root/.ssh; cat /tmp/eye.pub >> /root/.ssh/authorized_keys; sort -u /root/.ssh/authorized_keys -o /root/.ssh/authorized_keys; chmod 600 /root/.ssh/authorized_keys; rm -f /tmp/eye.pub'
	echo "[provision] installed admin SSH key"
fi

echo "[provision] rebooting $NAME"
adb shell reboot

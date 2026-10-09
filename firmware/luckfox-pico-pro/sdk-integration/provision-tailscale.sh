#!/bin/sh
# Onboard a Luckfox Cyclops eye to the tailnet over ADB.
#
#   provision-tailscale.sh <node_name> [authkey]
#
# - installs the Tailscale static arm binaries into /usr/bin (rootfs)
# - installs /etc/init.d/S98tailscale so tailscaled starts at boot
# - joins the tailnet once; the node identity then persists in
#   /var/lib/tailscale, so the auth key is not needed again
#
# The board must have internet (Ethernet to the router) for the first join.
#
# The auth key is a SECRET. Pass it as arg 2, via $TS_AUTHKEY, or put it in
# ~/.config/cyclops/tailscale.authkey. It is never written into the repo.
set -eu

NAME=${1:?usage: provision-tailscale.sh <node_name> [authkey]}
KEY=${2:-${TS_AUTHKEY:-}}
if [ -z "${KEY:-}" ]; then
	KF="$HOME/.config/cyclops/tailscale.authkey"
	[ -f "$KF" ] && KEY=$(cat "$KF")
fi
[ -n "${KEY:-}" ] || {
	echo "no Tailscale auth key (arg2, \$TS_AUTHKEY, or $HOME/.config/cyclops/tailscale.authkey)" >&2
	exit 1
}

TS_VERSION=${TS_VERSION:-1.104.1}
PKG="tailscale_${TS_VERSION}_arm"
URL="https://pkgs.tailscale.com/stable/${PKG}.tgz"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOCK=/var/run/tailscale/tailscaled.sock

adb wait-for-device

echo "[ts] connectivity check on the board"
adb shell 'ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 || { echo "board has no internet - connect Ethernet"; exit 1; }'

echo "[ts] installing Tailscale ${TS_VERSION} into /usr/bin"
adb shell "cd /usr/bin && wget -qO- '${URL}' | gunzip -c | tar xf - --strip-components=1 ${PKG}/tailscale ${PKG}/tailscaled && chmod 755 tailscale tailscaled && ./tailscale version | head -1"

echo "[ts] installing boot script /etc/init.d/S98tailscale"
adb push "${HERE}/S98tailscale" /etc/init.d/S98tailscale >/dev/null
adb shell 'chmod 755 /etc/init.d/S98tailscale'

echo "[ts] starting tailscaled"
adb shell '/etc/init.d/S98tailscale start; sleep 5'

# Hand the key to the board via a temp file so it stays off the adb command line.
tmp=$(mktemp 2>/dev/null || echo /tmp/ts_authkey.$$); printf '%s' "$KEY" > "$tmp"
adb push "$tmp" /tmp/ts_authkey >/dev/null; rm -f "$tmp"
echo "[ts] joining the tailnet as ${NAME}"
adb shell "/usr/bin/tailscale --socket=${SOCK} up --authkey=\$(cat /tmp/ts_authkey) --hostname=${NAME} --accept-dns=false --timeout=45s; rm -f /tmp/ts_authkey" || true
adb shell "/usr/bin/tailscale --socket=${SOCK} status | head -3"

cat <<EOF

[ts] done. If the node reports "not yet approved by tailnet admin", approve it
     at https://login.tailscale.com/admin/machines (or mint the key
     pre-authorized). Confirm inbound from the brain or this Mac:
       tailscale ping ${NAME} ;  nc -z \$(tailscale ip -4 ${NAME}) 8554
EOF

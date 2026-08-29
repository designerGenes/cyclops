#!/usr/bin/env bash
# Make a freshly-flashed SD card boot straight into a Cyclops eye.
#
# WORKFLOW: flash Raspberry Pi OS Lite 64-bit (Trixie) with Imager as
# usual (no need to configure anything in Imager). Re-insert the card so
# the boot partition mounts, then run this. It drops the cloud-init files
# and a self-contained payload onto the boot partition. Boot the Pi and
# it joins the tailnet and registers itself — no keyboard, no monitor.
#
#   deploy/make_eye_sdcard.sh --name front-door \
#       --ssh-pubkey ~/.ssh/id_ed25519.pub \
#       --wifi-ssid "MyNet" --wifi-pass "secret" --wifi-country US \
#       --cyclops-url http://cyclops:8080 \
#       --token <enroll-token> \
#       [--boot /Volumes/bootfs] [--user pi] [--timezone America/New_York] \
#       [--ts-authkey tskey-auth-... | --ts-mint] [--ts-tag tag:cyclops-eye]
#
# Tailscale options:
#   --ts-authkey   use a key you already minted
#   --ts-mint      mint a fresh one-off key now (needs TS_OAUTH_CLIENT_ID
#                  / TS_OAUTH_CLIENT_SECRET in the environment)
#   (omit both to skip Tailscale and rely on LAN/mDNS)
source "$(dirname "$0")/lib.sh"

NAME=""; PUBKEY=""; SSID=""; WPASS=""; COUNTRY=""; CURL="http://cyclops:8080"
BOOT=""; USER_="pi"; TZ_="Etc/UTC"; TS_AUTHKEY=""; TS_MINT=0; TS_TAG="tag:cyclops-eye"
while [ $# -gt 0 ]; do case "$1" in
  --name) NAME="$2"; shift 2;;
  --ssh-pubkey) PUBKEY="$2"; shift 2;;
  --wifi-ssid) SSID="$2"; shift 2;;
  --wifi-pass) WPASS="$2"; shift 2;;
  --wifi-country) COUNTRY="$2"; shift 2;;
  --cyclops-url) CURL="$2"; shift 2;;
  --token) ENROLL_TOKEN="$2"; shift 2;;
  --boot) BOOT="$2"; shift 2;;
  --user) USER_="$2"; shift 2;;
  --timezone) TZ_="$2"; shift 2;;
  --ts-authkey) TS_AUTHKEY="$2"; shift 2;;
  --ts-mint) TS_MINT=1; shift;;
  --ts-tag) TS_TAG="$2"; shift 2;;
  *) die "unknown arg: $1";;
esac; done

: "${NAME:?--name required}"; : "${PUBKEY:?--ssh-pubkey required}"
: "${SSID:?--wifi-ssid required}"; : "${WPASS:?--wifi-pass required}"
: "${COUNTRY:?--wifi-country required (ISO 3166, e.g. US/GB)}"
ENROLL_TOKEN="${ENROLL_TOKEN:-${CYCLOPS_ENROLL_TOKEN:-}}"
: "${ENROLL_TOKEN:?set --token or CYCLOPS_ENROLL_TOKEN (must match server config.toml)}"
[ -f "$PUBKEY" ] || die "ssh public key not found: $PUBKEY"
echo "$NAME" | grep -Eq '^[a-zA-Z0-9-]{1,40}$' || die "name must be a valid hostname [a-zA-Z0-9-]"

# Locate the boot partition (FAT32). On macOS it mounts at /Volumes/bootfs.
if [ -z "$BOOT" ]; then
  for cand in /Volumes/bootfs /Volumes/boot /boot/firmware; do
    [ -f "$cand/config.txt" ] && BOOT="$cand" && break
  done
fi
[ -n "$BOOT" ] || die "could not find the boot partition. Pass --boot /path/to/bootfs"
[ -f "$BOOT/config.txt" ] || die "$BOOT has no config.txt — that's not a Pi boot partition. Refusing."
log "using boot partition: $BOOT"

PUBKEY_LINE="$(tr -d '\n' < "$PUBKEY")"

# Optionally mint a fresh one-off Tailscale auth key right now.
if [ "$TS_MINT" = 1 ]; then
  log "minting a one-off Tailscale auth key (tag ${TS_TAG})"
  TS_AUTHKEY="$("$(dirname "$0")/mint_tailscale_key.sh" --tag "$TS_TAG" --desc "cyclops eye $NAME")" \
    || die "failed to mint auth key"
fi

render() {  # render <template> with the placeholders below
  sed -e "s|__NODE_NAME__|$NAME|g" \
      -e "s|__SSH_USER__|$USER_|g" \
      -e "s|__TIMEZONE__|$TZ_|g" \
      -e "s|__WIFI_SSID__|$SSID|g" \
      -e "s|__WIFI_PASSWORD__|$WPASS|g" \
      -e "s|__WIFI_COUNTRY__|$COUNTRY|g" \
      "$1"
}

log "writing cloud-init files to boot partition"
render "$REPO_ROOT/provision/sd/meta-data.tmpl"       > "$BOOT/meta-data"
render "$REPO_ROOT/provision/sd/network-config.tmpl"  > "$BOOT/network-config"
# user-data needs the pubkey injected separately (it contains slashes/+)
render "$REPO_ROOT/provision/sd/user-data.tmpl" \
  | awk -v k="$PUBKEY_LINE" '{gsub(/__SSH_PUBKEY__/,k)}1' > "$BOOT/user-data"

log "writing self-contained payload to $BOOT/cyclops/"
PAY="$BOOT/cyclops"
rm -rf "$PAY"; mkdir -p "$PAY/repo"
# the agent + installer + provisioning files the device needs at boot
cp -R "$REPO_ROOT/node" "$REPO_ROOT/provision" "$PAY/repo/"
find "$PAY/repo" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
cp "$REPO_ROOT/provision/sd/firstboot.sh" "$PAY/firstboot.sh"
cat > "$PAY/eye.env" <<ENV
NODE_NAME="$NAME"
CYCLOPS_URL="$CURL"
ENROLL_TOKEN="$ENROLL_TOKEN"
TS_TAGS="${TS_AUTHKEY:+$TS_TAG}"
ENV
chmod 600 "$PAY/eye.env"
if [ -n "$TS_AUTHKEY" ]; then
  printf '%s' "$TS_AUTHKEY" > "$PAY/tailscale.authkey"
  chmod 600 "$PAY/tailscale.authkey"
  log "baked one-off Tailscale auth key (the device shreds it after joining)"
else
  warn "no Tailscale key baked in. The eye will use LAN/mDNS (${NAME}.local)."
fi

# Compatibility for older cards that still invoke a boot-partition
# first-boot script instead of cloud-init runcmd.
log "writing legacy first-boot compatibility wrapper"
cat > "$BOOT/first_boot_setup.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
PAYLOAD=/boot/firmware/cyclops
[ -d "$PAYLOAD" ] || PAYLOAD=/boot/cyclops
exec bash "$PAYLOAD/firstboot.sh"
SH
chmod +x "$BOOT/first_boot_setup.sh"

sync
log "SD card ready. Eject it, boot the Pi, and watch ${CURL}/stream"
echo
echo "  First boot does: connect WiFi -> join tailnet -> install camnode"
echo "  -> reboot once for the camera overlay -> register. Allow ~3-5 min."
echo "  If you did NOT use a pre-authorized key, approve the device in the"
echo "  Tailscale admin console when it appears (the only manual step)."
echo "  First-boot log on the device: /var/log/cyclops-firstboot.log"

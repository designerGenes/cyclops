# Shared helpers for Cyclops deploy scripts. Sourced, not executed.
# shellcheck shell=bash
set -euo pipefail

c_red=$'\033[31m'; c_grn=$'\033[32m'; c_yel=$'\033[33m'; c_dim=$'\033[2m'; c_off=$'\033[0m'
log()  { printf '%s==>%s %s\n' "$c_grn" "$c_off" "$*" >&2; }
warn() { printf '%s!! %s%s\n' "$c_yel" "$*" "$c_off" >&2; }
die()  { printf '%sxx %s%s\n' "$c_red" "$*" "$c_off" >&2; exit 1; }
step() { printf '%s   %s%s\n' "$c_dim" "$*" "$c_off" >&2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# SSH/SCP wrappers. Always key-based, never prompt for a password, and
# don't choke on a re-flashed host reusing an IP (changed host key).
SSH_USER="${SSH_USER:-pi}"
ssh_opts() {
  printf '%s' \
    "-i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new " \
    "-o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
}
rsh()  { ssh $(ssh_opts) "${SSH_USER}@${TARGET_IP}" "$@"; }
rcp()  { scp $(ssh_opts) -q "$@"; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

# Wait until SSH answers again (used after a remote reboot).
wait_for_ssh() {
  local tries="${1:-60}"
  step "waiting for ${TARGET_IP} to come back up..."
  for _ in $(seq 1 "$tries"); do
    if rsh true 2>/dev/null; then log "host is back"; return 0; fi
    sleep 5
  done
  die "host did not come back within $((tries * 5))s"
}

# JSON field extractor that works whether the Mac has jq or just python3.
json_get() {  # json_get '<json>' '<dotted.path>'
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$1" | jq -r ".$2"
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$1" | python3 -c 'import sys,json
d=json.load(sys.stdin)
for k in sys.argv[1].split("."):
    d=d.get(k) if isinstance(d,dict) else None
print(d if d is not None else "")' "$2"
  else
    die "need either jq or python3 to parse JSON"
  fi
}

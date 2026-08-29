#!/usr/bin/env bash
# Mint a fresh, single-use, pre-authorized, tagged Tailscale auth key
# using an OAuth client. Prints the key (tskey-auth-...) to stdout.
#
#   deploy/mint_tailscale_key.sh [--tag tag:cyclops-eye] [--desc "..."] \
#                                [--reusable] [--expiry-seconds 3600]
#
# Requires env (from your Tailscale admin console -> Trust credentials):
#   TS_OAUTH_CLIENT_ID, TS_OAUTH_CLIENT_SECRET
#
# One-time setup in the Tailscale admin console:
#   1. Create an OAuth client with the `auth_keys` (Keys write) scope.
#   2. Give it the tag you pass here (e.g. tag:cyclops-eye); that tag
#      must exist as a tagOwner in your ACL. Keys minted via OAuth MUST
#      be tagged — that's a Tailscale requirement, not a choice.
source "$(dirname "$0")/lib.sh" 2>/dev/null || { set -euo pipefail; json_get(){ :; }; }

TAG="tag:cyclops-eye"; DESC="cyclops eye (one-off)"; REUSABLE=false; EXPIRY=3600
while [ $# -gt 0 ]; do case "$1" in
  --tag) TAG="$2"; shift 2;;
  --desc) DESC="$2"; shift 2;;
  --reusable) REUSABLE=true; shift;;
  --expiry-seconds) EXPIRY="$2"; shift 2;;
  *) echo "unknown arg: $1" >&2; exit 1;;
esac; done

: "${TS_OAUTH_CLIENT_ID:?set TS_OAUTH_CLIENT_ID}"
: "${TS_OAUTH_CLIENT_SECRET:?set TS_OAUTH_CLIENT_SECRET}"
command -v curl >/dev/null || { echo "curl required" >&2; exit 1; }

token_json=$(curl -fsSL -u "${TS_OAUTH_CLIENT_ID}:${TS_OAUTH_CLIENT_SECRET}" \
  -d 'grant_type=client_credentials' \
  https://api.tailscale.com/api/v2/oauth/token) || { echo "OAuth token request failed" >&2; exit 1; }
access_token=$(json_get "$token_json" access_token)
[ -n "$access_token" ] || { echo "no access_token in OAuth response" >&2; exit 1; }

key_json=$(curl -fsSL -H "Authorization: Bearer ${access_token}" \
  -H 'Content-Type: application/json' \
  https://api.tailscale.com/api/v2/tailnet/-/keys \
  --data-binary @- <<JSON
{
  "capabilities": { "devices": { "create": {
    "reusable": ${REUSABLE},
    "ephemeral": false,
    "preauthorized": true,
    "tags": ["${TAG}"]
  } } },
  "expirySeconds": ${EXPIRY},
  "description": "${DESC}"
}
JSON
) || { echo "auth key creation failed" >&2; exit 1; }

key=$(json_get "$key_json" key)
[ -n "$key" ] || { echo "no key in response: $key_json" >&2; exit 1; }
printf '%s\n' "$key"

#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  printf 'Usage: %s <repo-path> <service-name>\n' "$0"
  exit 1
fi

REPO_PATH="$1"
SERVICE_NAME="$2"

cd "${REPO_PATH}"
git pull --ff-only
uv sync --frozen
if [ -f "${REPO_PATH}/apps/coordinator-web/package.json" ] && [ "${SERVICE_NAME}" = "cyclops-coordinator" ]; then
  pnpm --dir "${REPO_PATH}/apps/coordinator-web" build
fi
systemctl restart "${SERVICE_NAME}"
printf 'Updated %s from git at %s\n' "${SERVICE_NAME}" "${REPO_PATH}"

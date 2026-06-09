#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  printf 'Usage: %s <release-tarball> <user@host>\n' "$0"
  exit 1
fi

RELEASE_TARBALL="$1"
TARGET="$2"
VERSION="$(basename "${RELEASE_TARBALL}" .tar.gz | sed 's/^cyclops-//')"
REMOTE_RELEASE_DIR="/opt/cyclops/releases/cyclops-${VERSION}"

scp -o BatchMode=yes -o StrictHostKeyChecking=no "${RELEASE_TARBALL}" "${TARGET}:/tmp/cyclops-${VERSION}.tar.gz"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "${TARGET}" "mkdir -p /opt/cyclops/releases /etc/cyclops && tar -xzf /tmp/cyclops-${VERSION}.tar.gz -C /opt/cyclops/releases && ln -sfn ${REMOTE_RELEASE_DIR} /opt/cyclops/current && cd /opt/cyclops/current && UV_BIN=\$(command -v uv || true) && if [ -z \"\${UV_BIN}\" ] && [ -x /home/jadennation/.local/bin/uv ]; then UV_BIN=/home/jadennation/.local/bin/uv; fi && if [ -z \"\${UV_BIN}\" ]; then printf 'uv not found on remote host\n' >&2; exit 1; fi && \"\${UV_BIN}\" sync --frozen && if [ ! -f /etc/systemd/system/cyclops-coordinator.service ]; then sudo -n cp /opt/cyclops/current/ops/systemd/cyclops-coordinator.service /etc/systemd/system/cyclops-coordinator.service; fi && sudo -n systemctl daemon-reload && sudo -n systemctl enable cyclops-coordinator.service && sudo -n systemctl restart cyclops-coordinator.service"

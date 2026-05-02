#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadennation/DEV/01_active_projects/cyclops"
WEB_DIR="${PROJECT_ROOT}/apps/coordinator-web"
COORD_STATIC_DIR="${PROJECT_ROOT}/apps/coordinator-api/src/cyclops_coordinator/static"
DIST_ROOT="${PROJECT_ROOT}/dist/releases"
BUILD_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_SHA="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || printf 'nogit')"
VERSION="${BUILD_TIMESTAMP}-${GIT_SHA}"
STAGING_DIR="${DIST_ROOT}/cyclops-${VERSION}"

rm -rf "${STAGING_DIR}"
mkdir -p "${DIST_ROOT}" "${STAGING_DIR}"

pnpm --dir "${WEB_DIR}" build

rm -rf "${COORD_STATIC_DIR}/assets" "${COORD_STATIC_DIR}/index.html"
mkdir -p "${COORD_STATIC_DIR}"
cp -R "${WEB_DIR}/dist/assets" "${COORD_STATIC_DIR}/assets"
cp "${WEB_DIR}/dist/index.html" "${COORD_STATIC_DIR}/index.html"

cp -R "${PROJECT_ROOT}/apps" "${STAGING_DIR}/apps"
cp -R "${PROJECT_ROOT}/packages" "${STAGING_DIR}/packages"
cp -R "${PROJECT_ROOT}/config" "${STAGING_DIR}/config"
cp -R "${PROJECT_ROOT}/ops" "${STAGING_DIR}/ops"
cp -R "${PROJECT_ROOT}/docs" "${STAGING_DIR}/docs"
cp "${PROJECT_ROOT}/README.md" "${PROJECT_ROOT}/pyproject.toml" "${PROJECT_ROOT}/package.json" "${PROJECT_ROOT}/pnpm-workspace.yaml" "${PROJECT_ROOT}/.nvmrc" "${PROJECT_ROOT}/.python-version" "${STAGING_DIR}/"
if [ -f "${PROJECT_ROOT}/uv.lock" ]; then cp "${PROJECT_ROOT}/uv.lock" "${STAGING_DIR}/"; fi
if [ -f "${PROJECT_ROOT}/pnpm-lock.yaml" ]; then cp "${PROJECT_ROOT}/pnpm-lock.yaml" "${STAGING_DIR}/"; fi

cat > "${STAGING_DIR}/version-manifest.json" <<EOF
{
  "version": "${VERSION}",
  "git_sha": "${GIT_SHA}",
  "build_timestamp": "${BUILD_TIMESTAMP}"
}
EOF

tar -czf "${DIST_ROOT}/cyclops-${VERSION}.tar.gz" -C "${DIST_ROOT}" "cyclops-${VERSION}"
printf '%s\n' "Created release: ${DIST_ROOT}/cyclops-${VERSION}.tar.gz"

#!/bin/sh
# Build a Cyclops update.img for the Luckfox Pico Pro/Max using the official
# SDK inside Docker (x86_64 emulated on Apple Silicon).
#
#   make-image.sh <host-output-dir> [sdk-volume] [firmware-dir]
#
# Prerequisites (one-time, see RUNBOOK.md): the Docker image
# `cyclops/luckfox-sdk-builder:ubuntu22` and the SDK volume with the
# Pro/Max SPI-NAND Buildroot board selected and the jobserver/wifi patches
# applied.
set -eu

OUT=${1:?usage: make-image.sh <host-output-dir> [sdk-volume] [firmware-dir]}
VOL=${2:-luckfox-sdk-rv1106}
FW=${3:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
IMG=cyclops/luckfox-sdk-builder:ubuntu22

[ -d "$FW/src" ] || { echo "not a firmware dir: $FW" >&2; exit 1; }
mkdir -p "$OUT"

echo "[make-image] staging Cyclops app + launcher into $VOL"
docker run --rm --platform linux/amd64 -v "$VOL:/sdk" -v "$FW:/fw:ro" "$IMG" bash -lc '
set -e
APP=/sdk/project/app/cyclops_eye
rm -rf "$APP"; mkdir -p "$APP/cyclops/src" "$APP/cyclops/include" "$APP/cyclops/config"
cp -a /fw/src/. "$APP/cyclops/src/"
cp -a /fw/include/. "$APP/cyclops/include/"
cp -a /fw/config/. "$APP/cyclops/config/"
cp /fw/sdk-integration/app-Makefile "$APP/Makefile"
cp /fw/sdk-integration/RkLunch.sh /sdk/project/app/rkipc/rkipc/src/rv1106_ipc/RkLunch.sh
'

echo "[make-image] building app + firmware (incremental; minutes)"
docker run --rm --platform linux/amd64 -v "$VOL:/sdk" "$IMG" bash -lc 'cd /sdk && ./build.sh app && ./build.sh firmware'

echo "[make-image] extracting image"
docker run --rm -v "$VOL:/sdk" -v "$OUT:/out" "$IMG" bash -lc 'cp /sdk/output/image/update.img /out/cyclops-update.img'

echo "[make-image] wrote $OUT/cyclops-update.img"

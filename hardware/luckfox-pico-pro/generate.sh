#!/usr/bin/env bash
# Regenerate the LuckFox Pico Pro enclosure in Blender from the parametric
# geometry model, then verify the exported STLs are watertight.
#
# Usage:
#   hardware/luckfox-pico-pro/generate.sh
#
# Produces, under hardware/luckfox-pico-pro/out/:
#   luckfox_pico_pro_enclosure.blend   Blender project (open for refinement)
#   stl/luckfox_enclosure_*.stl        one printable STL per part
#   preview/luckfox_enclosure_*.png    render previews
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$SCRIPT_DIR/out"

BLENDER="${BLENDER:-blender}"

echo "[generate] building enclosure with Blender..."
"$BLENDER" --background --python "$SCRIPT_DIR/generate_case.py" -- --out "$OUT_DIR"

echo "[generate] verifying STL integrity..."
"$BLENDER" --background --python "$SCRIPT_DIR/verify_stls.py" -- --stl "$OUT_DIR/stl"

echo "[generate] done. Open $OUT_DIR/luckfox_pico_pro_enclosure.blend in Blender."
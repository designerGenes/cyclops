#!/bin/sh
# Stage the Cyclops eye integration into a Luckfox SDK checkout and build.
#
#   apply.sh /path/to/luckfox-pico [updateimg]
#
# Without the second argument it runs an incremental `./build.sh app` only,
# which is enough to cross-compile and install the daemon while iterating.
# With `updateimg` (or on the second run) it repackages the full image.
set -eu

SDK=${1:?usage: apply.sh /path/to/luckfox-pico [updateimg]}
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
FW=$(CDPATH= cd -- "$HERE/.." && pwd)
DO_IMAGE=${2:-}

APP="$SDK/project/app/cyclops_eye"
RKIPC_LUNCH="$SDK/project/app/rkipc/rkipc/src/rv1106_ipc/RkLunch.sh"

[ -d "$SDK/project/app" ] || { echo "not a Luckfox SDK: $SDK" >&2; exit 1; }

rm -rf "$APP"
mkdir -p "$APP/cyclops/src" "$APP/cyclops/include" "$APP/cyclops/config"
cp -a "$FW/src/." "$APP/cyclops/src/"
cp -a "$FW/include/." "$APP/cyclops/include/"
cp -a "$FW/config/." "$APP/cyclops/config/"
cp "$HERE/app-Makefile" "$APP/Makefile"

# Replace the stock camera-owner launcher (idempotent; keep one backup).
if [ -f "$RKIPC_LUNCH" ] && [ ! -f "$RKIPC_LUNCH.vendor" ]; then
	cp "$RKIPC_LUNCH" "$RKIPC_LUNCH.vendor"
fi
cp "$HERE/RkLunch.sh" "$RKIPC_LUNCH"

echo "staged Cyclops app; source under $APP/cyclops"

cd "$SDK"
./build.sh app
if [ "$DO_IMAGE" = "updateimg" ]; then
	./build.sh updateimg
	echo "image: $SDK/output/image/update.img"
fi

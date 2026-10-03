#!/bin/sh
# Build and stage an install tree. It never opens a network connection, writes
# to a connected LuckFox, replaces rkipc, or enables the init script.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
STAGE=
SDK_ROOT=${LUCKFOX_SDK_ROOT:-}
SET_VERSION=

usage() {
  echo "usage: $0 --stage-dir ABSOLUTE_PATH [--sdk-root PATH] [--set-version X.Y.Z|--bump-version]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --stage-dir) STAGE=${2:-}; shift 2 ;;
    --sdk-root) SDK_ROOT=${2:-}; shift 2 ;;
    --set-version) SET_VERSION=${2:-}; shift 2 ;;
    --bump-version)
      CURRENT=$(sed -n 's/^project(cyclops_eye_luckfox VERSION \([0-9][0-9.]*\).*/\1/p' "$ROOT/CMakeLists.txt")
      MAJOR=${CURRENT%%.*}
      REST=${CURRENT#*.}
      MINOR=${REST%%.*}
      PATCH=${REST##*.}
      SET_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
      shift
      ;;
    *) usage; exit 64 ;;
  esac
done

[ -n "$STAGE" ] && [ "${STAGE#/*}" != "$STAGE" ] || { usage; exit 64; }
[ -n "$SDK_ROOT" ] || { echo "--sdk-root (or LUCKFOX_SDK_ROOT) is required" >&2; exit 64; }

if [ -n "$SET_VERSION" ]; then
  case "$SET_VERSION" in
    *[!0-9.]*|.*|*.) echo "version must be X.Y.Z" >&2; exit 64 ;;
  esac
  sed -i.bak "s/project(cyclops_eye_luckfox VERSION [0-9.]*/project(cyclops_eye_luckfox VERSION $SET_VERSION/" "$ROOT/CMakeLists.txt"
  rm -f "$ROOT/CMakeLists.txt.bak"
fi

cmake -S "$ROOT" -B "$ROOT/build" -DCYCLOPS_EYE_WITH_LUCKFOX_SDK=ON -DLUCKFOX_SDK_ROOT="$SDK_ROOT"
cmake --build "$ROOT/build"
cmake --install "$ROOT/build" --prefix "$STAGE"
install -D -m 0600 "$ROOT/config/cyclops-eye.conf.example" "$STAGE/etc/cyclops-eye.conf.example"
install -D -m 0755 "$ROOT/system/S50cyclops-eye" "$STAGE/etc/init.d/S50cyclops-eye"
echo "Staged review artifact at $STAGE; no device was changed."

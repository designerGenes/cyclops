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
cp /fw/sdk-integration/RkLunch-stop.sh /sdk/project/app/rkipc/rkipc/src/rv1106_ipc/RkLunch-stop.sh
'

echo "[make-image] enabling the RV1106 hardware watchdog in the kernel"
docker run --rm --platform linux/amd64 -v "$VOL:/sdk" "$IMG" bash -lc '
set -e
DTS=/sdk/sysdrv/source/kernel/arch/arm/boot/dts/rv1106g-luckfox-pico-pro-max.dts
if ! grep -q "&wdt" "$DTS"; then
	printf "\n&wdt {\n\tstatus = \"okay\";\n};\n" >> "$DTS"
fi
DEF=/sdk/sysdrv/source/kernel/arch/arm/configs/luckfox_rv1106_linux_defconfig
if grep -q "CONFIG_WATCHDOG_NOWAYOUT" "$DEF"; then
	sed -i "s/.*CONFIG_WATCHDOG_NOWAYOUT.*/CONFIG_WATCHDOG_NOWAYOUT=y/" "$DEF"
else
	echo "CONFIG_WATCHDOG_NOWAYOUT=y" >> "$DEF"
fi
# incremental builds reuse objs_kernel/.config, so patch it too
CFG=/sdk/sysdrv/source/objs_kernel/.config
if [ -f "$CFG" ]; then
	if grep -q "CONFIG_WATCHDOG_NOWAYOUT" "$CFG"; then
		sed -i "s/.*CONFIG_WATCHDOG_NOWAYOUT.*/CONFIG_WATCHDOG_NOWAYOUT=y/" "$CFG"
	else
		echo "CONFIG_WATCHDOG_NOWAYOUT=y" >> "$CFG"
	fi
fi
echo "  wdt override: $(grep -c "&wdt" "$DTS")"
echo "  $(grep NOWAYOUT "$DEF")"
'

echo "[make-image] staging /etc/TZ + S98tailscale into the rootfs overlay"
docker run --rm --platform linux/amd64 -v "$VOL:/sdk" -v "$FW:/fw:ro" "$IMG" bash -lc '
set -e
OV=/sdk/project/cfg/BoardConfig_IPC/overlay/overlay-luckfox-config
mkdir -p "$OV/etc/init.d"
printf "CST6CDT,M3.2.0,M11.1.0\n" > "$OV/etc/TZ"
cp /fw/sdk-integration/S98tailscale "$OV/etc/init.d/S98tailscale"
chmod 755 "$OV/etc/init.d/S98tailscale"
echo "  staged $OV/etc/TZ and $OV/etc/init.d/S98tailscale"
'

echo "[make-image] building app + firmware (incremental; minutes)"
docker run --rm --platform linux/amd64 -v "$VOL:/sdk" "$IMG" bash -lc 'cd /sdk && ./build.sh kernel && ./build.sh app && ./build.sh firmware'

echo "[make-image] extracting image"
docker run --rm -v "$VOL:/sdk" -v "$OUT:/out" "$IMG" bash -lc 'cp /sdk/output/image/update.img /out/cyclops-update.img'

echo "[make-image] wrote $OUT/cyclops-update.img"

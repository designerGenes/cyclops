#!/bin/sh
# Live progress monitor for the Luckfox SDK build.
#
#   watch-build.sh <build-log> [volume] [interval-seconds] [iterations]
#
# Prints one compact status line per interval so forward motion (or a stall)
# is obvious. Uses rg (grep is unavailable in this environment).

LOG=${1:?usage: watch-build.sh <build-log> [volume] [interval] [iterations]}
VOL=${2:-luckfox-sdk-rv1106}
INTERVAL=${3:-20}
ITERS=${4:-1}

RG=$(command -v rg || echo /opt/homebrew/bin/rg)

phase_of() {
	if "$RG" -q 'New image generated successfully' "$LOG" 2>/dev/null; then
		echo "FINAL:update.img"
	elif "$RG" -q 'build rkipc done|cyclops_eye|Start building app' "$LOG" 2>/dev/null; then
		echo "app"
	elif "$RG" -q 'Start building media|==media==|build_media succeeded' "$LOG" 2>/dev/null; then
		echo "media"
	elif "$RG" -q '^>>>' "$LOG" 2>/dev/null; then
		echo "rootfs"
	elif "$RG" -q 'Start building kernel' "$LOG" 2>/dev/null; then
		echo "kernel"
	elif "$RG" -q 'Start building uboot|build_uboot succeeded' "$LOG" 2>/dev/null; then
		echo "uboot"
	else
		echo "starting"
	fi
}

cur_pkg() { "$RG" '^>>>' "$LOG" 2>/dev/null | tail -1 | sed 's/^>>> //'; }
done_pkgs() { "$RG" -c '^>>> .* Installing to target$' "$LOG" 2>/dev/null || echo 0; }
lines() { wc -l < "$LOG" 2>/dev/null | tr -d ' '; }
img_ready() { docker run --rm -v "$VOL:/sdk" alpine sh -c 'test -f /sdk/output/image/update.img && echo yes || echo no' 2>/dev/null; }

prev_lines=0
i=0
while [ "$i" -lt "$ITERS" ]; do
	i=$((i + 1))
	L=$(lines)
	DL=$((L - prev_lines))
	prev_lines=$L
	[ "$i" -eq 1 ] && DL=0
	echo "$(date +%H:%M:%S) phase=$(phase_of) pkgs_installed=$(done_pkgs) lines=$L (+$DL) update.img=$(img_ready)"
	echo "           now: $(cur_pkg)"
	if [ "$i" -lt "$ITERS" ]; then sleep "$INTERVAL"; fi
done
exit 0

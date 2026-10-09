# Cyclops Luckfox Pico Pro/Max Eye — Runbook

Everything learned bringing up the first pilot. Follow this to add each new
board. The whole software flow is reproducible; the slow part is only the
one-time SDK build.

Node roles: the **brain** is coordinator (`cyclops.local:8080` on the LAN).
Each eye is a Luckfox Pico Pro/Max (RV1106, SC3336 camera). Keep the Pi eyes
running; give every Luckfox a unique `node_name`.

---

## 0. Per-board checklist (the fast path once setup is done)

1. Flash `cyclops-update.img` (Section 4).
2. Provision a unique node name (Section 5).
3. Verify it appears in Cyclops and streams (Section 6).

Setup (Sections 1–3) is done once and reused for every board.

---

## 1. Host tooling (one-time)

Needs Docker Desktop (Apple Silicon runs the x86_64 SDK under emulation).

Builder image:

```sh
cat > luckfox-sdk-builder.Dockerfile <<'EOF'
FROM --platform=linux/amd64 ubuntu:22.04
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    git ssh make gcc gcc-multilib g++-multilib module-assistant expect gawk texinfo \
    libssl-dev bison flex fakeroot cmake unzip gperf autoconf device-tree-compiler \
    libncurses5-dev pkg-config bc python-is-python3 passwd openssl openssh-server \
    openssh-client vim file cpio rsync mtd-utils curl subversion && rm -rf /var/lib/apt/lists/*
WORKDIR /sdk
EOF
docker build --platform linux/amd64 -t cyclops/luckfox-sdk-builder:ubuntu22 -f luckfox-sdk-builder.Dockerfile .
```

SDK in a case-sensitive Docker volume (the Linux kernel tree cannot build on the
case-insensitive macOS filesystem):

```sh
docker volume create luckfox-sdk-rv1106
docker run --rm --platform linux/amd64 -v luckfox-sdk-rv1106:/sdk ubuntu:22.04 bash -lc \
  'apt-get update -qq && apt-get install -y -qq git ca-certificates >/dev/null && \
   git clone --depth 1 https://github.com/LuckfoxTECH/luckfox-pico.git /sdk'
```

Rollback image: keep the official vendor
`Luckfox_Pico_Pro_Max_Flash_250607/update.img` (and/or an SDK-built baseline).

Flasher (macOS): **`upgrade_tool` v2.25** (v2.44 segfaults on this Mac):
<https://wiki.luckfox.com/assets/files/upgrade_tool_v2.25_for_mac-be4af178e48d6a55755c118d1d3c2f7e.zip>

---

## 2. Prepare the SDK (one-time)

Select the exact target — **Pro/Max, SPI_NAND, Buildroot**:

```sh
docker run --rm --platform linux/amd64 -v luckfox-sdk-rv1106:/sdk \
  cyclops/luckfox-sdk-builder:ubuntu22 bash -lc 'cd /sdk && printf "4\n1\n0\n" | ./build.sh lunch'
```

Apply the three required patches (these fix real, reproduced failures):

```sh
docker run --rm -v luckfox-sdk-rv1106:/sdk cyclops/luckfox-sdk-builder:ubuntu22 bash -lc '
# 1) GNU make jobserver bug: build Buildroot with no jobserver
sed -i "s#-j\$(SYSDRV_JOBS) -C \$(BUILDROOT_DIR)/\$(BUILDROOT_VER)#-j1 -C \$(BUILDROOT_DIR)/\$(BUILDROOT_VER)#" /sdk/sysdrv/Makefile
# 2) same bug in the media build
printf "\nRK_MEDIA_JOBS:=1\n" >> /sdk/media/Makefile.param
# 3) skip the wifi app (Ethernet eye; its bundled libnl does not build here)
printf "\nexport RK_ENABLE_WIFI=n\n" >> /sdk/.BoardConfig.mk
printf "\nexport RK_ENABLE_WIFI=n\n" >> /sdk/project/cfg/BoardConfig_IPC/BoardConfig-SPI_NAND-Buildroot-RV1106_Luckfox_Pico_Pro_Max-IPC.mk
'
```

> Do **not** `sed -i` the SDK's root `build.sh` — it is a git symlink to
> `project/build.sh`. Editing it in place breaks the script's own path
> resolution. Patch files directly, not the symlink.

---

## 3. One-time full build (slow)

```sh
docker run --rm --platform linux/amd64 -v luckfox-sdk-rv1106:/sdk \
  cyclops/luckfox-sdk-builder:ubuntu22 bash -lc 'cd /sdk && ./build.sh allsave'
```

- Under x86_64 emulation this is the long pole (hours). It produces
  `/sdk/output/image/update.img` (baseline).
- After it completes, the Cyclops image rebuild is incremental and takes
  **minutes** (only `app` + `firmware`).

---

## 4. Build the Cyclops image and flash

```sh
# from the repo:
firmware/luckfox-pico-pro/sdk-integration/make-image.sh "$HOME/cyclops-luckfox"
# -> $HOME/cyclops-luckfox/cyclops-update.img
```

Flash (board must enter MaskROM; no button press needed if it is running):

```sh
adb reboot loader                     # running board -> MaskROM
upgrade_tool LD                       # expect Mode=Maskrom
upgrade_tool UF "$HOME/cyclops-luckfox/cyclops-update.img"
```

If `adb` is unavailable (e.g. won't boot), hold **BOOT** while connecting
USB-C to enter MaskROM.

---

## 5. Provision the eye

```sh
firmware/luckfox-pico-pro/sdk-integration/provision-eye.sh <node_name>
# e.g. ... luckfox-2
```

This writes `/oem/etc/cyclops-eye.conf` (persists across reboots), installs the
admin SSH key, and reboots. It reads the shared enroll token from the brain.

Key config choices (already handled by the script):
- `advertise_host=` empty — the daemon **re-discovers its LAN IP every
  heartbeat**, because this board's DHCP address changes across boots.
- `reboot_after_unreachable_seconds=65535` — avoid an offline reboot loop
  (the parser caps this field at 65535).
- `iq_dir=/oem/usr/share/iqfiles` — the official image's sensor tuning path.

---

## 6. Verify

Local (over USB/ADB):

```sh
adb shell 'cat /sys/class/net/eth0/carrier'          # want 1
adb forward tcp:8554 tcp:8554
ffprobe -v error -rtsp_transport tcp -select_streams v:0 \
  -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 \
  rtsp://127.0.0.1:8554/cam        # H.264 1920x1080
# .../detect                       # H.264 640x360
```

Brain:

```sh
ssh admin@cyclops 'curl -s localhost:8080/api/nodes' | python3 -m json.tool
# expect the new node: online=true stream_ready=true, detect_frame_age small
ssh admin@cyclops 'curl -s localhost:9997/v3/paths/get/cam_<name>'
# expect ready=true and bytesReceived increasing
```

---

## 7. Troubleshooting (the failures we actually hit)

| Symptom | Cause | Fix |
|---|---|---|
| Build dies: `write jobserver: Bad file descriptor` (busybox, freetype, …) | GNU make jobserver vs recursive `make -j` | Section 2 patch #1 (`-j1` buildroot) and #2 (media) |
| Build dies in `wifi_app`: `-lnl-3` / `netlink/genl/genl.h` missing | bundled libnl broken by the jobserver bug | Section 2 patch #3 (`RK_ENABLE_WIFI=n`) |
| Build dies: `find cfg: No such file` / `unset_board_config_all failed` | `sed -i` replaced the `build.sh` symlink | restore `ln -sf ./project/build.sh build.sh` |
| `timeout: curl: not found` / `svn: command not found` | missing tools in builder | builder image now installs `curl subversion` |
| No DHCP, no LAN IP | image's `/etc/network/interfaces` is loopback-only; DHCP comes from `RkLunch.sh` `network_init` | ensure link is up; verify `carrier=1` |
| `eth0 carrier=0` despite switch LED | switch **Extend (Ports 1–2)** mode, or bad cable/port | set switch toggle off; use a non-Extend port or plug straight into the router; swap cable |
| Daemon exits: `invalid configuration on line N` | a numeric field exceeded the 65535 cap (e.g. `86400`) | use <= 65535 |
| Node online but `stream_ready=false` | brain proxy uses node name (unresolvable); daemon reported empty `lan_host` | flash update3+ (re-discovers LAN IP each heartbeat), or set a working `advertise_host` |
| rkipc core dumps in `/userdata/core-*-rkipc` | vendor camera owner crashes in this image | expected; we replace it with `cyclops-eye` via `RkLunch.sh` |

---

## 8. Mental model / gotchas

- The Luckfox is **not** a Raspberry Pi: Rockchip MPP + RKAIQ, Buildroot, UBIFS
  on SPI NAND, SysV init. The Pi eye's Python/picamera2/MediaMTX stack does not
  transfer; the camera path is `rk_aiq_uapi2_sysctl_*` + MPP VI/VENC + `rtsp_demo`.
- Only **one** process may own the camera. Our `RkLunch.sh` starts `cyclops-eye`
  when `/oem/etc/cyclops-eye.conf` exists, else falls back to `rkipc`.
- `/oem` and `/userdata` are writable; the `rootfs` is read-only. Put persistent
  eye config in `/oem/etc/`.
- MaskROM lives in the chip boot ROM — a bad image is always recoverable via
  `upgrade_tool UF` with the vendor `update.img`.
- The board's Ethernet MAC/IP **changes per boot**; don't hard-code the address.
- Secrets: the enroll token is shared by all eyes; never commit it. `.githooks/`
  has a gitleaks pre-commit guard in the repo.

---

## 9. Tailscale (optional: stable address + remote fallback)

The Luckfox kernel has **no TUN** (`# CONFIG_TUN is not set`), so Tailscale runs
in `userspace-networking` mode. Tailscale >= ~1.100 still proxies **inbound TCP**
to the node's local listeners, so the brain can pull `rtsp://<name>:8554` and SSH
works over the tailnet — **no kernel rebuild needed**.

Onboard a board once, over ADB, from the repo:

```sh
# Put the auth key in a file (never commit it; gitleaks guards commits):
install -d -m700 ~/.config/cyclops
printf '%s' 'tskey-auth-...' > ~/.config/cyclops/tailscale.authkey
chmod 600 ~/.config/cyclops/tailscale.authkey

firmware/luckfox-pico-pro/sdk-integration/provision-tailscale.sh camera-02
```

That installs `tailscale`/`tailscaled` into `/usr/bin`, installs
`/etc/init.d/S98tailscale` (starts `tailscaled` at boot), and joins the tailnet
as `<node_name>`. The node identity persists in `/var/lib/tailscale`, so the
auth key is used **only on the first join** — later start/stop needs no key.

- Approve the node at <https://login.tailscale.com/admin/machines> if it is not
  pre-authorized by the key.
- Verify from the brain or this Mac: `tailscale ping <name>` and
  `nc -z "$(tailscale ip -4 <name>)" 8554`.
- Pin the version with `TS_VERSION=<x.y.z>` (default in the script).

Notes / gotchas:

- The binaries and boot script live on the **rootfs**, so a firmware reflash
  wipes them — re-run `provision-tailscale.sh` after a reflash. Baking them into
  the image is a possible follow-up (needs the SDK rootfs overlay path).
- `tailscaled` costs ~30–60 MB RAM on the 180 MB board. It coexists with
  `cyclops-eye` but leaves less headroom.
- The board's tailnet hostname is its Cyclops `node_name` (`camera-02`,
  `frasiercrane`, `martincrane`), matching the brain's node registry.

---

## 10. Hardware watchdog & resilience

The eye must recover from a hang by itself. The RV1106 has a DW watchdog, but
its DT node was disabled and the image exposed no `/dev/watchdog`, so a wedged
board needed a manual power-cycle. That is now fixed:

- **Kernel** — `make-image.sh` appends `&wdt { status = "okay"; };` to the
  Pro/Max DTS and sets `CONFIG_WATCHDOG_NOWAYOUT=y` (the DW driver is already
  built in). It also runs **`./build.sh kernel`** first — **`./build.sh firmware`
  alone only packages and reuses the old kernel**, so a DTS/config change does
  not take effect without it.
- **App** — `cyclops-eye` opens `/dev/watchdog` (30 s timeout) and pets it every
  5 s from the main loop. With NOWAYOUT armed, if the daemon or the kernel hangs
  the board resets itself. Verified by `kill -STOP` on the daemon: the board
  rebooted unaided ~40 s later.
- **Supervisor (`RkLunch.sh`)** — restarts the daemon on exit but **never
  reboots** (the watchdog owns that). It also `export TZ='CST6CDT,M3.2.0,M11.1.0'`
  so the timestamp OSD uses local time without tzdata.
- **Rootfs overlay** — `make-image.sh` bakes `/etc/TZ` and
  `/etc/init.d/S98tailscale` into the rootfs (the board's `RK_POST_OVERLAY`
  includes `overlay-luckfox-config`).

Gotchas we hit:

- **No camera = daemon crash.** A disconnected SC3336 logs
  `sc3336: Unexpected sensor id(000000)`, then `rk_aiq` init faults inside
  `librkaiq.so` (`+0x52f08`, `r0=0`) and the daemon exits `rc=139`. **Reseat the
  CSI ribbon.** The supervisor now retries quietly (no reboot-loop) and the
  watchdog does not fire (the daemon never opened it).
- The same `librkaiq + 0x52f08` fault is what tripped the older random wedges.
- **After a reflash** the node config, `/etc/TZ`, SSH key and Tailscale state are
  wiped — re-run `provision-eye.sh` then `provision-tailscale.sh` (fresh auth
  key), and re-approve the node in the Tailscale console (delete the stale
  entry so the new node keeps the name).

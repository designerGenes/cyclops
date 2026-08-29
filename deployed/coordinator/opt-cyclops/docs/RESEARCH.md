# Verified research notes — June 12, 2026

Sources checked live before this build. These supersede any training-era
knowledge. Re-verify if reading this after ~2026.

## Innomaker CAM-IMX708AF (the exact module specified)
- Sony IMX708, 12MP (4608x2592), PDAF autofocus, HDR to 3MP, 75° DFOV,
  IR-cut filter. Functionally a Raspberry Pi Camera Module 3 clone.
  Ships with BOTH 15-pin and 22-pin FFC cables — the Zero 2 W uses the
  **22-pin (mini) connector**, contacts facing the board.
- Vendor setup (github.com/INNO-MAKER/cam-imx708af, confirmed current):
  in `/boot/firmware/config.txt`:
  - change `camera_auto_detect=1` -> `camera_auto_detect=0`
  - add `dtoverlay=imx708`  (Pi 5 only would need `,cam0`/`,cam1`; the
    Zero 2 W has a single port — no suffix)
  - reboot, verify: `rpicam-hello --list-cameras` -> `imx708 [4608x2592]`
- Why auto-detect fails on clones: probing relies on sensor ID quirks;
  third-party boards intermittently fail it. Explicit overlay is the
  documented vendor path and is deterministic. This was the recurring
  "hung up on outdated docs" failure: old guides say `start_x=1`,
  `gpu_mem=128`, `raspistill`, `/boot/config.txt` — ALL obsolete.

## Current OS / camera stack (Raspberry Pi OS, Debian 13 "Trixie")
- Config file lives at `/boot/firmware/config.txt` (not `/boot/config.txt`).
- CLI tools are `rpicam-hello/-vid/-still` (libcamera-* names are gone;
  rpicam-apps 1.9.x, libcamera v0.5.x as of late 2025).
- Picamera2 remains the Python API; MediaMTX's built-in `rpiCamera`
  source talks to libcamera directly and is the lightest streaming path
  on a Zero 2 W (hardware H.264, no ffmpeg pipe, no V4L2 loopback).
- MediaMTX supports a **secondary stream** from the same sensor
  (`rpiCameraSecondary: true`) with independent resolution/FPS/bitrate —
  we use it as a dedicated low-res AI feed. Force `rtspTransports: [tcp]`
  to avoid H.264 corruption on lossy WiFi. Community-validated stable
  bitrate on Zero 2 W: ~1-1.5 Mbps primary.
- MediaMTX HTTP API (`/v3/config/paths/patch/<name>`) hot-applies
  rpiCamera parameter changes — this is how the thermal governor steps
  quality up/down without restarting the service.

## AI HAT+ on Trixie (changed December 2025 — this is the new part)
- Hailo support returned to Trixie in Dec 2025. The Hailo kernel driver
  was REMOVED from Raspberry Pi kernel builds and is now built via DKMS:
  `sudo apt install dkms` **before** `sudo apt install hailo-all`
  (order matters; forums confirm silent failure otherwise), then reboot
  and verify with `hailortcli fw-control identify`.
- hailo-all provides HailoRT + Python bindings (`hailo_platform`) +
  Tappas post-processing. Reference apps moved to the `hailo-apps`
  GitHub repo (hailo-rpi5-examples is legacy).
- AI HAT+ = Hailo-8L (13 TOPS) or Hailo-8 (26 TOPS). YOLOv8s person
  detection runs >100 FPS — a single NPU services many camera feeds.
  HEF files are per-chip: pick the `h8l` build for the 8L variant.
- PCIe: current firmware auto-enables; force Gen3 with
  `dtparam=pciex1_gen=3` in config.txt if throughput-bound.

## Zero 2 W thermal & power facts used by the governor
- `vcgencmd measure_temp` / `/sys/class/thermal/thermal_zone0/temp`.
- `vcgencmd get_throttled` bitfield: bit0 under-voltage now, bit1 freq
  capped, bit2 throttled, bit3 soft temp limit; bits 16-19 = same,
  "has occurred since boot".
- Firmware throttles hard at 80 C; our governor acts from 63 C so the
  encoder never meets the cliff. Hardware watchdog: `dtparam=watchdog=on`
  + systemd `RuntimeWatchdogSec` reboots a wedged kernel.

## First-boot provisioning on Trixie (changed Nov 24 2025)
- Raspberry Pi OS Trixie images released 24 Nov 2025+ ship **cloud-init**
  and place three files on the FAT32 boot partition: `meta-data`,
  `network-config`, `user-data`. This replaces the legacy `firstrun.sh`.
- `user-data` MUST begin with the literal line `#cloud-config`. It sets
  hostname, users + `ssh_authorized_keys`, `enable_ssh: true` (an
  RPi-specific extension), `ssh_pwauth: false`, and `runcmd`.
- `network-config` is netplan v2 (`renderer: NetworkManager`); set
  `regulatory-domain` to the ISO country code or WiFi may stay down.
- Known breakage: rpi-imager 2.x GUI customization with SSH *public key*
  auth stopped applying on images after ~Dec 4 2025 (rpi-imager issues
  #1320/#1386). Writing the cloud-init files by hand is unaffected and is
  what we do — so the SD path doesn't depend on the buggy GUI flow.
- cloud-init `runcmd` runs once per instance-id; rebooting inside it
  won't re-run it. So firstboot.sh does ALL install work, sets a
  sentinel, then reboots last (only to load the camera overlay).

## Tailscale headless join (verified Jan-Apr 2026 docs)
- Device side: `tailscale up --authkey=tskey-auth-... --hostname=<name>`.
  Pass the key via env/file, never inline in shell history.
- Long-lived static keys are gone (auth keys expire <=90 days, one-off
  keys die on first use). The supported automation is an **OAuth client**
  (scope `auth_keys`) -> POST /api/v2/oauth/token for an access token ->
  POST /api/v2/tailnet/-/keys to mint an auth key.
- OAuth-minted keys MUST carry a tag; the tag must be a tagOwner in the
  ACL and owned by the OAuth client. We use one-off + preauthorized so
  the device joins with zero manual approval and the key can't be reused.

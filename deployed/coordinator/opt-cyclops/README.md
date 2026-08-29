# CYCLOPS — many eyes, one watcher

A resilient multi-camera human-presence detection system.

- **Eyes**: Raspberry Pi Zero 2 W + Innomaker 12MP IMX708 autofocus camera (Camera Module 3 clone)
- **Brain**: Raspberry Pi 5 + AI HAT+ (Hailo-8/8L NPU), running detection + the `/stream` console
- **Network**: shared WiFi + Tailscale (WireGuard transport + identity between nodes)

## Architecture

```
[Zero 2 W "eye"]                          [Pi 5 "Cyclops"]
 MediaMTX (rpiCamera source)               MediaMTX (central)
   /cam     1536x864 H264 (UI feed)  --->    proxies /cam_<name> --> browser (WebRTC/WHEP)
   /detect   640x360 H264 (AI feed)  --->  Detector (Hailo YOLOv8 person) --> SMS/MMS alert
 camnode agent (stdlib Python)             Cyclops API (FastAPI)
   thermal governor / heartbeat              node registry, /stream UI, alert snapshots
   hw+systemd watchdogs
```

Both video streams are encoded **once, in hardware**, on the Zero 2 W
(BCM2710 H.264 encoder). The Pi 5 never re-encodes: the browser gets the
primary stream via WebRTC, and the detector decodes only the cheap 640x360
secondary stream.

## Why not Kubernetes

The Zero 2 W has 512 MB RAM. A k3s agent alone consumes ~250 MB and adds
CPU jitter that starves the video encoder and *raises* heat — the exact
failure mode we're defending against. The same guarantees come cheaper:

| Failure            | Mitigation                                              |
|--------------------|---------------------------------------------------------|
| Process crash      | systemd `Restart=always`, `RestartSec=2`                |
| Agent hang         | systemd `WatchdogSec=30` (sd_notify pings)              |
| Kernel hang        | BCM hardware watchdog (`RuntimeWatchdogSec=15s`)        |
| Overheat           | thermal governor steps stream tiers down with hysteresis|
| Power instability  | `vcgencmd get_throttled` monitored; tier drop on UV     |
| WiFi loss          | NetworkManager autoconnect, wifi powersave off          |
| Total isolation    | agent reboots node after 10 min of unreachable brain    |
| Accidental kill    | services re-enable + restart; node rejoins tailnet      |

## Quick start

### 1. Pi 5 (Cyclops brain) — Raspberry Pi OS **Trixie** 64-bit
```bash
sudo apt update && sudo apt full-upgrade -y && sudo rpi-eeprom-update -a && sudo reboot
# AI HAT+ (Hailo-8/8L). dkms MUST be installed first (driver moved out of kernel on Trixie):
sudo apt install -y dkms && sudo apt install -y hailo-all && sudo reboot
hailortcli fw-control identify        # must print device info
git clone <this repo> ~/cyclops && cd ~/cyclops
sudo scripts/install_server.sh        # MediaMTX + venv + systemd units
# fetch a person-detection model compiled for your NPU (pick ONE):
#   Hailo-8L: yolov8s_h8l.hef    Hailo-8: yolov8s.hef   (Hailo Model Zoo)
sudo cp yolov8s*.hef /opt/cyclops/models/yolov8s.hef
sudo nano /opt/cyclops/config.toml    # enroll token, Twilio creds
sudo systemctl restart cyclops
```
Visit `http://<pi5-tailnet-name>:8080/stream`.

### 2. Add an eye (repeat per camera, ~3 minutes each)
Flash Raspberry Pi OS **Lite 64-bit (Trixie)** with Imager (set hostname,
SSH key, WiFi). Join it to Tailscale, then from your workstation:
```bash
pip install pyinfra
scripts/add_camera.sh <node-host-or-ip> <camera-name>
```
That's it. The node reboots once (config.txt camera overlay), registers
itself with Cyclops, and its tile appears at the bottom of `/stream`.

## Innomaker IMX708 — the part that kept breaking
See `docs/RESEARCH.md` for the verified, current (June 2026) facts. The
short version: it's a CM3 clone, **auto-detect does not reliably probe
clones**, so provisioning sets `camera_auto_detect=0` + `dtoverlay=imx708`
(vendor-confirmed), uses the **22-pin** FFC end on the Zero's mini CSI
port, and verifies with `rpicam-hello --list-cameras`.

## SMS alerts
Configure Twilio in `/opt/cyclops/config.toml`. If `public_media_base`
is set (any public HTTPS host serving `/alerts`), alerts go out as MMS
with the snapshot attached. Otherwise you get an SMS with a tailnet link
to the snapshot (your phone is on the tailnet, so it opens instantly).

## Repo layout
```
provision/   pyinfra deploy for new camera nodes
node/        camnode agent (zero pip dependencies, stdlib only)
server/      Cyclops: FastAPI app, detector, UI, MediaMTX config
scripts/     install_server.sh, add_camera.sh
docs/        RESEARCH.md — verified hardware/software facts + dates
```

## Deployment from your MacBook (SSH)

Everything below needs only `ssh` and `rsync` on the Mac (plus `curl`/
`python3` for the Tailscale minting helper). Each script takes an IP and
an SSH key path and does the rest.

### Brain (Pi 5)
```bash
deploy/bootstrap_cyclops.sh --ip <pi5-ip> --key ~/.ssh/id_ed25519 \
    --with-hailo --hef ~/models/yolov8s_h8l.hef \
    --public-base http://cyclops:8080
```
`--with-hailo` installs the NPU stack in the correct order (dkms first,
then `hailo-all`) and reboots once. Then SSH in once to set a real
`enroll_token` and Twilio creds in `/opt/cyclops/config.toml`.

### Eye (already-booted, reachable Pi Zero 2 W)
```bash
export CYCLOPS_ENROLL_TOKEN=<same token as the server>
deploy/bootstrap_eye.sh --ip <eye-ip> --key ~/.ssh/id_ed25519 --name front-door
```
Copies the repo, installs the camnode stack, reboots if the camera
overlay was newly enabled, waits, and confirms registration.

## Zero-touch: provision an Eye from the SD card

Flash Raspberry Pi OS **Lite 64-bit (Trixie)** with Imager (you can skip
all of Imager's customization — this script does it). Re-insert the card
so the boot partition mounts, then:

```bash
export CYCLOPS_ENROLL_TOKEN=<token>
# Tailscale: either mint a fresh one-off key now...
export TS_OAUTH_CLIENT_ID=...   TS_OAUTH_CLIENT_SECRET=...
deploy/make_eye_sdcard.sh --name driveway \
    --ssh-pubkey ~/.ssh/id_ed25519.pub \
    --wifi-ssid "MyNet" --wifi-pass "secret" --wifi-country US \
    --cyclops-url http://cyclops:8080 --ts-mint
# ...or pass a key you already have: --ts-authkey tskey-auth-...
```

Eject, boot the Pi, done. First boot connects WiFi, joins the tailnet,
installs camnode, reboots once for the camera overlay, and registers —
no keyboard or monitor. The new tile appears at the bottom of `/stream`.

**Why cloud-init, not `firstrun.sh`:** Raspberry Pi OS Trixie images
(24 Nov 2025+) switched first-boot provisioning to **cloud-init**
(`user-data` / `network-config` / `meta-data` on the boot partition).
The legacy `firstrun.sh` and the Imager GUI's SSH-key customization are
both unreliable on current images, so we write the cloud-init files
directly — see `docs/RESEARCH.md`.

**Tailscale auth keys:** OAuth-minted keys must be tagged. One-time
admin-console setup: create an OAuth client with the `auth_keys` scope
owning `tag:cyclops-eye`, and add `tag:cyclops-eye` as a tagOwner in
your ACL. `make_eye_sdcard.sh --ts-mint` then mints a fresh single-use,
pre-authorized key per card; the device shreds it after joining.

**The one possible manual step:** if you use a key that is *not*
pre-authorized (or you skip `--ts-mint`/`--ts-authkey`), approve the new
device once in the Tailscale admin console when it appears.

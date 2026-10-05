# Cyclops SDK integration (Luckfox Pico Pro/Max, RV1106)

This directory contains the files needed to build a Cyclops eye into an official
Luckfox SDK firmware image — the sanctioned, reversible path (no hand-repacking
of flashed partitions).

## How the stock image owns the camera

`/etc/init.d/S21appinit` runs `/oem/usr/bin/RkLunch.sh`, which:
1. loads the camera kernel modules,
2. brings up `eth0` and runs `udhcpc`,
3. starts `rkipc -a /oem/usr/share/iqfiles` as the single camera owner.

Only one process may own the RV1106 ISP/VI, so the Cyclops daemon must replace
the `rkipc` launch. We do that in `RkLunch.sh`, keeping the module load and
network setup intact and falling back to `rkipc` if the cyclops binary is
missing (so a plain SDK build still works).

## Files

- `app-Makefile` — SDK app package Makefile; place at `project/app/cyclops_eye/Makefile`.
- `RkLunch.sh` — replacement launcher; place at
  `project/app/rkipc/rkipc/src/rv1106_ipc/RkLunch.sh`.
- `cyclops-eye.conf.example` — board config template (goes to `/etc/cyclops-eye.conf`).
- `apply.sh` — stages everything into an SDK checkout and runs the incremental build.

## Build

```
SDK=/path/to/luckfox-pico sdk-integration/apply.sh "$SDK"
# produces "$SDK/output/image/update.img"
```

For the full, verified end-to-end procedure (SDK setup, jobserver/wifi patches,
flashing, provisioning, verification, and the exact failures we hit), see
**`RUNBOOK.md`**. Two helpers implement the routine steps:

- `make-image.sh <host-out-dir>` — stages the app + launcher into the SDK
  Docker volume, runs `./build.sh app && ./build.sh firmware`, and copies the
  resulting `update.img` out.
- `provision-eye.sh <node_name>` — over ADB writes `/oem/etc/cyclops-eye.conf`,
  installs the admin SSH key, and reboots so the eye self-registers.
- `watch-build.sh <log> [volume] [interval] [iters]` — live build progress.

`apply.sh` targets a host-path SDK; `make-image.sh` targets the Docker-volume
SDK used in this project.

Because the SDK app Makefile auto-discovers `./*/Makefile`, adding
`project/app/cyclops_eye/` makes `./build.sh app` compile the Cyclops daemon and
install it to `/oem/usr/bin/cyclops-eye`, and `./build.sh updateimg` repackages
the full image.

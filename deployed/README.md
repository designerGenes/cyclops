# Deployed System Snapshot

Exact copies of the software **as currently deployed** to the running Cyclops
installation, captured 2026-08-28 after the tier-drift fix. This is the live
lineage (FastAPI brain + camnode agents + MediaMTX) — it is *not* the newer
`apps/coordinator-*` rewrite elsewhere in this repo.

## Layout

```
coordinator/            Pi 5 brain (cyclops, Tailscale "cyclops")
  opt-cyclops/           /opt/cyclops snapshot (live software, not venv/data)
  etc-systemd-system/    cyclops.service, mediamtx-central.service

eyes/                    RPi Zero 2 W camera nodes (IMX708 cameras)
  shared/                Identical on both eyes (md5-verified):
                           opt-camnode/     /opt/camnode/camnode (agent code)
                           opt-mediamtx/    /opt/mediamtx/mediamtx.yml
                           etc-systemd-system/  camnode.service, mediamtx.service
  camera-01/            camnode.toml + /boot/firmware/{cmdline,config}.txt
  camera-02/              camnode.toml + /boot/firmware/{cmdline,config}.txt
```

The brain's `opt-cyclops/node/camnode/` is the canonical deploy source for the
eyes (used by `provision/install_camnode.sh`); the eyes run the same files —
md5s match as of the capture date.

## Versions

- Brain: Raspberry Pi 5 (aarch64), Python venv at `/opt/cyclops/venv`,
  uvicorn serving `cyclops.main:app` on :8080, Hailo detection with
  `/opt/cyclops/models/yolov8s.hef`
- Eyes: Raspberry Pi Zero 2 W, Python 3.11.2 (stdlib-only agent)
- MediaMTX v1.19.1 (binary at `/opt/mediamtx/mediamtx`, not included) on all
  three machines

## Excluded from the snapshot

- `/opt/cyclops/venv/` (133M), `releases/` (54M), `models/*.hef` (21M),
  `hailort.log`, `__pycache__`, `*.bak` backups, `.git_backup/`
- One person-detection alert snapshot JPEG under `data/alerts/`
- MediaMTX and other binaries

## Secrets

The shared enrollment token was **redacted** in these files (originals on the
machines are untouched):

- `coordinator/opt-cyclops/config.toml`
- `eyes/camera-01/camnode.toml`
- `eyes/camera-02/camnode.toml`

All three originally contained `enroll_token = "<REDACTED-SEE-NOTE-IN-README>"`;
replace from the live machines when reconstructing a deployment. No Tailscale
auth keys, WiFi passwords, or other credentials are present (scanned).

## Reconstructing

Copy each tree back to its original path (`coordinator/opt-cyclops` →
`/opt/cyclops`, `eyes/shared/*` → the same absolute paths on each eye,
per-eye `camnode.toml` → `/opt/camnode/camnode.toml`), install the venv from
`requirements.txt`, provide the Hailo `.hef` model and MediaMTX v1.19.1
binaries, then `systemctl daemon-reload` and start the units in
`etc-systemd-system/`.
# Configuration

## Edge service

Use `/Users/jadennation/DEV/01_active_projects/cyclops/config/examples/edge.env.example` as the baseline environment file. The edge service persists effective settings to `/var/lib/cyclops-edge/settings.json` by default and supports `CYCLOPS_CAMERA_PROVIDER=mock` for non-Pi development and CI.

Edge endpoint summary:

- `GET /stream` – MJPEG stream
- `GET /settings` – human-usable settings page
- `GET /api/v1/settings` – current settings JSON
- `PUT /api/v1/settings` – apply settings JSON
- `GET /healthz` – cheap health probe
- `GET /api/v1/camera` – camera metadata

## Coordinator service

Use `/Users/jadennation/DEV/01_active_projects/cyclops/config/examples/coordinator.env.example` and a YAML camera registry such as `/Users/jadennation/DEV/01_active_projects/cyclops/config/examples/cameras.example.yaml`.

Coordinator defaults:

- SQLite DB path: `/var/lib/cyclops-coordinator/cyclops.db`
- health polling interval: 10 seconds
- per-camera polling timeout: 2 seconds

The coordinator preserves offline registry cameras and serves the built coordinator UI from its own HTTP service.

## Security note

Phase 1 intentionally does not include app-level authentication and assumes operation within a trusted private LAN or Tailscale boundary.

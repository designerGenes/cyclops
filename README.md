# Cyclops Phase 1

Cyclops is a Phase 1 private-LAN home camera system with:

- a FastAPI edge camera service exposing MJPEG at `/stream`
- a FastAPI coordinator API serving a mobile-first React UI
- SQLite-backed shared layout persistence on the coordinator
- JSON-backed camera settings persistence on each edge node
- a mock camera provider for local development and CI

## Phase 1 limitations

- No application-level authentication; deployment assumes a trusted private LAN or Tailscale boundary.
- No motion detection, recording storage, public exposure, or cloud dependencies.
- Live video is loaded directly from edge devices by the browser.

## Monorepo layout

- `/Users/jadennation/DEV/01_active_projects/cyclops/apps/edge-camera` – edge camera service
- `/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-api` – coordinator API and static UI host
- `/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web` – React web UI
- `/Users/jadennation/DEV/01_active_projects/cyclops/packages/contracts` – shared schemas and TS contracts

## Local development

```bash
cd /Users/jadennation/DEV/01_active_projects/cyclops && uv sync
cd /Users/jadennation/DEV/01_active_projects/cyclops && pnpm install

cd /Users/jadennation/DEV/01_active_projects/cyclops && uv run uvicorn cyclops_edge.app:app --app-dir /Users/jadennation/DEV/01_active_projects/cyclops/apps/edge-camera/src --reload --port 8050
cd /Users/jadennation/DEV/01_active_projects/cyclops && uv run uvicorn cyclops_coordinator.app:app --app-dir /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-api/src --reload --port 8060
cd /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web && pnpm dev
```

Use `/Users/jadennation/DEV/01_active_projects/cyclops/config/examples/edge.env.example`, `/Users/jadennation/DEV/01_active_projects/cyclops/config/examples/coordinator.env.example`, and `/Users/jadennation/DEV/01_active_projects/cyclops/config/examples/cameras.example.yaml` as templates.

## Verification

```bash
cd /Users/jadennation/DEV/01_active_projects/cyclops && uv run pytest /Users/jadennation/DEV/01_active_projects/cyclops/apps/edge-camera/tests /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-api/tests
cd /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web && pnpm test
cd /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web && pnpm exec playwright test
cd /Users/jadennation/DEV/01_active_projects/cyclops && bash /Users/jadennation/DEV/01_active_projects/cyclops/ops/deploy/build-release.sh
```

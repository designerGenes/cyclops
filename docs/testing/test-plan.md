# Test Plan

Cyclops Phase 1 verification requires all of the following:

## Python backend tests

```bash
cd /Users/jadennation/DEV/01_active_projects/cyclops && uv run pytest /Users/jadennation/DEV/01_active_projects/cyclops/apps/edge-camera/tests /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-api/tests
```

Coverage includes edge MJPEG behavior, settings page/API, health reporting, coordinator registry loading, layout persistence, health polling, and stale layout reconciliation.

## Frontend unit tests

```bash
cd /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web && pnpm test
```

Coverage includes rendering 1/2/3/4/N camera layouts, offline tiles, reorder and resize state, localStorage persistence, and stale layout cleanup.

## Mobile end-to-end tests

```bash
cd /Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web && pnpm exec playwright test
```

The Playwright suite runs with a mobile viewport, verifies the stacked layout, tests tile reorder and resize behavior, confirms reload persistence, and ensures offline tiles remain visible.

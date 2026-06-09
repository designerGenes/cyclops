# ADR 0001: Phase 1 Stack

- **Status:** Accepted
- **Date:** 2026-05-02

## Decision

Cyclops Phase 1 uses Python 3.11 + uv for the edge and coordinator services, FastAPI + Uvicorn for HTTP APIs, React + TypeScript + Vite + pnpm for the coordinator web UI, SQLite on the coordinator for persisted shared state, JSON settings persistence on edge nodes, and MJPEG over HTTP at `/stream`.

## Rationale

- Raspberry Pi camera integration is best served by Python.
- MJPEG enables browser-native playback in `<img>` tags with low implementation risk.
- React provides a practical touch-first path for reorder and resize interactions.
- SQLite and JSON minimize operational complexity while remaining restart-safe.

## Consequences

- Live video is loaded directly from edge devices by the browser.
- Phase 1 intentionally relies on the private LAN/Tailscale trust boundary instead of app-level auth.
- The camera provider abstraction preserves a future path to replace MJPEG internals without breaking `/stream` or `/settings` paths.

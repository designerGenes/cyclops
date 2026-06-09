from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from cyclops_coordinator import __version__
from cyclops_coordinator.config import CoordinatorConfig, get_config
from cyclops_coordinator.db import CoordinatorDatabase
from cyclops_coordinator.health_polling import HealthPoller
from cyclops_coordinator.layout_store import generate_default_layout, reconcile_layout
from cyclops_coordinator.models import CameraNode, Layout, SystemStatus
from cyclops_coordinator.registry import RegistryState, load_registry
from cyclops_coordinator.routes.cameras import router as cameras_router
from cyclops_coordinator.routes.layouts import router as layouts_router
from cyclops_coordinator.routes.status import router as status_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config: CoordinatorConfig | None = None, *, start_poller: bool = True) -> FastAPI:
    config = config or get_config()
    app = FastAPI(title="Cyclops Coordinator", version=__version__)
    db = CoordinatorDatabase(config.db_path)
    registry_state = _load_registry_safe(config.camera_registry_path)

    def registry_cameras() -> list[CameraNode]:
        return registry_state.cameras

    def camera_view() -> list[CameraNode]:
        cache = db.get_status_cache()
        cameras: list[CameraNode] = []
        for camera in registry_state.cameras:
            record = cache.get(camera.id)
            cameras.append(
                camera.model_copy(
                    update={
                        "status": record.status if record else "unknown",
                        "last_seen_at": record.last_seen_at if record else None,
                        "software_version": record.software_version if record else None,
                    }
                )
            )
        layout = db.get_layout("default")
        if layout is None:
            return cameras
        order_map = {tile.camera_id: tile.order for tile in layout.tiles}
        return sorted(cameras, key=lambda camera: order_map.get(camera.id, len(cameras)))

    def get_layout() -> Layout:
        camera_ids = [camera.id for camera in registry_state.cameras]
        layout = db.get_layout("default")
        if layout is None:
            return generate_default_layout(camera_ids)
        reconciled = reconcile_layout(layout, camera_ids)
        if reconciled != layout:
            db.save_layout(reconciled)
        return reconciled

    def save_layout(layout: Layout) -> Layout:
        saved = reconcile_layout(layout, [camera.id for camera in registry_state.cameras])
        return db.save_layout(saved)

    def system_status() -> SystemStatus:
        cameras = camera_view()
        return SystemStatus(
            coordinator_version=__version__,
            camera_count=len(cameras),
            online_count=len([camera for camera in cameras if camera.status == "online"]),
            offline_count=len([camera for camera in cameras if camera.status == "offline"]),
            last_registry_reload_timestamp=registry_state.loaded_at,
        )

    poller = HealthPoller(
        db=db,
        timeout_seconds=config.health_poll_timeout_seconds,
        interval_seconds=config.health_poll_interval_seconds,
        get_cameras=registry_cameras,
    )

    app.state.services = {
        "db": db,
        "registry_cameras": registry_cameras,
        "camera_view": camera_view,
        "get_layout": get_layout,
        "save_layout": save_layout,
        "system_status": system_status,
        "poller": poller,
    }
    app.include_router(cameras_router)
    app.include_router(layouts_router)
    app.include_router(status_router)

    static_dir = config.static_dir
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "assets").mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.on_event("startup")
    async def startup() -> None:
        if start_poller:
            await poller.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await poller.stop()

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "coordinator web UI is not built; run the release or frontend build workflow"
            },
        )

    return app


def _load_registry_safe(path: Path) -> RegistryState:
    try:
        return load_registry(path)
    except Exception as exc:
        logger.warning("Failed to load registry at %s: %s", path, exc)
        return RegistryState(cameras=[], loaded_at=datetime.now(UTC))


app = create_app()

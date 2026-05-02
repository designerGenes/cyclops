from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from cyclops_coordinator import __version__
from cyclops_coordinator.db import CoordinatorDatabase
from cyclops_coordinator.models import CameraHealth, CameraNode, CameraStatusCacheRecord

logger = logging.getLogger(__name__)


class HealthPoller:
    def __init__(
        self,
        db: CoordinatorDatabase,
        timeout_seconds: float,
        get_cameras,
        interval_seconds: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.db = db
        self.timeout_seconds = timeout_seconds
        self.interval_seconds = interval_seconds
        self.get_cameras = get_cameras
        self.client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        await self.client.aclose()

    async def _run(self) -> None:
        while not self._stop.is_set():
            await self.poll_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def poll_once(self) -> None:
        cameras: list[CameraNode] = self.get_cameras()
        await asyncio.gather(*(self._poll_camera(camera) for camera in cameras), return_exceptions=True)

    async def _poll_camera(self, camera: CameraNode) -> None:
        cache = self.db.get_status_cache().get(camera.id)
        try:
            response = await self.client.get(camera.health_url, timeout=self.timeout_seconds)
            response.raise_for_status()
            health = CameraHealth.model_validate(response.json())
            status = "degraded" if (not health.camera_ready or not health.stream_ready or health.status == "degraded") else "online"
            record = CameraStatusCacheRecord(
                camera_id=camera.id,
                status=status,
                last_seen_at=datetime.now(UTC),
                software_version=health.software_version,
                provider=health.provider,
                camera_ready=health.camera_ready,
                stream_ready=health.stream_ready,
                last_frame_at=health.last_frame_at,
                consecutive_failures=0,
                updated_at=datetime.now(UTC),
            )
        except Exception as exc:
            logger.warning("Health poll failed for %s: %s", camera.id, exc)
            failures = (cache.consecutive_failures if cache else 0) + 1
            status = "offline" if failures >= 3 else (cache.status if cache else "unknown")
            record = CameraStatusCacheRecord(
                camera_id=camera.id,
                status=status,
                last_seen_at=cache.last_seen_at if cache else None,
                software_version=cache.software_version if cache else __version__,
                provider=cache.provider if cache else camera.capabilities.provider,
                camera_ready=cache.camera_ready if cache else False,
                stream_ready=cache.stream_ready if cache else False,
                last_frame_at=cache.last_frame_at if cache else None,
                consecutive_failures=failures,
                updated_at=datetime.now(UTC),
            )
        self.db.upsert_status(record)

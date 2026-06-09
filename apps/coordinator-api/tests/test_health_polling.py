from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from cyclops_coordinator.db import CoordinatorDatabase
from cyclops_coordinator.health_polling import HealthPoller
from cyclops_coordinator.models import CameraCapabilities, CameraNode


def cameras() -> list[CameraNode]:
    return [
        CameraNode(
            id="cam1",
            name="Cam 1",
            hostname=None,
            tailscale_ip=None,
            stream_url="http://cam1/stream",
            settings_url="http://cam1/settings",
            health_url="http://cam1/healthz",
            status="unknown",
            last_seen_at=None,
            software_version=None,
            capabilities=CameraCapabilities(provider="mock"),
        ),
        CameraNode(
            id="cam2",
            name="Cam 2",
            hostname=None,
            tailscale_ip=None,
            stream_url="http://cam2/stream",
            settings_url="http://cam2/settings",
            health_url="http://cam2/healthz",
            status="unknown",
            last_seen_at=None,
            software_version=None,
            capabilities=CameraCapabilities(provider="mock"),
        ),
        CameraNode(
            id="cam3",
            name="Cam 3",
            hostname=None,
            tailscale_ip=None,
            stream_url="http://cam3/stream",
            settings_url="http://cam3/settings",
            health_url="http://cam3/healthz",
            status="unknown",
            last_seen_at=None,
            software_version=None,
            capabilities=CameraCapabilities(provider="mock"),
        ),
    ]


@pytest.mark.asyncio
async def test_health_polling_marks_online_offline_degraded_correctly(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cam1":
            if request.url.path == "/api/v1/frame":
                return httpx.Response(200, content=b"jpeg")
            return httpx.Response(
                200,
                json={
                    "camera_id": "cam1",
                    "status": "online",
                    "provider": "mock",
                    "camera_ready": True,
                    "stream_ready": True,
                    "last_frame_at": "2026-01-01T00:00:00+00:00",
                    "uptime_seconds": 1,
                    "software_version": "0.1.0",
                },
            )
        if request.url.host == "cam2":
            if request.url.path == "/api/v1/frame":
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "camera_id": "cam2",
                    "status": "degraded",
                    "provider": "mock",
                    "camera_ready": True,
                    "stream_ready": False,
                    "last_frame_at": None,
                    "uptime_seconds": 1,
                    "software_version": "0.1.0",
                },
            )
        raise httpx.ConnectTimeout("timeout")

    db = CoordinatorDatabase(tmp_path / "cyclops.db")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    poller = HealthPoller(db=db, timeout_seconds=1, interval_seconds=60, get_cameras=cameras, client=client)
    await poller.poll_once()
    await poller.poll_once()
    await poller.poll_once()
    status = db.get_status_cache()
    assert status["cam1"].status == "online"
    assert status["cam2"].status == "degraded"
    assert status["cam3"].status == "offline"

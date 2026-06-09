from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cyclops_edge.app import create_app
from cyclops_edge.camera_provider import CameraProviderError, RecoveringCameraProvider
from cyclops_edge.config import EdgeConfig
from cyclops_edge.models import CameraHealth, CameraSettings


def test_health_reports_readiness_fields(tmp_path: Path) -> None:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["camera_ready"] is True
    assert body["stream_ready"] is True
    assert body["provider"] == "mock"


def test_health_recovers_provider_after_startup_failure(tmp_path: Path) -> None:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    original_provider = app.state.edge.provider
    attempts = {"count": 0}

    class HealthyProvider:
        def __init__(self, settings: CameraSettings) -> None:
            self._settings = settings

        def get_settings(self):
            return self._settings

        def apply_settings(self, settings):
            self._settings = settings
            return original_provider.apply_settings(settings)

        def next_frame(self) -> bytes:
            return b"jpeg-bytes"

        def health(self) -> CameraHealth:
            return CameraHealth(
                camera_id="camera-1",
                status="online",
                provider="mock",
                camera_ready=True,
                stream_ready=True,
                last_frame_at=None,
                uptime_seconds=1,
                software_version="test",
            )

        def capabilities_provider(self) -> str:
            return "mock"

        def last_frame_at(self):
            return None

        def close(self) -> None:
            return None

    def flaky_factory(settings: CameraSettings):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise CameraProviderError("camera booting")
        return HealthyProvider(settings)

    app.state.edge.provider = RecoveringCameraProvider(
        factory=flaky_factory,
        camera_id="camera-1",
        provider="mock",
        settings=original_provider.get_settings(),
        retry_interval_seconds=0,
    )
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["camera_ready"] is True
    assert body["status"] == "online"
    assert attempts["count"] >= 2

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from cyclops_edge.app import create_app
from cyclops_edge.camera_provider import CameraProviderError
from cyclops_edge.config import EdgeConfig
from cyclops_edge.models import CameraHealth


def test_stream_returns_mjpeg_content_type(tmp_path: Path) -> None:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    client = TestClient(app)
    with client.stream("GET", "/stream", headers={"x-cyclops-test-once": "1"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("multipart/x-mixed-replace; boundary=frame")


def test_stream_emits_boundary(tmp_path: Path) -> None:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    client = TestClient(app)
    with client.stream("GET", "/stream", headers={"x-cyclops-test-once": "1"}) as response:
        chunk = next(response.iter_bytes())
        assert b"--frame" in chunk


def test_stream_stops_cleanly_when_provider_fails_after_start(tmp_path: Path) -> None:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    original_provider = app.state.edge.provider

    class FailingProvider:
        def get_settings(self):
            return original_provider.get_settings()

        def apply_settings(self, settings):
            return original_provider.apply_settings(settings)

        def __init__(self) -> None:
            self.calls = 0

        def next_frame(self) -> bytes:
            self.calls += 1
            if self.calls == 1:
                return b"jpeg-bytes"
            raise CameraProviderError("camera offline")

        def health(self) -> CameraHealth:
            return CameraHealth(
                camera_id="camera-1",
                status="degraded",
                provider="mock",
                camera_ready=True,
                stream_ready=False,
                last_frame_at=datetime.now(),
                uptime_seconds=1,
                software_version="test",
            )

        def capabilities_provider(self) -> str:
            return "mock"

        def last_frame_at(self):
            return None

    app.state.edge.provider = FailingProvider()
    client = TestClient(app)

    with client.stream("GET", "/stream", headers={"x-cyclops-test-once": "1"}) as response:
        chunk = next(response.iter_bytes())
        assert response.status_code == 200
        assert b"--frame" in chunk


def test_stream_returns_503_when_first_frame_fails(tmp_path: Path) -> None:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    original_provider = app.state.edge.provider

    class UnavailableStreamProvider:
        def get_settings(self):
            return original_provider.get_settings()

        def apply_settings(self, settings):
            return original_provider.apply_settings(settings)

        def next_frame(self) -> bytes:
            raise CameraProviderError("camera offline")

        def health(self) -> CameraHealth:
            return CameraHealth(
                camera_id="camera-1",
                status="degraded",
                provider="mock",
                camera_ready=True,
                stream_ready=False,
                last_frame_at=datetime.now(),
                uptime_seconds=1,
                software_version="test",
            )

        def capabilities_provider(self) -> str:
            return "mock"

        def last_frame_at(self):
            return None

    app.state.edge.provider = UnavailableStreamProvider()
    client = TestClient(app)

    response = client.get("/stream")

    assert response.status_code == 503
    assert response.json() == {"detail": "stream unavailable"}

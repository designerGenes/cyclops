from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cyclops_edge.app import create_app
from cyclops_edge.config import EdgeConfig


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

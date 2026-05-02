from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cyclops_coordinator.app import create_app
from cyclops_coordinator.config import CoordinatorConfig
from cyclops_coordinator.registry import load_registry


def make_config(tmp_path: Path, registry_text: str) -> CoordinatorConfig:
    registry_path = tmp_path / "cameras.yaml"
    registry_path.write_text(registry_text)
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    return CoordinatorConfig(
        CYCLOPS_DB_PATH=tmp_path / "cyclops.db",
        CYCLOPS_CAMERA_REGISTRY_PATH=registry_path,
        CYCLOPS_STATIC_DIR=static_dir,
        CYCLOPS_HEALTH_POLL_INTERVAL_SECONDS=60,
        CYCLOPS_HEALTH_POLL_TIMEOUT_SECONDS=1,
    )


def registry_text() -> str:
    return """
cameras:
  - id: nilescrane
    name: Niles Crane
    hostname: nilescrane.local
    tailscale_ip: 100.64.0.10
    stream_url: http://nilescrane.local:8050/stream
    settings_url: http://nilescrane.local:8050/settings
    health_url: http://nilescrane.local:8050/healthz
    enabled: true
    provider: mock
  - id: daphnemoon
    name: Daphne Moon
    hostname: daphnemoon.local
    tailscale_ip: 100.64.0.11
    stream_url: http://daphnemoon.local:8050/stream
    settings_url: http://daphnemoon.local:8050/settings
    health_url: http://daphnemoon.local:8050/healthz
    enabled: true
    provider: mock
"""


def test_registry_file_loads(tmp_path: Path) -> None:
    config = make_config(tmp_path, registry_text())
    registry = load_registry(config.camera_registry_path)
    assert [camera.id for camera in registry.cameras] == ["nilescrane", "daphnemoon"]


def test_get_cameras_includes_offline_registry_entries(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path, registry_text()), start_poller=False)
    with TestClient(app) as client:
        response = client.get("/api/v1/cameras")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {item["status"] for item in body} == {"unknown"}

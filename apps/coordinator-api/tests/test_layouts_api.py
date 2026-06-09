from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cyclops_coordinator.app import create_app
from cyclops_coordinator.config import CoordinatorConfig


def make_app(tmp_path: Path, registry_text: str):
    registry_path = tmp_path / "cameras.yaml"
    registry_path.write_text(registry_text)
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    config = CoordinatorConfig(
        CYCLOPS_DB_PATH=tmp_path / "cyclops.db",
        CYCLOPS_CAMERA_REGISTRY_PATH=registry_path,
        CYCLOPS_STATIC_DIR=static_dir,
        CYCLOPS_HEALTH_POLL_INTERVAL_SECONDS=60,
        CYCLOPS_HEALTH_POLL_TIMEOUT_SECONDS=1,
    )
    return create_app(config, start_poller=False)


def test_get_default_layout_generates_registry_order(tmp_path: Path) -> None:
    app = make_app(
        tmp_path,
        """
cameras:
  - id: a
    name: A
    stream_url: http://a/stream
    settings_url: http://a/settings
    health_url: http://a/healthz
    enabled: true
    provider: mock
  - id: b
    name: B
    stream_url: http://b/stream
    settings_url: http://b/settings
    health_url: http://b/healthz
    enabled: true
    provider: mock
""",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/layouts/default")
    assert response.status_code == 200
    body = response.json()
    assert [tile["camera_id"] for tile in body["tiles"]] == ["a", "b"]
    assert all(tile["height_px"] == 240 for tile in body["tiles"])


def test_put_default_layout_validates_and_persists(tmp_path: Path) -> None:
    app = make_app(
        tmp_path,
        """
cameras:
  - id: a
    name: A
    stream_url: http://a/stream
    settings_url: http://a/settings
    health_url: http://a/healthz
    enabled: true
    provider: mock
  - id: b
    name: B
    stream_url: http://b/stream
    settings_url: http://b/settings
    health_url: http://b/healthz
    enabled: true
    provider: mock
""",
    )
    with TestClient(app) as client:
        payload = {
            "layout_id": "default",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "tiles": [
                {"camera_id": "b", "order": 0, "height_px": 300, "visible": True},
                {"camera_id": "a", "order": 1, "height_px": 200, "visible": True},
            ],
        }
        response = client.put("/api/v1/layouts/default", json=payload)
        persisted = client.get("/api/v1/layouts/default")
    assert response.status_code == 200
    assert persisted.json()["tiles"][0]["camera_id"] == "b"


def test_stale_layout_reconciliation_when_registry_changes(tmp_path: Path) -> None:
    initial_registry = tmp_path / "registry.yaml"
    initial_registry.write_text(
        """
cameras:
  - id: a
    name: A
    stream_url: http://a/stream
    settings_url: http://a/settings
    health_url: http://a/healthz
    enabled: true
    provider: mock
  - id: b
    name: B
    stream_url: http://b/stream
    settings_url: http://b/settings
    health_url: http://b/healthz
    enabled: true
    provider: mock
"""
    )
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    db_path = tmp_path / "cyclops.db"
    app = create_app(
        CoordinatorConfig(
            CYCLOPS_DB_PATH=db_path,
            CYCLOPS_CAMERA_REGISTRY_PATH=initial_registry,
            CYCLOPS_STATIC_DIR=static_dir,
            CYCLOPS_HEALTH_POLL_INTERVAL_SECONDS=60,
            CYCLOPS_HEALTH_POLL_TIMEOUT_SECONDS=1,
        ),
        start_poller=False,
    )
    with TestClient(app) as client:
        client.put(
            "/api/v1/layouts/default",
            json={
                "layout_id": "default",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "tiles": [
                    {"camera_id": "b", "order": 0, "height_px": 300, "visible": True},
                    {"camera_id": "a", "order": 1, "height_px": 240, "visible": True},
                ],
            },
        )

    initial_registry.write_text(
        """
cameras:
  - id: b
    name: B
    stream_url: http://b/stream
    settings_url: http://b/settings
    health_url: http://b/healthz
    enabled: true
    provider: mock
  - id: c
    name: C
    stream_url: http://c/stream
    settings_url: http://c/settings
    health_url: http://c/healthz
    enabled: true
    provider: mock
"""
    )
    app_reloaded = create_app(
        CoordinatorConfig(
            CYCLOPS_DB_PATH=db_path,
            CYCLOPS_CAMERA_REGISTRY_PATH=initial_registry,
            CYCLOPS_STATIC_DIR=static_dir,
            CYCLOPS_HEALTH_POLL_INTERVAL_SECONDS=60,
            CYCLOPS_HEALTH_POLL_TIMEOUT_SECONDS=1,
        ),
        start_poller=False,
    )
    with TestClient(app_reloaded) as client:
        response = client.get("/api/v1/layouts/default")
    assert [tile["camera_id"] for tile in response.json()["tiles"]] == ["b", "c"]

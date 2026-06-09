from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from cyclops_edge.app import create_app
from cyclops_edge.config import EdgeConfig


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    return TestClient(app)


def test_get_settings_returns_defaults(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["frame_rate"] == 5


def test_put_settings_persists_valid_settings(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = {
        "rotation_degrees": 90,
        "hflip": True,
        "vflip": False,
        "brightness": 0.2,
        "contrast": 1.3,
        "saturation": 1.1,
        "jpeg_quality": 80,
        "frame_rate": 8,
        "stream_width": 800,
        "stream_height": 450,
    }
    response = client.put("/api/v1/settings", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["settings"]["rotation_degrees"] == 90
    persisted = json.loads((tmp_path / "settings.json").read_text())
    assert persisted["stream_width"] == 800


def test_invalid_settings_return_422(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.put(
        "/api/v1/settings",
        json={
            "rotation_degrees": 0,
            "hflip": False,
            "vflip": False,
            "brightness": 2,
            "contrast": 1,
            "saturation": 1,
            "jpeg_quality": 80,
            "frame_rate": 8,
            "stream_width": 800,
            "stream_height": 450,
        },
    )
    assert response.status_code == 422

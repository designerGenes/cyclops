from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cyclops_edge.app import create_app
from cyclops_edge.config import EdgeConfig


def test_settings_page_returns_html_with_values(tmp_path: Path) -> None:
    app = create_app(
        EdgeConfig(
            CYCLOPS_SETTINGS_PATH=tmp_path / "settings.json",
            CYCLOPS_CAMERA_PROVIDER="mock",
        )
    )
    client = TestClient(app)
    response = client.get("/settings")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Apply Settings" in response.text
    assert 'value="640"' in response.text

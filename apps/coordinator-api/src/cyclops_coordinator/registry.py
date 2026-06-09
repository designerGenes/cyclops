from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from cyclops_coordinator.models import CameraCapabilities, CameraNode, RegistryDocument


@dataclass
class RegistryState:
    cameras: list[CameraNode]
    loaded_at: datetime


def load_registry(path: Path) -> RegistryState:
    raw = yaml.safe_load(path.read_text()) if path.exists() else {"cameras": []}
    document = RegistryDocument.model_validate(raw or {"cameras": []})
    cameras = [
        CameraNode(
            id=entry.id,
            name=entry.name,
            hostname=entry.hostname,
            tailscale_ip=entry.tailscale_ip,
            stream_url=entry.stream_url,
            settings_url=entry.settings_url,
            health_url=entry.health_url,
            status="unknown",
            last_seen_at=None,
            software_version=None,
            capabilities=CameraCapabilities(
                provider=entry.provider,
                stream_kind="mjpeg",
                supports_settings=True,
                supports_future_analytics_ingest=True,
            ),
        )
        for entry in document.cameras
        if entry.enabled
    ]
    return RegistryState(cameras=cameras, loaded_at=datetime.now(UTC))

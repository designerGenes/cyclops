from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CameraProviderKind = Literal["mock", "picamera2"]
CameraStatus = Literal["unknown", "online", "offline", "degraded"]


class CameraCapabilities(BaseModel):
    provider: CameraProviderKind
    stream_kind: Literal["mjpeg"] = "mjpeg"
    supports_settings: bool = True
    supports_future_analytics_ingest: bool = True


class CameraNode(BaseModel):
    id: str
    name: str
    hostname: str | None
    tailscale_ip: str | None
    stream_url: str
    settings_url: str
    health_url: str
    status: CameraStatus = "unknown"
    last_seen_at: datetime | None = None
    software_version: str | None = None
    capabilities: CameraCapabilities


class CameraHealth(BaseModel):
    camera_id: str
    status: Literal["online", "offline", "degraded"]
    provider: CameraProviderKind
    camera_ready: bool
    stream_ready: bool
    last_frame_at: datetime | None = None
    uptime_seconds: int
    software_version: str


class RegistryCameraEntry(BaseModel):
    id: str
    name: str
    hostname: str | None = None
    tailscale_ip: str | None = None
    stream_url: str
    settings_url: str
    health_url: str
    enabled: bool = True
    provider: CameraProviderKind = "mock"


class RegistryDocument(BaseModel):
    cameras: list[RegistryCameraEntry] = Field(default_factory=list)


class LayoutTile(BaseModel):
    camera_id: str
    order: int = Field(ge=0)
    height_px: int = Field(ge=180, le=720)
    visible: bool = True


class Layout(BaseModel):
    layout_id: Literal["default"] = "default"
    tiles: list[LayoutTile]
    updated_at: datetime

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_order(self) -> "Layout":
        orders = [tile.order for tile in self.tiles]
        if sorted(orders) != list(range(len(self.tiles))):
            raise ValueError("tile order must be contiguous starting at 0")
        return self


class CameraStatusCacheRecord(BaseModel):
    camera_id: str
    status: CameraStatus
    last_seen_at: datetime | None = None
    software_version: str | None = None
    provider: CameraProviderKind | None = None
    camera_ready: bool | None = None
    stream_ready: bool | None = None
    last_frame_at: datetime | None = None
    consecutive_failures: int = 0
    updated_at: datetime


class SystemStatus(BaseModel):
    coordinator_version: str
    camera_count: int
    online_count: int
    offline_count: int
    last_registry_reload_timestamp: datetime


class ErrorResponse(BaseModel):
    detail: str

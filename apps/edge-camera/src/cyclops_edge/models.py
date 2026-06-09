from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CameraProviderKind = Literal["mock", "picamera2"]
CameraStatus = Literal["unknown", "online", "offline", "degraded"]
CameraHealthStatus = Literal["online", "offline", "degraded"]


class CameraCapabilities(BaseModel):
    provider: CameraProviderKind
    stream_kind: Literal["mjpeg"] = "mjpeg"
    supports_settings: bool = True
    supports_future_analytics_ingest: bool = True


class CameraSettings(BaseModel):
    rotation_degrees: Literal[0, 90, 180, 270] = 0
    hflip: bool = False
    vflip: bool = False
    brightness: float = Field(default=0.0, ge=-1.0, le=1.0)
    contrast: float = Field(default=1.0, ge=0.0, le=2.0)
    saturation: float = Field(default=1.0, ge=0.0, le=2.0)
    jpeg_quality: int = Field(default=75, ge=40, le=95)
    frame_rate: int = Field(default=5, ge=1, le=15)
    stream_width: int = Field(default=640, gt=0)
    stream_height: int = Field(default=360, gt=0)

    model_config = ConfigDict(extra="forbid")


class CameraHealth(BaseModel):
    camera_id: str
    status: CameraHealthStatus
    provider: CameraProviderKind
    camera_ready: bool
    stream_ready: bool
    last_frame_at: datetime | None = None
    uptime_seconds: int
    software_version: str


class CameraNode(BaseModel):
    id: str
    name: str
    hostname: str | None
    tailscale_ip: str | None
    stream_url: str
    settings_url: str
    health_url: str
    status: CameraStatus
    last_seen_at: datetime | None = None
    software_version: str | None = None
    capabilities: CameraCapabilities


class SettingsUpdateResponse(BaseModel):
    settings: CameraSettings
    restart_required: bool
    restart_performed: bool


class FrameMetadata(BaseModel):
    captured_at: datetime
    frame_number: int | None = None


class ErrorResponse(BaseModel):
    detail: str

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cyclops_edge.models import CameraSettings


class EdgeConfig(BaseSettings):
    camera_id: str = Field(default="nilescrane", alias="CYCLOPS_CAMERA_ID")
    camera_name: str = Field(default="Niles Crane", alias="CYCLOPS_CAMERA_NAME")
    bind_host: str = Field(default="0.0.0.0", alias="CYCLOPS_BIND_HOST")
    port: int = Field(default=8050, alias="CYCLOPS_PORT")
    camera_provider: str = Field(default="mock", alias="CYCLOPS_CAMERA_PROVIDER")
    settings_path: Path = Field(default=Path("/var/lib/cyclops-edge/settings.json"), alias="CYCLOPS_SETTINGS_PATH")
    stream_width: int = Field(default=640, alias="CYCLOPS_STREAM_WIDTH")
    stream_height: int = Field(default=360, alias="CYCLOPS_STREAM_HEIGHT")
    frame_rate: int = Field(default=5, alias="CYCLOPS_FRAME_RATE")
    jpeg_quality: int = Field(default=75, alias="CYCLOPS_JPEG_QUALITY")
    hostname: str | None = Field(default=None, alias="CYCLOPS_HOSTNAME")
    tailscale_ip: str | None = Field(default=None, alias="CYCLOPS_TAILSCALE_IP")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def default_settings(self) -> CameraSettings:
        return CameraSettings(
            stream_width=self.stream_width,
            stream_height=self.stream_height,
            frame_rate=self.frame_rate,
            jpeg_quality=self.jpeg_quality,
        )


def get_config() -> EdgeConfig:
    return EdgeConfig()

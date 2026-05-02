from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from cyclops_edge import __version__
from cyclops_edge.models import CameraHealth, CameraProviderKind, CameraSettings


class CameraProviderError(RuntimeError):
    pass


class CameraBusyError(CameraProviderError):
    pass


@dataclass
class ApplySettingsResult:
    settings: CameraSettings
    restart_required: bool
    restart_performed: bool


class CameraProvider(ABC):
    @abstractmethod
    def get_settings(self) -> CameraSettings: ...

    @abstractmethod
    def apply_settings(self, settings: CameraSettings) -> ApplySettingsResult: ...

    @abstractmethod
    def next_frame(self) -> bytes: ...

    @abstractmethod
    def health(self) -> CameraHealth: ...

    @abstractmethod
    def capabilities_provider(self) -> str: ...

    @abstractmethod
    def last_frame_at(self) -> datetime | None: ...


class UnavailableCameraProvider(CameraProvider):
    def __init__(self, camera_id: str, provider: CameraProviderKind, settings: CameraSettings, reason: str) -> None:
        self.camera_id = camera_id
        self.provider = provider
        self._settings = settings
        self.reason = reason

    def get_settings(self) -> CameraSettings:
        return self._settings

    def apply_settings(self, settings: CameraSettings) -> ApplySettingsResult:
        self._settings = settings
        raise CameraProviderError(self.reason)

    def next_frame(self) -> bytes:
        raise CameraProviderError(self.reason)

    def health(self) -> CameraHealth:
        return CameraHealth(
            camera_id=self.camera_id,
            status="degraded",
            provider=self.provider,
            camera_ready=False,
            stream_ready=False,
            last_frame_at=None,
            uptime_seconds=0,
            software_version=__version__,
        )

    def capabilities_provider(self) -> str:
        return self.provider

    def last_frame_at(self) -> datetime | None:
        return None

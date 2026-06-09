from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Callable

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

    def last_frame_number(self) -> int | None:
        return None

    def restart(self) -> None:
        return None

    def close(self) -> None:
        return None


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


class RecoveringCameraProvider(CameraProvider):
    def __init__(
        self,
        factory: Callable[[CameraSettings], CameraProvider],
        camera_id: str,
        provider: CameraProviderKind,
        settings: CameraSettings,
        retry_interval_seconds: float = 5.0,
    ) -> None:
        self._factory = factory
        self.camera_id = camera_id
        self.provider = provider
        self._settings = settings
        self._retry_interval_seconds = retry_interval_seconds
        self._current: CameraProvider = UnavailableCameraProvider(
            camera_id=camera_id,
            provider=provider,
            settings=settings,
            reason="camera provider has not initialized yet",
        )
        self._last_error = "camera provider has not initialized yet"
        self._last_attempt_monotonic = 0.0
        self._lock = Lock()
        self._attempt_recovery(force=True)

    def _swap_current(self, provider: CameraProvider, error: str | None = None) -> None:
        previous = self._current
        self._current = provider
        if error is not None:
            self._last_error = error
        if previous is not provider:
            previous.close()

    def _attempt_recovery(self, force: bool = False) -> CameraProvider:
        with self._lock:
            now = __import__("time").monotonic()
            if not force and self._current.health().camera_ready:
                return self._current
            if not force and now - self._last_attempt_monotonic < self._retry_interval_seconds:
                return self._current
            self._last_attempt_monotonic = now
            try:
                provider = self._factory(self._settings)
            except CameraProviderError as exc:
                self._swap_current(
                    UnavailableCameraProvider(
                        camera_id=self.camera_id,
                        provider=self.provider,
                        settings=self._settings,
                        reason=str(exc),
                    ),
                    error=str(exc),
                )
            else:
                self._swap_current(provider)
        return self._current

    def _mark_unavailable(self, exc: CameraProviderError) -> None:
        with self._lock:
            self._swap_current(
                UnavailableCameraProvider(
                    camera_id=self.camera_id,
                    provider=self.provider,
                    settings=self._settings,
                    reason=str(exc),
                ),
                error=str(exc),
            )
            self._last_attempt_monotonic = 0.0

    def get_settings(self) -> CameraSettings:
        return self._settings

    def apply_settings(self, settings: CameraSettings) -> ApplySettingsResult:
        self._settings = settings
        provider = self._attempt_recovery()
        try:
            result = provider.apply_settings(settings)
        except CameraProviderError as exc:
            self._mark_unavailable(exc)
            raise
        self._settings = result.settings
        return result

    def next_frame(self) -> bytes:
        provider = self._attempt_recovery()
        try:
            return provider.next_frame()
        except CameraProviderError as exc:
            # If startup recovery already failed for this request, do not immediately
            # hammer the camera stack with a second init attempt.
            if not provider.health().camera_ready:
                self._mark_unavailable(exc)
                raise
            self._mark_unavailable(exc)
            provider = self._attempt_recovery(force=True)
            try:
                return provider.next_frame()
            except CameraProviderError as retry_exc:
                self._mark_unavailable(retry_exc)
                raise retry_exc

    def health(self) -> CameraHealth:
        return self._current.health()

    def capabilities_provider(self) -> str:
        return self.provider

    def last_frame_at(self) -> datetime | None:
        return self._current.last_frame_at()

    def close(self) -> None:
        self._current.close()

    def last_frame_number(self) -> int | None:
        getter = getattr(self._current, "last_frame_number", None)
        return getter() if callable(getter) else None

    def restart(self) -> None:
        with self._lock:
            self._current.close()
            self._current = UnavailableCameraProvider(
                camera_id=self.camera_id,
                provider=self.provider,
                settings=self._settings,
                reason="camera restart requested",
            )
            self._last_attempt_monotonic = 0.0
        self._attempt_recovery(force=True)

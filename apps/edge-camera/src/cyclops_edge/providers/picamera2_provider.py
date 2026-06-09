from __future__ import annotations

import logging
import sys
import time
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from cyclops_edge import __version__
from cyclops_edge.camera_provider import ApplySettingsResult, CameraProvider, CameraProviderError
from cyclops_edge.frame_overlay import annotate_frame
from cyclops_edge.models import CameraHealth, CameraSettings

logger = logging.getLogger(__name__)


def _load_picamera2():
    try:  # pragma: no cover - import depends on runtime
        from picamera2 import Picamera2 as runtime_picamera2  # type: ignore

        return runtime_picamera2
    except Exception:
        pass

    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    fallback_paths = [
        Path(f"/usr/lib/{version}/dist-packages"),
        Path("/usr/lib/python3/dist-packages"),
    ]
    for fallback_path in fallback_paths:
        if not fallback_path.exists():
            continue
        fallback = str(fallback_path)
        if fallback not in sys.path:
            sys.path.append(fallback)
        try:  # pragma: no cover - import depends on runtime
            from picamera2 import Picamera2 as runtime_picamera2  # type: ignore

            logger.info("Loaded picamera2 from system packages at %s", fallback_path)
            return runtime_picamera2
        except Exception:
            continue
    return None


Picamera2 = _load_picamera2()


class Picamera2Provider(CameraProvider):
    def __init__(self, camera_id: str, settings: CameraSettings) -> None:
        self.camera_id = camera_id
        self._settings = settings
        self._started_at = time.monotonic()
        self._last_frame_at: datetime | None = None
        self._camera = None
        self._frame_counter = 0
        if Picamera2 is None:
            raise CameraProviderError("picamera2 runtime is unavailable")

        try:
            self._camera = Picamera2()
            config = self._camera.create_video_configuration(
                main={"size": (settings.stream_width, settings.stream_height)}
            )
            self._camera.configure(config)
            self._camera.start()
        except Exception as exc:  # pragma: no cover - hardware specific
            logger.exception("Failed to initialize picamera2 provider")
            raise CameraProviderError(str(exc)) from exc

    def get_settings(self) -> CameraSettings:
        return self._settings

    def apply_settings(self, settings: CameraSettings) -> ApplySettingsResult:
        restart_required = any(
            getattr(self._settings, field) != getattr(settings, field)
            for field in ("stream_width", "stream_height", "frame_rate", "jpeg_quality")
        )
        if restart_required:
            try:
                assert self._camera is not None
                self._camera.stop()
                config = self._camera.create_video_configuration(
                    main={"size": (settings.stream_width, settings.stream_height)}
                )
                self._camera.configure(config)
                self._camera.start()
            except Exception as exc:  # pragma: no cover - hardware specific
                raise CameraProviderError(f"camera pipeline restart failed: {exc}") from exc
        self._settings = settings
        return ApplySettingsResult(settings=settings, restart_required=restart_required, restart_performed=restart_required)

    def next_frame(self) -> bytes:
        if self._camera is None:  # pragma: no cover - defensive
            raise CameraProviderError("camera not initialized")
        try:
            frame = self._camera.capture_buffer("main")
            image = self._camera.helpers.make_image(frame, self._camera.camera_configuration()["main"])
            self._last_frame_at = datetime.now(UTC)
            self._frame_counter += 1
            image = annotate_frame(
                image,
                camera_label=self.camera_id,
                frame_number=self._frame_counter,
                frame_rate=self._settings.frame_rate,
                width=self._settings.stream_width,
                height=self._settings.stream_height,
                captured_at=self._last_frame_at,
            )

            output = BytesIO()
            image.save(output, format="JPEG", quality=self._settings.jpeg_quality)
            return output.getvalue()
        except Exception as exc:  # pragma: no cover - hardware specific
            raise CameraProviderError(f"frame generation failed: {exc}") from exc

    def health(self) -> CameraHealth:
        stream_ready = self._last_frame_at is not None
        status = "online" if stream_ready else "degraded"
        return CameraHealth(
            camera_id=self.camera_id,
            status=status,
            provider="picamera2",
            camera_ready=self._camera is not None,
            stream_ready=stream_ready,
            last_frame_at=self._last_frame_at,
            uptime_seconds=int(time.monotonic() - self._started_at),
            software_version=__version__,
        )

    def capabilities_provider(self) -> str:
        return "picamera2"

    def last_frame_at(self) -> datetime | None:
        return self._last_frame_at

    def last_frame_number(self) -> int | None:
        return self._frame_counter

    def close(self) -> None:
        if self._camera is None:  # pragma: no cover - defensive
            return
        try:
            self._camera.stop()
        except Exception:  # pragma: no cover - hardware specific
            logger.exception("Failed to stop picamera2 provider cleanly")
        finally:
            self._camera = None

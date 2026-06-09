from __future__ import annotations

import io
import math
import time
from datetime import UTC, datetime

from PIL import Image, ImageDraw

from cyclops_edge import __version__
from cyclops_edge.camera_provider import ApplySettingsResult, CameraProvider
from cyclops_edge.frame_overlay import annotate_frame
from cyclops_edge.models import CameraHealth, CameraSettings


class MockCameraProvider(CameraProvider):
    def __init__(self, camera_id: str, camera_name: str, settings: CameraSettings) -> None:
        self.camera_id = camera_id
        self.camera_name = camera_name
        self._settings = settings
        self._started_at = time.monotonic()
        self._last_frame_at: datetime | None = None
        self._frame_counter = 0

    def get_settings(self) -> CameraSettings:
        return self._settings

    def apply_settings(self, settings: CameraSettings) -> ApplySettingsResult:
        restart_required = any(
            getattr(self._settings, field) != getattr(settings, field)
            for field in ("stream_width", "stream_height", "frame_rate", "jpeg_quality")
        )
        self._settings = settings
        return ApplySettingsResult(
            settings=settings,
            restart_required=restart_required,
            restart_performed=restart_required,
        )

    def next_frame(self) -> bytes:
        now = datetime.now(UTC)
        self._last_frame_at = now
        self._frame_counter += 1
        width = self._settings.stream_width
        height = self._settings.stream_height
        phase = int(time.time() * self._settings.frame_rate)
        image = Image.new("RGB", (width, height), color=(24, 28, 36))
        draw = ImageDraw.Draw(image)
        accent = int((math.sin(phase / 4) + 1) * 90)
        draw.rectangle((0, 0, width, height), outline=(accent, 200, 240), width=6)
        draw.rectangle((16, height - 56, width - 16, height - 24), outline=(accent, 200, 240), width=3)
        image = annotate_frame(
            image,
            camera_label=self.camera_name,
            frame_number=self._frame_counter,
            frame_rate=self._settings.frame_rate,
            width=width,
            height=height,
            captured_at=now,
        )
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=self._settings.jpeg_quality)
        return buffer.getvalue()

    def health(self) -> CameraHealth:
        return CameraHealth(
            camera_id=self.camera_id,
            status="online",
            provider="mock",
            camera_ready=True,
            stream_ready=True,
            last_frame_at=self._last_frame_at,
            uptime_seconds=int(time.monotonic() - self._started_at),
            software_version=__version__,
        )

    def capabilities_provider(self) -> str:
        return "mock"

    def last_frame_at(self) -> datetime | None:
        return self._last_frame_at

    def last_frame_number(self) -> int | None:
        return self._frame_counter

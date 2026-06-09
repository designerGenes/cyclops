from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock


@dataclass
class StoredFrame:
    jpeg_bytes: bytes
    captured_at: datetime
    frame_number: int


class FrameStore:
    def __init__(self, max_frames: int = 300) -> None:
        self._frames: deque[StoredFrame] = deque(maxlen=max_frames)
        self._lock = Lock()

    def append(self, jpeg_bytes: bytes, *, captured_at: datetime, frame_number: int) -> None:
        with self._lock:
            self._frames.append(StoredFrame(jpeg_bytes=jpeg_bytes, captured_at=captured_at, frame_number=frame_number))

    def latest(self) -> StoredFrame | None:
        with self._lock:
            return self._frames[-1] if self._frames else None

    def at_offset(self, seconds_ago: int) -> StoredFrame | None:
        if seconds_ago <= 0:
            return self.latest()
        target = datetime.now(UTC) - timedelta(seconds=seconds_ago)
        with self._lock:
            candidates = [frame for frame in self._frames if frame.captured_at <= target]
            if candidates:
                return candidates[-1]
            return self._frames[0] if self._frames else None

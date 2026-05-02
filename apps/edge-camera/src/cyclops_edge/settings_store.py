from __future__ import annotations

import json
import logging
from pathlib import Path

from cyclops_edge.models import CameraSettings

logger = logging.getLogger(__name__)


class SettingsStore:
    def __init__(self, path: Path, defaults: CameraSettings) -> None:
        self.path = path
        self.defaults = defaults

    def load(self) -> CameraSettings:
        if not self.path.exists():
            return self.defaults

        try:
            payload = json.loads(self.path.read_text())
            return CameraSettings.model_validate(payload)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Invalid persisted settings at %s: %s", self.path, exc)
            return self.defaults

    def save(self, settings: CameraSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(settings.model_dump_json(indent=2))
        temp_path.replace(self.path)

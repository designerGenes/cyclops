from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from cyclops_edge.camera_provider import CameraProvider, CameraProviderError, RecoveringCameraProvider
from cyclops_edge.config import EdgeConfig, get_config
from cyclops_edge.models import CameraSettings
from cyclops_edge.providers.mock_provider import MockCameraProvider
from cyclops_edge.providers.picamera2_provider import Picamera2Provider
from cyclops_edge.routes.health import router as health_router
from cyclops_edge.routes.settings import router as settings_router
from cyclops_edge.routes.stream import router as stream_router
from cyclops_edge.settings_store import SettingsStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EdgeState:
    config: EdgeConfig
    settings_store: SettingsStore
    provider: CameraProvider
    apply_lock: asyncio.Lock


def create_provider(config: EdgeConfig, settings: CameraSettings) -> CameraProvider:
    if config.camera_provider == "mock":
        return MockCameraProvider(config.camera_id, config.camera_name, settings)
    if config.camera_provider == "picamera2":
        return Picamera2Provider(config.camera_id, settings)
    raise CameraProviderError(f"unsupported camera provider: {config.camera_provider}")


def create_app(config: EdgeConfig | None = None) -> FastAPI:
    config = config or get_config()
    app = FastAPI(title="Cyclops Edge Camera", version="0.1.0")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    settings_store = SettingsStore(config.settings_path, config.default_settings())
    settings = settings_store.load()
    provider = RecoveringCameraProvider(
        factory=lambda active_settings: create_provider(config, active_settings),
        camera_id=config.camera_id,
        provider=config.camera_provider,
        settings=settings,
    )
    app.state.edge = EdgeState(
        config=config,
        settings_store=settings_store,
        provider=provider,
        apply_lock=asyncio.Lock(),
    )
    app.state.templates = templates
    app.include_router(stream_router)
    app.include_router(settings_router)
    app.include_router(health_router)
    return app


app = create_app()

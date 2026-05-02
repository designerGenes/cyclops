from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path("/Users/jadennation/DEV/01_active_projects/cyclops")


class CoordinatorConfig(BaseSettings):
    bind_host: str = Field(default="0.0.0.0", alias="CYCLOPS_BIND_HOST")
    port: int = Field(default=8060, alias="CYCLOPS_PORT")
    db_path: Path = Field(default=PROJECT_ROOT / "cyclops.dev.db", alias="CYCLOPS_DB_PATH")
    camera_registry_path: Path = Field(default=PROJECT_ROOT / "config/examples/cameras.example.yaml", alias="CYCLOPS_CAMERA_REGISTRY_PATH")
    static_dir: Path = Field(default=PROJECT_ROOT / "apps/coordinator-api/src/cyclops_coordinator/static", alias="CYCLOPS_STATIC_DIR")
    health_poll_interval_seconds: int = Field(default=10, alias="CYCLOPS_HEALTH_POLL_INTERVAL_SECONDS")
    health_poll_timeout_seconds: float = Field(default=2.0, alias="CYCLOPS_HEALTH_POLL_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_config() -> CoordinatorConfig:
    return CoordinatorConfig()

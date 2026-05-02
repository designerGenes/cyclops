from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from cyclops_coordinator.models import CameraStatusCacheRecord, Layout


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


class CoordinatorDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection = _connect(path)
        self.initialize()

    def initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS camera_status_cache (
                camera_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                last_seen_at TEXT NULL,
                software_version TEXT NULL,
                provider TEXT NULL,
                camera_ready INTEGER NULL,
                stream_ready INTEGER NULL,
                last_frame_at TEXT NULL,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS layouts (
                layout_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._connection
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def get_status_cache(self) -> dict[str, CameraStatusCacheRecord]:
        rows = self._connection.execute("SELECT * FROM camera_status_cache").fetchall()
        result: dict[str, CameraStatusCacheRecord] = {}
        for row in rows:
            result[row["camera_id"]] = CameraStatusCacheRecord(
                camera_id=row["camera_id"],
                status=row["status"],
                last_seen_at=_parse_datetime(row["last_seen_at"]),
                software_version=row["software_version"],
                provider=row["provider"],
                camera_ready=_parse_bool(row["camera_ready"]),
                stream_ready=_parse_bool(row["stream_ready"]),
                last_frame_at=_parse_datetime(row["last_frame_at"]),
                consecutive_failures=row["consecutive_failures"],
                updated_at=_parse_datetime(row["updated_at"]) or datetime.now(UTC),
            )
        return result

    def upsert_status(self, record: CameraStatusCacheRecord) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO camera_status_cache (
                    camera_id, status, last_seen_at, software_version, provider,
                    camera_ready, stream_ready, last_frame_at, consecutive_failures, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(camera_id) DO UPDATE SET
                    status=excluded.status,
                    last_seen_at=excluded.last_seen_at,
                    software_version=excluded.software_version,
                    provider=excluded.provider,
                    camera_ready=excluded.camera_ready,
                    stream_ready=excluded.stream_ready,
                    last_frame_at=excluded.last_frame_at,
                    consecutive_failures=excluded.consecutive_failures,
                    updated_at=excluded.updated_at
                """,
                (
                    record.camera_id,
                    record.status,
                    _to_iso(record.last_seen_at),
                    record.software_version,
                    record.provider,
                    _bool_int(record.camera_ready),
                    _bool_int(record.stream_ready),
                    _to_iso(record.last_frame_at),
                    record.consecutive_failures,
                    _to_iso(record.updated_at),
                ),
            )

    def get_layout(self, layout_id: str = "default") -> Layout | None:
        row = self._connection.execute(
            "SELECT payload FROM layouts WHERE layout_id = ?", (layout_id,)
        ).fetchone()
        if row is None:
            return None
        return Layout.model_validate(json.loads(row["payload"]))

    def save_layout(self, layout: Layout) -> Layout:
        payload = layout.model_dump(mode="json")
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO layouts (layout_id, payload, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(layout_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (layout.layout_id, json.dumps(payload), _to_iso(layout.updated_at)),
            )
        return layout


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _bool_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(value)

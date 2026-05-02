from __future__ import annotations

from datetime import UTC, datetime

from cyclops_coordinator.models import Layout, LayoutTile


def generate_default_layout(camera_ids: list[str]) -> Layout:
    return Layout(
        layout_id="default",
        tiles=[
            LayoutTile(camera_id=camera_id, order=index, height_px=240, visible=True)
            for index, camera_id in enumerate(camera_ids)
        ],
        updated_at=datetime.now(UTC),
    )


def reconcile_layout(layout: Layout, camera_ids: list[str]) -> Layout:
    known = set(camera_ids)
    remaining = [tile for tile in layout.tiles if tile.camera_id in known]
    existing_ids = {tile.camera_id for tile in remaining}
    remaining.extend(
        LayoutTile(camera_id=camera_id, order=0, height_px=240, visible=True)
        for camera_id in camera_ids
        if camera_id not in existing_ids
    )
    normalized = [
        LayoutTile(
            camera_id=tile.camera_id,
            order=index,
            height_px=max(180, min(720, tile.height_px)),
            visible=tile.visible,
        )
        for index, tile in enumerate(sorted(remaining, key=lambda tile: tile.order))
    ]
    return Layout(layout_id="default", tiles=normalized, updated_at=datetime.now(UTC))


def validate_layout_camera_ids(layout: Layout, camera_ids: list[str]) -> None:
    known = set(camera_ids)
    unknown = [tile.camera_id for tile in layout.tiles if tile.camera_id not in known]
    if unknown:
        raise KeyError(", ".join(unknown))

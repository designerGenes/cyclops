from __future__ import annotations

from datetime import UTC, datetime

from PIL import Image

from cyclops_edge.frame_overlay import annotate_frame


def test_annotate_frame_draws_live_metadata() -> None:
    image = Image.new("RGB", (320, 180), color=(0, 0, 0))

    annotated = annotate_frame(
        image,
        camera_label="Niles Crane",
        frame_number=42,
        frame_rate=5,
        width=320,
        height=180,
        captured_at=datetime(2026, 6, 9, 1, 0, 0, tzinfo=UTC),
    )

    assert annotated.size == (320, 180)
    assert annotated.getpixel((160, 24)) != (0, 0, 0)
    assert annotated.getpixel((30, 150)) != (0, 0, 0)

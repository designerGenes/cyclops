from __future__ import annotations

from datetime import UTC, datetime

from PIL import Image, ImageDraw, ImageFont


def annotate_frame(
    image: Image.Image,
    *,
    camera_label: str,
    frame_number: int,
    frame_rate: int,
    width: int,
    height: int,
    captured_at: datetime | None = None,
) -> Image.Image:
    captured_at = captured_at or datetime.now(UTC)
    annotated = image.convert("RGBA")
    draw = ImageDraw.Draw(annotated, "RGBA")
    font = ImageFont.load_default()

    top_panel = (12, 12, min(width - 12, 280), 76)
    bottom_panel = (12, max(12, height - 44), min(width - 12, 360), height - 12)
    draw.rounded_rectangle(top_panel, radius=12, fill=(15, 23, 42, 196))
    draw.rounded_rectangle(bottom_panel, radius=12, fill=(15, 23, 42, 196))
    draw.ellipse((24, 24, 36, 36), fill=(52, 211, 153, 255))
    draw.text((44, 22), f"LIVE  {camera_label}", fill=(248, 250, 252, 255), font=font)
    draw.text((24, 46), captured_at.strftime("%Y-%m-%d %H:%M:%S UTC"), fill=(191, 219, 254, 255), font=font)
    draw.text(
        (24, height - 36),
        f"frame {frame_number:06d}   {width}x{height}   {frame_rate} fps",
        fill=(226, 232, 240, 255),
        font=font,
    )
    return annotated.convert("RGB")

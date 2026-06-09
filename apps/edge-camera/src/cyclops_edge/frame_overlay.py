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

    top_panel = (width - min(width - 12, 196), 12, width - 12, 40)
    bottom_panel = (12, max(12, height - 34), min(width - 12, 276), height - 12)
    draw.rounded_rectangle(top_panel, radius=12, fill=(15, 23, 42, 168))
    draw.rounded_rectangle(bottom_panel, radius=12, fill=(15, 23, 42, 168))
    draw.ellipse((top_panel[0] + 12, 21, top_panel[0] + 20, 29), fill=(52, 211, 153, 255))
    draw.text((top_panel[0] + 28, 18), f"LIVE {camera_label}", fill=(248, 250, 252, 255), font=font)
    draw.text(
        (24, height - 28),
        f"{captured_at.strftime('%H:%M:%S')}  frame {frame_number:06d}  {width}x{height}  {frame_rate}fps",
        fill=(226, 232, 240, 255),
        font=font,
    )
    return annotated.convert("RGB")

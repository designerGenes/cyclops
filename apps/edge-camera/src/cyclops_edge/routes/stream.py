from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from cyclops_edge.camera_provider import CameraProviderError
from cyclops_edge.models import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _frame_headers(captured_at: datetime, frame_number: int | None = None) -> dict[str, str]:
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Accel-Buffering": "no",
        "X-Cyclops-Captured-At": captured_at.astimezone(UTC).isoformat(),
    }
    if frame_number is not None:
        headers["X-Cyclops-Frame-Number"] = str(frame_number)
    return headers


async def _capture_frame(state) -> tuple[bytes, datetime, int | None]:
    frame = await asyncio.to_thread(state.provider.next_frame)
    captured_at = state.provider.last_frame_at() or datetime.now(UTC)
    frame_number_getter = getattr(state.provider, "last_frame_number", None)
    frame_number = frame_number_getter() if callable(frame_number_getter) else None
    if frame_number is not None:
        state.frame_store.append(frame, captured_at=captured_at, frame_number=frame_number)
    return frame, captured_at, frame_number


@router.get("/stream")
async def stream(request: Request):
    state = request.app.state.edge
    provider = state.provider
    health = provider.health()
    single_frame = request.headers.get("x-cyclops-test-once") == "1"
    if not health.camera_ready:
        return JSONResponse(status_code=503, content=ErrorResponse(detail="camera unavailable").model_dump())

    try:
        first_frame, captured_at, frame_number = await _capture_frame(state)
    except CameraProviderError as exc:
        logger.warning("Stream unavailable: %s", exc)
        return JSONResponse(status_code=503, content=ErrorResponse(detail="stream unavailable").model_dump())

    async def frame_generator():
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + first_frame + b"\r\n"
        if single_frame:
            return

        while True:
            if await request.is_disconnected():
                break
            try:
                frame, _, _ = await _capture_frame(state)
            except CameraProviderError as exc:
                logger.warning("Stream unavailable: %s", exc)
                break
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(max(1 / provider.get_settings().frame_rate, 0.01))

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=_frame_headers(captured_at, frame_number),
    )


@router.get("/api/v1/frame")
async def frame_snapshot(request: Request, seconds_ago: int = 0):
    state = request.app.state.edge
    if seconds_ago > 0:
        stored_frame = state.frame_store.at_offset(seconds_ago)
        if stored_frame is None:
            return JSONResponse(status_code=404, content=ErrorResponse(detail="no buffered frame available").model_dump())
        return Response(
            content=stored_frame.jpeg_bytes,
            media_type="image/jpeg",
            headers=_frame_headers(stored_frame.captured_at, stored_frame.frame_number),
        )

    try:
        frame, captured_at, frame_number = await _capture_frame(state)
    except CameraProviderError as exc:
        return JSONResponse(status_code=503, content=ErrorResponse(detail=str(exc)).model_dump())
    return Response(content=frame, media_type="image/jpeg", headers=_frame_headers(captured_at, frame_number))


@router.post("/api/v1/stream/restart")
async def restart_stream(request: Request):
    state = request.app.state.edge
    if state.apply_lock.locked():
        return JSONResponse(status_code=409, content=ErrorResponse(detail="camera busy").model_dump())
    async with state.apply_lock:
        try:
            await asyncio.to_thread(state.provider.restart)
        except CameraProviderError as exc:
            return JSONResponse(status_code=500, content=ErrorResponse(detail=str(exc)).model_dump())
    return JSONResponse(status_code=200, content={"detail": "stream restarted"})

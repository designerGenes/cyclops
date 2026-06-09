from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from cyclops_edge.camera_provider import CameraProviderError
from cyclops_edge.models import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stream")
async def stream(request: Request):
    state = request.app.state.edge
    provider = state.provider
    health = provider.health()
    single_frame = request.headers.get("x-cyclops-test-once") == "1"
    if not health.camera_ready:
        return JSONResponse(status_code=503, content=ErrorResponse(detail="camera unavailable").model_dump())

    try:
        first_frame = await asyncio.to_thread(provider.next_frame)
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
                frame = await asyncio.to_thread(provider.next_frame)
            except CameraProviderError as exc:
                logger.warning("Stream unavailable: %s", exc)
                break
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(max(1 / provider.get_settings().frame_rate, 0.01))

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )

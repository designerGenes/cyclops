from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from cyclops_coordinator.layout_store import validate_layout_camera_ids
from cyclops_coordinator.models import Layout

router = APIRouter(prefix="/api/v1/layouts", tags=["layouts"])


@router.get("/default", response_model=Layout)
async def get_default_layout(request: Request) -> Layout:
    return request.app.state.services["get_layout"]()


@router.put("/default", response_model=Layout)
async def put_default_layout(request: Request, payload: Layout) -> Layout:
    camera_ids = [camera.id for camera in request.app.state.services["registry_cameras"]()]
    try:
        validate_layout_camera_ids(payload, camera_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown camera id referenced: {exc.args[0]}") from exc
    return request.app.state.services["save_layout"](payload)

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from cyclops_coordinator.models import CameraNode

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraNode])
async def list_cameras(request: Request) -> list[CameraNode]:
    return request.app.state.services["camera_view"]()


@router.get("/{camera_id}", response_model=CameraNode)
async def get_camera(camera_id: str, request: Request) -> CameraNode:
    for camera in request.app.state.services["camera_view"]():
        if camera.id == camera_id:
            return camera
    raise HTTPException(status_code=404, detail="unknown camera id")

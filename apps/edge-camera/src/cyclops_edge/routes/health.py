from __future__ import annotations

from fastapi import APIRouter, Request

from cyclops_edge.models import CameraHealth

router = APIRouter()


@router.get("/healthz", response_model=CameraHealth)
async def healthz(request: Request) -> CameraHealth:
    return request.app.state.edge.provider.health()

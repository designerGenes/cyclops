from __future__ import annotations

from fastapi import APIRouter, Request

from cyclops_coordinator.models import SystemStatus

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status", response_model=SystemStatus)
async def system_status(request: Request) -> SystemStatus:
    return request.app.state.services["system_status"]()

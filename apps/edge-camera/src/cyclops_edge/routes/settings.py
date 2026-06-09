from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from cyclops_edge.camera_provider import CameraBusyError, CameraProviderError
from cyclops_edge.models import CameraNode, CameraSettings, ErrorResponse, SettingsUpdateResponse

router = APIRouter()


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    state = request.app.state.edge
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "camera": build_camera_node(request),
            "settings": state.provider.get_settings(),
        },
    )


@router.get("/api/v1/settings", response_model=CameraSettings)
async def get_settings(request: Request) -> CameraSettings:
    return request.app.state.edge.provider.get_settings()


@router.put("/api/v1/settings", response_model=SettingsUpdateResponse)
async def put_settings(request: Request, payload: CameraSettings):
    state = request.app.state.edge
    if state.apply_lock.locked():
        return JSONResponse(status_code=409, content=ErrorResponse(detail="camera busy").model_dump())

    async with state.apply_lock:
        try:
            result = await asyncio.to_thread(state.provider.apply_settings, payload)
            state.settings_store.save(result.settings)
            return SettingsUpdateResponse(
                settings=result.settings,
                restart_required=result.restart_required,
                restart_performed=result.restart_performed,
            )
        except CameraBusyError:
            return JSONResponse(status_code=409, content=ErrorResponse(detail="camera busy").model_dump())
        except CameraProviderError as exc:
            return JSONResponse(status_code=500, content=ErrorResponse(detail=str(exc)).model_dump())


@router.get("/api/v1/camera", response_model=CameraNode)
async def get_camera(request: Request) -> CameraNode:
    return build_camera_node(request)


def build_camera_node(request: Request) -> CameraNode:
    state = request.app.state.edge
    config = state.config
    health = state.provider.health()
    base_url = str(request.base_url).rstrip("/")
    return CameraNode(
        id=config.camera_id,
        name=config.camera_name,
        hostname=config.hostname,
        tailscale_ip=config.tailscale_ip,
        stream_url=f"{base_url}/stream",
        settings_url=f"{base_url}/settings",
        health_url=f"{base_url}/healthz",
        status=health.status,
        last_seen_at=state.provider.last_frame_at(),
        software_version=health.software_version,
        capabilities={
            "provider": state.provider.capabilities_provider(),
            "stream_kind": "mjpeg",
            "supports_settings": True,
            "supports_future_analytics_ingest": True,
        },
    )

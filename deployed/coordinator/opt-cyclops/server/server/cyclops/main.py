from __future__ import annotations
import os
import time
from contextlib import asynccontextmanager

import requests as _rq
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .alerts import ALERT_DIR
from .config import load
from .detector import DetectorPool
from .mediamtx import CentralMTX
from .registry import Registry, SAFE_NAME
from .config import DATA_DIR

cfg = load()
registry = Registry(DATA_DIR)
mtx = CentralMTX(cfg.mediamtx_api)
pool = DetectorPool(cfg, registry)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-arm everything we knew before the restart.
    for node in registry.all():
        try:
            mtx.ensure_proxy(node.name, node.primary_rtsp)
        except Exception as e:
            print(f"[startup] mediamtx proxy for {node.name} failed: {e}", flush=True)
    pool.sync()
    yield


app = FastAPI(title="Cyclops", lifespan=lifespan)


class RegisterBody(BaseModel):
    name: str
    token: str
    host: str
    rtsp_port: int = 8554
    streams: dict[str, str] | None = None


class HeartbeatBody(BaseModel):
    name: str
    token: str
    temp_c: float = 0.0
    throttled: str = "0x0"
    tier: str = "full"
    uptime_s: int = 0


class LayoutBody(BaseModel):
    order: list[str] = []
    hidden: list[str] = []


class TierBody(BaseModel):
    tier: str = "auto"


class FpsBody(BaseModel):
    fps: str = "auto"


def _check_token(token: str) -> None:
    if token != cfg.enroll_token:
        raise HTTPException(403, "bad enroll token")


@app.post("/api/nodes/register")
def register(body: RegisterBody, request: Request):
    _check_token(body.token)
    host = body.host or (request.client.host if request.client else "")
    node = registry.upsert(body.name, host, body.rtsp_port, body.streams)
    try:
        mtx.ensure_proxy(node.name, node.primary_rtsp)
    except Exception as e:
        print(f"[register] mediamtx proxy failed for {node.name}: {e}", flush=True)
    pool.sync()
    return {"ok": True, "whep_path": f"cam_{node.name}"}


@app.post("/api/nodes/heartbeat")
def heartbeat(body: HeartbeatBody):
    _check_token(body.token)
    node = registry.heartbeat(body.name, body.temp_c, body.throttled,
                              body.tier, body.uptime_s)
    if node is None:
        raise HTTPException(404, "unknown node; re-register")
    return {"ok": True}


@app.get("/api/nodes")
def list_nodes():
    now = time.time()
    frames = pool.status()
    seen = pool.presence()
    return [{
        "name": n.name,
        "host": n.host,
        "whep_path": f"cam_{n.name}",
        "temp_c": n.temp_c,
        "throttled": n.throttled,
        "tier": n.tier,
        "uptime_s": n.uptime_s,
        "online": (now - n.last_seen) < cfg.node_offline_after_s,
        "detect_frame_age_s": (round(now - frames[n.name], 1)
                               if frames.get(n.name) else None),
        "person": bool(seen.get(n.name)
                       and (now - seen[n.name]) < cfg.detect.ui_hold_s),
        "person_age_s": (round(now - seen[n.name], 1)
                         if seen.get(n.name) else None),
    } for n in registry.all()]


@app.post("/api/nodes/{name}/tier")
def set_tier(name: str, body: TierBody):
    """Forward a manual quality override to the node's agent."""
    if not SAFE_NAME.match(name) or name not in {n.name for n in registry.all()}:
        raise HTTPException(404, "unknown node")
    node = next(n for n in registry.all() if n.name == name)
    try:
        r = _rq.post(f"http://{node.host}:8800/tier",
                     json={"tier": body.tier},
                     headers={"X-Camnode-Token": cfg.enroll_token}, timeout=5)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"node unreachable: {e}")
    return {"ok": True, "tier": body.tier}


@app.post("/api/nodes/{name}/fps")
def set_fps(name: str, body: FpsBody):
    if not SAFE_NAME.match(name) or name not in {n.name for n in registry.all()}:
        raise HTTPException(404, "unknown node")
    node = next(n for n in registry.all() if n.name == name)
    try:
        r = _rq.post(f"http://{node.host}:8800/fps",
                     json={"fps": body.fps},
                     headers={"X-Camnode-Token": cfg.enroll_token}, timeout=5)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"node unreachable: {e}")
    return {"ok": True, "fps": body.fps}


@app.get("/api/layout")
def get_layout():
    return registry.get_layout()


@app.put("/api/layout")
def put_layout(body: LayoutBody):
    registry.set_layout(body.model_dump())
    return {"ok": True}


@app.get("/alerts/{fname}")
def get_alert(fname: str):
    if "/" in fname or ".." in fname:
        raise HTTPException(400, "bad name")
    path = os.path.join(ALERT_DIR, fname)
    if not os.path.isfile(path):
        raise HTTPException(404, "no such alert")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/stream")
def stream_page():
    return FileResponse(os.path.join(STATIC_DIR, "stream.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

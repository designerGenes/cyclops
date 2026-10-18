from __future__ import annotations
import os
import threading
import time
from contextlib import asynccontextmanager

import requests as _rq
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
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

# --- stream-health sampling -------------------------------------------------
# The iris must reflect real video flow, not just heartbeat liveness. We treat
# a path as "streaming" when MediaMTX reports it ready AND its byte counter has
# advanced since the last sample. Debounced so bursty polling from several
# browsers stays cheap and stable.
_health_lock = threading.Lock()
_health: dict[str, tuple[float, int, bool, int]] = {}   # name -> (ts, bytes, ok, fail_streak)
_HEALTH_MIN_DT = 1.5
_HEALTH_FAIL_STREAK = 2


def _stream_ready(name: str) -> bool:
    now = time.time()
    with _health_lock:
        prev = _health.get(name)
        if prev and (now - prev[0]) < _HEALTH_MIN_DT:
            return prev[2]
    ready, nbytes = mtx.path_state(name)
    with _health_lock:
        prev = _health.get(name)
        if prev is None:
            ok = ready
            streak = 0 if ok else 1
        else:
            bytes_advanced = nbytes > prev[1]
            if ready and bytes_advanced:
                ok = True
                streak = 0
            elif ready:
                streak = prev[3] + 1
                ok = streak < _HEALTH_FAIL_STREAK
            else:
                ok = False
                streak = prev[3] + 1
        _health[name] = (now, nbytes, ok, streak)
        return ok


# Raspberry Pi throttle/undervolt bitmask (from vcgencmd get_throttled).
_UNDERVOLT = 0x1 | 0x10000      # now | has-occurred
_THROTTLE_NOW = 0x1 | 0x4       # undervolt-now | throttled-now


def _parse_throttle(val: str) -> int:
    try:
        return int(val, 16)
    except (TypeError, ValueError):
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-arm everything we knew before the restart.
    # Create proxy paths synchronously before accepting connections.
    for node in registry.all():
        try:
            mtx.ensure_proxy(node.name, node.primary_rtsp)
        except Exception as e:
            print(f"[startup] mediamtx proxy for {node.name} failed: {e}", flush=True)
    pool.sync()
    threading.Thread(target=_lan_fallback_loop, daemon=True,
                     name="lan-fallback").start()
    threading.Thread(target=_thermal_alert_loop, daemon=True,
                     name="thermal-alert").start()
    print("[startup] all proxy paths ready, accepting connections", flush=True)
    yield


# --- LAN-direct pull with tailnet fallback -------------------------------
# Proxies prefer the node's LAN address (no WireGuard crypto per frame on
# the thermally-limited eye). If the LAN route breaks, fall back to the
# tailnet route after 3 consecutive failed readiness checks (90 s); while on
# the tailnet route, retry the LAN route at most every 10 minutes. MediaMTX
# paths added through its API are runtime-only, so also recreate a missing
# proxy after MediaMTX restarts independently of Cyclops.
_LAN_FAILS_BEFORE_FALLBACK = 3
_LAN_RETRY_S = 600.0
_lan_state: dict[str, dict] = {}      # name -> {fails, next_lan_retry}


def _lan_fallback_loop():
    while True:
        for node in registry.all():
            try:
                ready, _ = mtx.path_state(node.name)
                st = _lan_state.setdefault(
                    node.name, {"fails": 0, "next_lan_retry": 0.0})
                if ready:
                    st["fails"] = 0
                    continue
                st["fails"] += 1
                source = mtx.source_of(node.name)
                if not source:
                    print(f"[proxy-recovery] {node.name}: central path missing — recreating {node.primary_rtsp}", flush=True)
                    mtx.ensure_proxy(node.name, node.primary_rtsp)
                    with _health_lock:
                        _health.pop(node.name, None)
                    st["fails"] = 0
                    st["next_lan_retry"] = 0.0
                    continue
                if st["fails"] < _LAN_FAILS_BEFORE_FALLBACK:
                    continue
                on_lan = bool(node.lan_host) and source == node.primary_rtsp
                if on_lan:
                    print(f"[lan-fallback] {node.name}: LAN route "
                          f"{node.primary_rtsp} not ready — switching to tailnet",
                          flush=True)
                    mtx.ensure_proxy(node.name, node.tailnet_primary_rtsp)
                    with _health_lock:
                        _health.pop(node.name, None)
                elif node.lan_host and source == node.tailnet_primary_rtsp:
                    if time.time() >= st["next_lan_retry"]:
                        st["next_lan_retry"] = time.time() + _LAN_RETRY_S
                        print(f"[lan-fallback] {node.name}: retrying LAN route "
                              f"{node.primary_rtsp}", flush=True)
                        mtx.ensure_proxy(node.name, node.primary_rtsp)
                        with _health_lock:
                            _health.pop(node.name, None)
            except Exception as e:
                print(f"[lan-fallback] {node.name}: {e}", flush=True)
        time.sleep(30)


# --- thermal watchdog ------------------------------------------------------
# Alert when a node has been at critical tier for 10+ minutes straight, so
# heat gets noticed before it becomes a red stream. Uses the same Twilio
# channel (and cooldowns) as person alerts.
_HOT_SUSTAINED_S = 600.0
_hot_since: dict[str, float] = {}


def _thermal_alert_loop():
    while True:
        now = time.time()
        for n in registry.all():
            try:
                if n.tier == "critical":
                    since = _hot_since.setdefault(n.name, now)
                    if now - since >= _HOT_SUSTAINED_S:
                        pool.alerts.thermal_alert(n)
                        _hot_since[n.name] = now   # rely on alert cooldown too
                else:
                    _hot_since.pop(n.name, None)
            except Exception as e:
                print(f"[thermal-alert] {n.name}: {e}", flush=True)
        time.sleep(60)


app = FastAPI(title="Cyclops", lifespan=lifespan)


class RegisterBody(BaseModel):
    name: str
    token: str
    host: str
    lan_host: str = ""
    rtsp_port: int = 8554
    streams: dict[str, str] | None = None


class HeartbeatBody(BaseModel):
    name: str
    token: str
    temp_c: float = 0.0
    throttled: str = "0x0"
    tier: str = "full"
    uptime_s: int = 0
    lan_host: str = ""


class LayoutBody(BaseModel):
    order: list[str] = []
    hidden: list[str] = []


class TierBody(BaseModel):
    tier: str = "auto"


class FpsBody(BaseModel):
    fps: str = "auto"


class RotationBody(BaseModel):
    rotation: int = 0


def _check_token(token: str) -> None:
    if token != cfg.enroll_token:
        raise HTTPException(403, "bad enroll token")


@app.post("/api/nodes/register")
def register(body: RegisterBody, request: Request):
    _check_token(body.token)
    host = body.host or (request.client.host if request.client else "")
    node = registry.upsert(body.name, host, body.rtsp_port, body.streams,
                           lan_host=body.lan_host)
    try:
        mtx.ensure_proxy(node.name, node.primary_rtsp)
    except Exception as e:
        print(f"[register] mediamtx proxy failed for {node.name}: {e}", flush=True)
    pool.sync()
    return {"ok": True, "whep_path": f"cam_{node.name}"}


@app.post("/api/nodes/heartbeat")
def heartbeat(body: HeartbeatBody):
    _check_token(body.token)
    # Snapshot BEFORE registry.heartbeat mutates the shared Node object.
    prev_lan = next((n.lan_host for n in registry.all()
                     if n.name == body.name), "")
    node = registry.heartbeat(body.name, body.temp_c, body.throttled,
                              body.tier, body.uptime_s,
                              lan_host=body.lan_host)
    if node is None:
        raise HTTPException(404, "unknown node; re-register")
    # First time we learn the node's LAN address (or it changed): move both
    # the central proxy and the detect watcher onto the cheaper LAN route.
    if body.lan_host and body.lan_host != prev_lan:
        try:
            mtx.ensure_proxy(node.name, node.primary_rtsp)
            with _health_lock:
                _health.pop(node.name, None)
            pool.restart_watcher(node.name)
            print(f"[heartbeat] {node.name}: switched to LAN route "
                  f"{node.primary_rtsp}", flush=True)
        except Exception as e:
            print(f"[heartbeat] {node.name}: LAN switch failed: {e}", flush=True)
    return {"ok": True}


@app.get("/api/nodes")
def list_nodes():
    now = time.time()
    frames = pool.status()
    seen = pool.presence()
    out = []
    for n in registry.all():
        online = (now - n.last_seen) < cfg.node_offline_after_s
        flags = _parse_throttle(n.throttled)
        out.append({
            "name": n.name,
            "host": n.host,
            "whep_path": f"cam_{n.name}",
            "temp_c": n.temp_c,
            "throttled": n.throttled,
            "tier": n.tier,
            "uptime_s": n.uptime_s,
            "rotation": n.rotation,
            "online": online,
            "heartbeat_age_s": round(now - n.last_seen, 1),
            "stream_ready": _stream_ready(n.name) if online else False,
            "undervolt": bool(flags & _UNDERVOLT),
            "power_warn": bool(flags & _THROTTLE_NOW),
            "detect_frame_age_s": (round(now - frames[n.name], 1)
                                   if frames.get(n.name) else None),
            "person": bool(seen.get(n.name)
                           and (now - seen[n.name]) < cfg.detect.ui_hold_s),
            "person_age_s": (round(now - seen[n.name], 1)
                             if seen.get(n.name) else None),
        })
    return out


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


@app.post("/api/nodes/{name}/rotation")
def set_rotation(name: str, body: RotationBody):
    """Persist a per-node display rotation (0/90/180/270). Display-only:
    the eyes keep publishing the same RTSP stream; the browser rotates it."""
    if not SAFE_NAME.match(name) or name not in {n.name for n in registry.all()}:
        raise HTTPException(404, "unknown node")
    node = registry.set_rotation(name, body.rotation)
    if node is None:
        raise HTTPException(404, "unknown node")
    # Also tell the eye so its burned-in timestamp counter-rotates to stay
    # upright in the viewer. Non-fatal: the registry remains the source of truth.
    try:
        _rq.post(f"http://{node.host}:8800/rotation",
                 json={"rotation": str(body.rotation)},
                 headers={"X-Camnode-Token": cfg.enroll_token}, timeout=5)
    except Exception as e:
        print(f"[rotation] {name}: OSD rotation update failed: {e}", flush=True)
    return {"ok": True, "rotation": node.rotation}


@app.post("/api/nodes/{name}/restart-proxy")
def restart_proxy(name: str):
    if not SAFE_NAME.match(name) or name not in {n.name for n in registry.all()}:
        raise HTTPException(404, "unknown node")
    node = next(n for n in registry.all() if n.name == name)
    try:
        mtx.restart_proxy(node.name, node.primary_rtsp)
    except Exception as e:
        raise HTTPException(502, f"proxy restart failed: {e}")
    with _health_lock:
        _health.pop(name, None)
    return {"ok": True}


@app.get("/api/debug/detect/{name}")
def debug_detect(name: str, threshold: float | None = None):
    """Run the detector against the latest frame from one eye (diagnostics)."""
    w = pool.watchers.get(name)
    if w is None or w.last_frame is None:
        raise HTTPException(404, "no watcher/frame for that node")
    detector = pool.detector
    saved = getattr(detector, "score_threshold", None)
    if threshold is not None and saved is not None:
        detector.score_threshold = threshold
    try:
        boxes = detector.detect(w.last_frame)
    finally:
        if saved is not None:
            detector.score_threshold = saved
    return {
        "ok": True,
        "node": name,
        "detector": detector.name,
        "threshold": threshold,
        "frame_age_s": round(time.time() - w.last_frame_at, 2),
        "box_count": len(boxes),
        "boxes": [[int(b[0]), int(b[1]), int(b[2]), int(b[3]),
                   round(float(b[4]), 3)] for b in boxes],
    }


@app.get("/api/debug/frame/{name}")
def debug_frame(name: str):
    """Return the exact frame the detector last analysed (JPEG)."""
    import cv2
    w = pool.watchers.get(name)
    if w is None or w.last_frame is None:
        raise HTTPException(404, "no watcher/frame for that node")
    ok, buf = cv2.imencode(".jpg", w.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise HTTPException(500, "encode failed")
    return Response(content=buf.tobytes(), media_type="image/jpeg")


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

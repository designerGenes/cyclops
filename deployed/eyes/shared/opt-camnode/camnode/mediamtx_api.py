"""Tiny stdlib client for the node-local MediaMTX control API."""
from __future__ import annotations
import json
import urllib.request

BASE = "http://127.0.0.1:9997/v3"

# The brain samples the detect stream at 4 fps — anything above that is
# pure MJPEG-encode heat on the eye for frames nobody looks at.
DETECT_FPS_CAP = 4


def _req(method: str, url: str, payload: dict | None = None) -> dict | None:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read()
        return json.loads(body) if body else None


def patch_path(name: str, fields: dict) -> None:
    """Hot-apply rpiCamera parameter changes to a running path."""
    _req("PATCH", f"{BASE}/config/paths/patch/{name}", fields)


def get_path_config(name: str) -> dict:
    d = _req("GET", f"{BASE}/config/paths/get/{name}")
    return d if isinstance(d, dict) else {}


def tier_cam_fields(tier: dict) -> dict:
    return {
        "rpiCameraWidth": tier["width"],
        "rpiCameraHeight": tier["height"],
        "rpiCameraFPS": tier["fps"],
        "rpiCameraBitrate": tier["bitrate"],
        "rpiCameraIDRPeriod": max(1, tier["fps"]),
    }


def tier_detect_fields(tier: dict) -> dict:
    fps = min(tier["fps"], DETECT_FPS_CAP)
    return {
        "rpiCameraFPS": fps,
        "rpiCameraIDRPeriod": max(1, fps),
    }


def apply_cam(fields: dict) -> None:
    patch_path("cam", fields)


def apply_tier(tier: dict) -> None:
    patch_path("cam", tier_cam_fields(tier))
    patch_path("detect", tier_detect_fields(tier))


def tier_drifted(tier: dict) -> bool:
    """True if the running path parameters differ from the tier's.

    A MediaMTX restart (agent-initiated encoder recovery, operator action,
    reboot) reloads the on-disk file, which boots the camera at full-tier
    parameters even when the governor has demoted the node — and no tier
    transition will ever fire to correct it. This detects that drift.
    """
    cam_want = tier_cam_fields(tier)
    detect_want = tier_detect_fields(tier)
    try:
        cam_cur = get_path_config("cam")
        detect_cur = get_path_config("detect")
    except Exception:
        return False  # mediamtx likely down/restarting; retry next tick
    if not cam_cur:
        return False
    if any(cam_cur.get(k) != v for k, v in cam_want.items()):
        return True
    if detect_cur and any(detect_cur.get(k) != v for k, v in detect_want.items()):
        return True
    return False


def apply_tier_if_drifted(tier: dict) -> bool:
    """Re-apply the tier only when runtime params have drifted.

    Every PATCH restarts the camera source, so never patch speculatively —
    only when the running config genuinely differs from the tier.
    """
    if not tier_drifted(tier):
        return False
    apply_tier(tier)
    return True


def healthy() -> bool:
    try:
        _req("GET", f"{BASE}/paths/list")
        return True
    except Exception:
        return False


def path_ready(name: str) -> bool:
    """True if the local MediaMTX path has its source connected/publishing."""
    try:
        d = _req("GET", f"{BASE}/paths/get/{name}")
        return bool(d and d.get("ready"))
    except Exception:
        return False
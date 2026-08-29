"""Client for the CENTRAL MediaMTX on the Pi 5. For each registered eye we
add a proxy path cam_<name> that pulls the node's primary RTSP feed; the
browser then plays it over WebRTC (WHEP) from the Pi 5 only. The pull is kept
warm at all times (resilience > saving a trickle of WiFi), so reloads never
race a cold start and stream health is always observable.
"""
from __future__ import annotations
import requests


class CentralMTX:
    def __init__(self, api_base: str) -> None:
        # cfg.mediamtx_api points at the API version root, e.g.
        # http://127.0.0.1:9997/v3. Keep endpoint paths relative to that base.
        self.base = api_base.rstrip("/")

    def _proxy_body(self, source_rtsp: str) -> dict:
        # NOT on-demand: keep the primary pulled at all times. A reload can
        # never race a cold source start, and the brain can always measure
        # whether video is actually flowing (see path_state).
        return {
            "source": source_rtsp,
            "sourceOnDemand": False,
            "rtspTransport": "tcp",
        }

    def ensure_proxy(self, name: str, source_rtsp: str) -> None:
        """Create the proxy if missing; patch only if the source changed.
        A no-op when nothing changed — so an eye re-registering never reloads
        the path and never drops the live viewers watching it."""
        path = f"cam_{name}"
        body = self._proxy_body(source_rtsp)
        try:
            g = requests.get(f"{self.base}/config/paths/get/{path}", timeout=5)
            if g.status_code == 200:
                if (g.json() or {}).get("source") == source_rtsp:
                    return  # already correct: leave the running path untouched
                requests.patch(f"{self.base}/config/paths/patch/{path}",
                               json=body, timeout=5).raise_for_status()
                return
        except requests.RequestException:
            pass  # fall through and try to add
        r = requests.post(f"{self.base}/config/paths/add/{path}",
                          json=body, timeout=5)
        if r.status_code == 400 and "already exists" in r.text:
            requests.patch(f"{self.base}/config/paths/patch/{path}",
                           json=body, timeout=5).raise_for_status()
        else:
            r.raise_for_status()

    def path_state(self, name: str) -> tuple[bool, int]:
        """(ready, bytes_received) for cam_<name> from the runtime API.
        ready=True means MediaMTX has the source connected and publishing."""
        try:
            r = requests.get(f"{self.base}/paths/get/cam_{name}", timeout=3)
            if r.status_code != 200:
                return (False, 0)
            d = r.json() or {}
            return (bool(d.get("ready")), int(d.get("bytesReceived") or 0))
        except (requests.RequestException, ValueError):
            return (False, 0)

    def remove_proxy(self, name: str) -> None:
        requests.delete(f"{self.base}/config/paths/delete/cam_{name}", timeout=5)

    def restart_proxy(self, name: str, source_rtsp: str) -> None:
        self.remove_proxy(name)
        body = self._proxy_body(source_rtsp)
        r = requests.post(f"{self.base}/config/paths/add/cam_{name}",
                          json=body, timeout=5)
        r.raise_for_status()

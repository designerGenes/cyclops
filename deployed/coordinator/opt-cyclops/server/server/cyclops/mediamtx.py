"""Client for the CENTRAL MediaMTX on the Pi 5. For each registered eye
we add a proxy path cam_<name> that pulls the node's primary RTSP feed
on demand; browsers then play it over WebRTC (WHEP) from the Pi 5 only.
"""
from __future__ import annotations
import requests


class CentralMTX:
    def __init__(self, api_base: str) -> None:
        self.base = api_base.rstrip("/")

    def ensure_proxy(self, name: str, source_rtsp: str) -> None:
        path = f"cam_{name}"
        body = {
            "source": source_rtsp,
            "sourceOnDemand": True,        # only pull while someone watches
            "rtspTransport": "tcp",
            "sourceOnDemandCloseAfter": "30s",
        }
        r = requests.post(f"{self.base}/config/paths/add/{path}",
                          json=body, timeout=5)
        if r.status_code == 400 and "already exists" in r.text:
            requests.patch(f"{self.base}/config/paths/patch/{path}",
                           json=body, timeout=5)
        else:
            r.raise_for_status()

    def remove_proxy(self, name: str) -> None:
        requests.delete(f"{self.base}/config/paths/delete/cam_{name}", timeout=5)

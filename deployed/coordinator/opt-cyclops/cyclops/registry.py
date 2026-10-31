from __future__ import annotations
import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field

SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")


@dataclass
class Node:
    name: str
    host: str
    rtsp_port: int = 8554
    primary_path: str = "cam"
    detect_path: str = "detect"
    lan_host: str = ""            # LAN IPv4 reported by the node, "" = none
    registered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    temp_c: float = 0.0
    throttled: str = "0x0"
    tier: str = "full"
    uptime_s: int = 0
    rotation: int = 0             # display rotation in degrees: 0/90/180/270
    notify: bool = True           # send presence alerts for this camera
    osd_scale: int = 6            # timestamp glyph scale (3..12)
    osd_color: int = 0            # timestamp color mode (0=white,1=cycle,2..6 hues)

    # RTSP endpoints prefer the LAN route (no per-packet WireGuard crypto
    # on the thermally-limited eye); the tailnet route is the fallback.
    @property
    def rtsp_host(self) -> str:
        return self.lan_host or self.host

    @property
    def primary_rtsp(self) -> str:
        return f"rtsp://{self.rtsp_host}:{self.rtsp_port}/{self.primary_path}"

    @property
    def detect_rtsp(self) -> str:
        return f"rtsp://{self.rtsp_host}:{self.rtsp_port}/{self.detect_path}"

    @property
    def tailnet_primary_rtsp(self) -> str:
        return f"rtsp://{self.host}:{self.rtsp_port}/{self.primary_path}"


class Registry:
    """Thread-safe node registry, persisted to JSON so a Cyclops restart
    keeps every known eye."""

    def __init__(self, data_dir: str) -> None:
        self.path = os.path.join(data_dir, "registry.json")
        self.layout_path = os.path.join(data_dir, "layout.json")
        self.lock = threading.RLock()
        self.nodes: dict[str, Node] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path) as f:
                for item in json.load(f):
                    n = Node(**item)
                    self.nodes[n.name] = n
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump([asdict(n) for n in self.nodes.values()], f, indent=2)
        os.replace(tmp, self.path)

    def upsert(self, name: str, host: str, rtsp_port: int,
               streams: dict | None = None, lan_host: str = "") -> Node:
        if not SAFE_NAME.match(name):
            raise ValueError("node name must match [a-zA-Z0-9_-]{1,40}")
        with self.lock:
            n = self.nodes.get(name) or Node(name=name, host=host)
            n.host, n.rtsp_port = host, rtsp_port
            if lan_host:
                n.lan_host = lan_host
            if streams:
                n.primary_path = streams.get("primary", n.primary_path)
                n.detect_path = streams.get("detect", n.detect_path)
            n.last_seen = time.time()
            self.nodes[name] = n
            self._save()
            return n

    def heartbeat(self, name: str, temp_c: float, throttled: str,
                  tier: str, uptime_s: int,
                  lan_host: str = "") -> Node | None:
        with self.lock:
            n = self.nodes.get(name)
            if not n:
                return None
            n.last_seen = time.time()
            n.temp_c, n.throttled, n.tier, n.uptime_s = temp_c, throttled, tier, uptime_s
            if lan_host and lan_host != n.lan_host:
                n.lan_host = lan_host
                self._save()      # persist the LAN route across restarts
            return n

    def set_rotation(self, name: str, rotation: int) -> Node | None:
        """Persist a node's display rotation, snapped to 90° increments."""
        with self.lock:
            n = self.nodes.get(name)
            if not n:
                return None
            n.rotation = (int(rotation) % 360 // 90) * 90
            self._save()
            return n

    def set_notify(self, name: str, enabled: bool) -> Node | None:
        """Enable/disable presence notifications for one camera."""
        with self.lock:
            n = self.nodes.get(name)
            if not n:
                return None
            n.notify = bool(enabled)
            self._save()
            return n

    def set_osd(self, name: str, scale: int, color: int) -> Node | None:
        """Persist a node's timestamp scale (3..12) and color mode."""
        with self.lock:
            n = self.nodes.get(name)
            if not n:
                return None
            n.osd_scale = max(3, min(12, int(scale)))
            n.osd_color = max(0, min(6, int(color)))
            self._save()
            return n

    def all(self) -> list[Node]:
        with self.lock:
            return list(self.nodes.values())

    # ---- UI layout (tile order / hidden), persisted server-side so
    # every browser sees the same stack ----
    def get_layout(self) -> dict:
        try:
            with open(self.layout_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"order": [], "hidden": []}

    def set_layout(self, layout: dict) -> None:
        os.makedirs(os.path.dirname(self.layout_path), exist_ok=True)
        with open(self.layout_path, "w") as f:
            json.dump({
                "order": [str(x) for x in layout.get("order", [])],
                "hidden": [str(x) for x in layout.get("hidden", [])],
            }, f, indent=2)

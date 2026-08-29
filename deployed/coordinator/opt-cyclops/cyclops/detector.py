"""One watcher thread per eye. Each thread holds an RTSP connection to
the node's low-res /detect stream (decoded on the Pi 5's A76 cores —
cheap at 640x360), samples frames at ~sample_fps, and runs the shared
NPU detector. `consecutive_hits` frames with a person triggers an alert.

Resilience: capture failures back off and reconnect forever; a node
going dark never affects the other watchers.
"""
from __future__ import annotations
import os
import threading
import time

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                      "rtsp_transport;tcp|stimeout;5000000")

import cv2  # noqa: E402  (env var must precede import)

from .alerts import AlertManager
from .config import Cfg
from .hailo_infer import make_detector
from .registry import Node, Registry


class Watcher(threading.Thread):
    def __init__(self, node: Node, pool: "DetectorPool") -> None:
        super().__init__(daemon=True, name=f"watch-{node.name}")
        self.node = node
        self.pool = pool
        self.stop_flag = threading.Event()
        self.hits = 0
        self.last_frame_at = 0.0
        self.last_person_at = 0.0          # UI presence latch (debounced)

    def run(self) -> None:
        backoff = 2.0
        period = 1.0 / max(0.5, self.pool.cfg.detect.sample_fps)
        while not self.stop_flag.is_set():
            # Re-read each reconnect: the brain may have switched the node
            # between its LAN and tailnet routes.
            url = self.node.detect_rtsp
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                time.sleep(backoff)
                backoff = min(backoff * 1.6, 30.0)
                continue
            backoff = 2.0
            print(f"[watch:{self.node.name}] connected {url}", flush=True)
            last_sample = 0.0
            while not self.stop_flag.is_set():
                ok = cap.grab()                       # drain at stream fps
                if not ok:
                    print(f"[watch:{self.node.name}] stream lost; reconnecting",
                          flush=True)
                    break
                now = time.monotonic()
                if now - last_sample < period:
                    continue
                last_sample = now
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    continue
                self.last_frame_at = time.time()
                self._analyze(frame)
            cap.release()
            time.sleep(1.0)

    def _analyze(self, frame) -> None:
        try:
            boxes = self.pool.detector.detect(frame)
        except Exception as e:
            print(f"[watch:{self.node.name}] inference error: {e}", flush=True)
            return
        if boxes:
            self.hits += 1
            if self.hits >= self.pool.cfg.detect.consecutive_hits:
                # Latch presence for the /stream UI. Refreshed every hit
                # while a person stays in frame, so it never flickers; it
                # decays on its own ui_hold_s after they leave. Kept
                # separate from maybe_alert so the tile still lights up
                # during the (much longer) SMS cooldown.
                self.last_person_at = time.time()
                self.pool.alerts.maybe_alert(
                    self.node.name, frame, boxes, self.pool.detector.name)
        else:
            self.hits = 0


class DetectorPool:
    def __init__(self, cfg: Cfg, registry: Registry) -> None:
        self.cfg = cfg
        self.registry = registry
        self.alerts = AlertManager(cfg)
        self.detector = make_detector(cfg.detect.hef_path,
                                      cfg.detect.score_threshold)
        self.watchers: dict[str, Watcher] = {}
        self._lock = threading.Lock()

    def sync(self) -> None:
        """Ensure exactly one live watcher per registered node."""
        with self._lock:
            for node in self.registry.all():
                w = self.watchers.get(node.name)
                if w is None or not w.is_alive():
                    w = Watcher(node, self)
                    self.watchers[node.name] = w
                    w.start()

    def restart_watcher(self, name: str) -> None:
        """Bounce a watcher so it picks up the node's current RTSP route
        (e.g. after the registry learned or changed its LAN address)."""
        with self._lock:
            w = self.watchers.get(name)
            if w:
                w.stop_flag.set()
        self.sync()

    def status(self) -> dict[str, float]:
        return {name: w.last_frame_at for name, w in self.watchers.items()}

    def presence(self) -> dict[str, float]:
        return {name: w.last_person_at for name, w in self.watchers.items()}

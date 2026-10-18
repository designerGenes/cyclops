"""One watcher thread per eye. Each thread holds an RTSP connection to
the node's low-res /detect stream (decoded on the Pi 5's A76 cores —
cheap at 640x360), samples frames at ~sample_fps, and runs the shared
NPU detector. `consecutive_hits` frames with a person triggers an alert.

Resilience: capture failures back off and reconnect forever; a node
going dark never affects the other watchers.
"""
from __future__ import annotations
import json
import os
import subprocess
import threading
import time
from collections import deque

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                      "rtsp_transport;tcp|stimeout;5000000")

import cv2  # noqa: E402  (env var must precede import)

from .alerts import AlertManager
from .config import Cfg, DATA_DIR
from .hailo_infer import make_detector
from .registry import Node, Registry


class Watcher(threading.Thread):
    def __init__(self, node: Node, pool: "DetectorPool") -> None:
        super().__init__(daemon=True, name=f"watch-{node.name}")
        self.node = node
        self.pool = pool
        self.stop_flag = threading.Event()
        self.hits = 0
        self.hit_times: deque[float] = deque()   # sliding-window hits
        self.last_frame = None                    # latest decoded frame (debug)
        self.last_frame_at = 0.0
        self.last_person_at = 0.0          # UI presence latch (debounced)
        # ISP-wedge watchdog state
        self.last_good_at = 0.0
        self.bad_since = 0.0
        self.last_recover_at = 0.0
        self.wedge_count = 0

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
                self._watchdog(frame)
                self._analyze(frame)
            cap.release()
            time.sleep(1.0)

    def _watchdog(self, frame) -> None:
        """Detect a wedged ISP (frozen AE/AWB) and bounce the eye.

        A healthy frame is roughly colour-balanced and has real tonal spread.
        When the ISP params stop applying, AE/AWB freeze: the picture goes
        either strongly colour-cast (\"lemonade\") or dark-and-flat. We only act
        on a healthy->bad transition so a legitimately dark night scene (which
        was never healthy) is left alone.
        """
        wd = self.pool.cfg.watchdog
        if not wd.enabled:
            return
        now = time.time()
        try:
            b, g, r, _ = cv2.mean(frame)
            luma = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            s = float(luma.std())
        except Exception:
            return
        y = 0.114 * b + 0.587 * g + 0.299 * r
        hi, lo = max(b, g, r), max(1.0, min(b, g, r))
        cast = hi / lo

        if cast <= wd.good_cast and s >= wd.good_std:
            self.last_good_at = now
            self.bad_since = 0.0
            return

        bad = cast >= wd.cast_ratio or (y < wd.dark_luma and s < wd.flat_std)
        if not bad:
            self.bad_since = 0.0
            return

        # Only recover nodes that were healthy recently (avoid night false-pos).
        if not self.last_good_at or (now - self.last_good_at) > wd.good_window_s:
            return
        if not self.bad_since:
            self.bad_since = now
        if (now - self.bad_since) < wd.confirm_s:
            return
        if (now - self.last_recover_at) < wd.cooldown_s:
            return
        print(f"[watchdog:{self.node.name}] wedge (cast={cast:.2f} y={y:.1f} "
              f"std={s:.1f}) -> bouncing eye", flush=True)
        self.last_recover_at = now
        self.bad_since = 0.0
        self.wedge_count += 1
        self.pool.recover(self.node)

    def _analyze(self, frame) -> None:
        try:
            boxes = self.pool.detector.detect(frame)
        except Exception as e:
            print(f"[watch:{self.node.name}] inference error: {e}", flush=True)
            return
        self.last_frame = frame
        cfg = self.pool.cfg.detect
        now = time.time()
        if boxes:
            self.hits += 1
            self.hit_times.append(now)
        # Sliding window: N hits within hit_window_s confirms a person. This
        # tolerates a missed frame (unlike consecutive_hits) while still
        # rejecting one-off false positives.
        cutoff = now - cfg.hit_window_s
        while self.hit_times and self.hit_times[0] < cutoff:
            self.hit_times.popleft()
        if len(self.hit_times) < max(1, cfg.min_hits):
            return
        # New presence episode? Log it for long-term tuning.
        if now - self.last_person_at > cfg.ui_hold_s:
            self._log_detection(boxes, now)
        # Latch presence for the /stream UI. Refreshed every hit while a
        # person stays in frame, so it never flickers; it decays on its own
        # ui_hold_s after they leave. Kept separate from maybe_alert so the
        # tile still lights up during the (much longer) SMS cooldown.
        self.last_person_at = now
        self.pool.alerts.maybe_alert(
            self.node.name, frame, boxes, self.pool.detector.name)

    def _log_detection(self, boxes, now: float) -> None:
        try:
            record = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                "node": self.node.name,
                "detector": self.pool.detector.name,
                "boxes": [[int(b[0]), int(b[1]), int(b[2]), int(b[3]),
                           round(float(b[4]), 3)] for b in boxes],
            }
            with open(os.path.join(DATA_DIR, "detections.jsonl"), "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass


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

    def recover(self, node: Node) -> None:
        """Bounce the eye's camera daemon over SSH; the on-device supervisor
        restarts it (re-initialising the ISP/AE/AWB)."""
        wd = self.cfg.watchdog
        addr = node.rtsp_host   # LAN address preferred, tailnet as fallback
        cmd = "kill $(ps | awk '/[c]yclops-eye/{print $1}') 2>/dev/null; echo bounced"
        try:
            r = subprocess.run(
                ["ssh", "-i", wd.ssh_key, "-o", "BatchMode=yes",
                 "-o", "StrictHostKeyChecking=accept-new",
                 "-o", "ConnectTimeout=6", f"{wd.ssh_user}@{addr}", cmd],
                capture_output=True, text=True, timeout=20)
            print(f"[watchdog] bounce {node.name}@{addr}: rc={r.returncode} "
                  f"{(r.stdout or r.stderr).strip()}", flush=True)
        except Exception as e:
            print(f"[watchdog] bounce {node.name}@{addr} failed: {e}", flush=True)

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

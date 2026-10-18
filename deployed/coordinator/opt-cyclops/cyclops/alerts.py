from __future__ import annotations
import os
import threading
import time

import cv2
import requests

from .config import Cfg, DATA_DIR

ALERT_DIR = os.path.join(DATA_DIR, "alerts")


class AlertManager:
    THERMAL_COOLDOWN_S = 1800.0      # max one heat SMS per node per 30 min

    def __init__(self, cfg: Cfg) -> None:
        self.cfg = cfg
        self._last_alert: dict[str, float] = {}
        self._lock = threading.Lock()
        os.makedirs(ALERT_DIR, exist_ok=True)

    def thermal_alert(self, node) -> bool:
        """A node has been running at critical tier for a sustained period —
        surface it through the same SMS channel as person alerts."""
        now = time.time()
        key = f"thermal:{node.name}"
        with self._lock:
            if now - self._last_alert.get(key, 0) < self.THERMAL_COOLDOWN_S:
                return False
            self._last_alert[key] = now
        body = (f"CYCLOPS: {node.name} running hot — {node.temp_c:.1f}C, "
                f"tier critical, throttled={node.throttled}. "
                f"Check cooling/enclosure.")
        self._notify(body, "")
        print(f"[alert-thermal] {body}", flush=True)
        return True

    def maybe_alert(self, node_name: str, frame, boxes, detector_name: str) -> bool:
        now = time.time()
        with self._lock:
            if now - self._last_alert.get(node_name, 0) < self.cfg.detect.cooldown_s:
                return False
            self._last_alert[node_name] = now

        annotated = frame.copy()
        for (x1, y1, x2, y2, score) in boxes:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (61, 163, 232), 2)
            cv2.putText(annotated, f"{score:.2f}", (x1, max(0, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (61, 163, 232), 1)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        fname = f"{stamp}_{node_name}.jpg"
        cv2.imwrite(os.path.join(ALERT_DIR, fname), annotated,
                    [cv2.IMWRITE_JPEG_QUALITY, 85])

        kind = "Person" if detector_name.startswith("hailo") else "Motion"
        body = (f"CYCLOPS: {kind} detected on '{node_name}' at "
                f"{time.strftime('%H:%M:%S')}. "
                f"{self.cfg.public_base}/alerts/{fname}")
        self._notify(body, fname)
        print(f"[alert] {body}", flush=True)
        return True

    def _notify(self, body: str, fname: str) -> None:
        """Fan out to every configured channel; each runs independently."""
        for target in (self._send_ntfy, self._send_sms):
            threading.Thread(target=target, args=(body, fname),
                             daemon=True).start()

    def _send_ntfy(self, body: str, fname: str) -> None:
        n = self.cfg.ntfy
        if not n.url:
            return
        headers = {"Title": "Cyclops", "Tags": "eyes"}
        if n.token:
            headers["Authorization"] = f"Bearer {n.token}"
        try:
            r = requests.post(n.url.rstrip("/"), data=body.encode(),
                              headers=headers, timeout=10)
            r.raise_for_status()
        except Exception as e:
            print(f"[alert] ntfy send failed: {e}", flush=True)

    def _send_sms(self, body: str, fname: str) -> None:
        t = self.cfg.twilio
        if not (t.account_sid and t.auth_token and t.from_number and t.to_number):
            return
        data = {"To": t.to_number, "From": t.from_number, "Body": body}
        # MMS only works if Twilio's servers can fetch the media — that
        # requires a PUBLIC https url, not a tailnet one.
        if t.public_media_base and fname:
            data["MediaUrl"] = f"{t.public_media_base.rstrip('/')}/alerts/{fname}"
        try:
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{t.account_sid}/Messages.json",
                data=data, auth=(t.account_sid, t.auth_token), timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"[alert] Twilio send failed: {e}", flush=True)

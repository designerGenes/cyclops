"""Person detection backends.

Primary: YOLOv8s on the AI HAT+ NPU via HailoRT (`hailo_platform`, from
the `hailo-all` apt package — the venv must be created with
`--system-site-packages` to see it). Use the HEF compiled for YOUR chip:
Hailo-8L -> yolov8s_h8l.hef, Hailo-8 -> yolov8s.hef (Hailo Model Zoo).
Model-zoo YOLOv8 HEFs run NMS on-chip; the output is per-class arrays of
[ymin, xmin, ymax, xmax, score] normalized to 0..1. COCO person = 0.

Fallback: background-subtraction motion detector, so the system still
streams and alerts (flagged as "motion") before the HEF is installed.
"""
from __future__ import annotations
import threading

import cv2
import numpy as np

PERSON_CLASS = 0


class HailoPersonDetector:
    name = "hailo-yolov8"

    def __init__(self, hef_path: str, score_threshold: float = 0.45) -> None:
        from hailo_platform import (  # noqa: import here: optional dep
            HEF, VDevice, ConfigureParams, HailoStreamInterface,
            InferVStreams, InputVStreamParams, OutputVStreamParams,
            FormatType,
        )
        self.score_threshold = score_threshold
        self._lock = threading.Lock()    # one NPU, many camera threads
        self._hef = HEF(hef_path)
        info = self._hef.get_input_vstream_infos()[0]
        self._in_name = info.name
        self._h, self._w = int(info.shape[0]), int(info.shape[1])
        self._legacy = False

        self._vdev = VDevice()
        try:
            params = ConfigureParams.create_from_hef(
                self._hef, interface=HailoStreamInterface.PCIe)
            self._ng = self._vdev.configure(self._hef, params)[0]
            self._in_params = InputVStreamParams.make(
                self._ng, format_type=FormatType.UINT8)
            self._out_params = OutputVStreamParams.make(
                self._ng, format_type=FormatType.FLOAT32)
            self._activation = self._ng.activate()
            self._activation.__enter__()
            self._pipe_cm = InferVStreams(self._ng, self._in_params, self._out_params)
            self._pipe = self._pipe_cm.__enter__()
            self._legacy = True
        except Exception:
            self._infer_model = self._vdev.create_infer_model(hef_path)
            self._infer_model.set_batch_size(1)
            self._configured = self._infer_model.configure()
            self._configured.__enter__()
            self._bindings = self._configured.create_bindings()
            self._flat_output = np.empty(
                (int(self._infer_model.output().shape[0]),), dtype=np.float32)

    def _letterbox(self, bgr: np.ndarray):
        ih, iw = bgr.shape[:2]
        scale = min(self._w / iw, self._h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        canvas = np.zeros((self._h, self._w, 3), dtype=np.uint8)
        dx, dy = (self._w - nw) // 2, (self._h - nh) // 2
        canvas[dy:dy + nh, dx:dx + nw] = cv2.resize(bgr, (nw, nh))
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        return rgb, scale, dx, dy

    def detect(self, bgr: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Returns person boxes as (x1, y1, x2, y2, score) in pixels."""
        rgb, scale, dx, dy = self._letterbox(bgr)
        batch = np.expand_dims(rgb, 0)
        with self._lock:
            if self._legacy:
                results = self._pipe.infer({self._in_name: batch})
                out = next(iter(results.values()))
            else:
                self._bindings.input().set_buffer(batch)
                self._bindings.output().set_buffer(self._flat_output)
                self._configured.run([self._bindings], timeout=10000)
                out = self._bindings.output().get_buffer(True)
        per_image = out[0] if isinstance(out, (list, np.ndarray)) else out
        try:
            person_rows = per_image[PERSON_CLASS]
        except (IndexError, KeyError, TypeError):
            return []
        boxes = []
        ih, iw = bgr.shape[:2]
        for row in np.asarray(person_rows).reshape(-1, 5):
            ymin, xmin, ymax, xmax, score = (float(v) for v in row)
            if score < self.score_threshold:
                continue
            x1 = (xmin * self._w - dx) / scale
            y1 = (ymin * self._h - dy) / scale
            x2 = (xmax * self._w - dx) / scale
            y2 = (ymax * self._h - dy) / scale
            boxes.append((
                max(0, int(x1)), max(0, int(y1)),
                min(iw - 1, int(x2)), min(ih - 1, int(y2)),
                score,
            ))
        return boxes


class MotionFallbackDetector:
    """Last-resort detector when the NPU/HEF is unavailable."""
    name = "motion-fallback"

    def __init__(self, min_area_frac: float = 0.02) -> None:
        self._subs: dict[int, cv2.BackgroundSubtractorMOG2] = {}
        self.min_area_frac = min_area_frac
        self._lock = threading.Lock()

    def detect(self, bgr: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        key = threading.get_ident()
        with self._lock:
            sub = self._subs.setdefault(
                key, cv2.createBackgroundSubtractorMOG2(detectShadows=False))
        mask = sub.apply(bgr)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        min_area = self.min_area_frac * bgr.shape[0] * bgr.shape[1]
        out = []
        for c in contours:
            if cv2.contourArea(c) >= min_area:
                x, y, w, h = cv2.boundingRect(c)
                out.append((x, y, x + w, y + h, 0.30))
        return out


def make_detector(hef_path: str, score_threshold: float):
    try:
        det = HailoPersonDetector(hef_path, score_threshold)
        print(f"[detect] Hailo NPU online, model={hef_path}", flush=True)
        return det
    except Exception as e:
        print(f"[detect] Hailo unavailable ({e}); using motion fallback. "
              f"Run `hailortcli fw-control identify` and check the HEF path.",
              flush=True)
        return MotionFallbackDetector()

"""Thermal + power telemetry and stream-tier policy for the Zero 2 W.

Stdlib only. The governor reads SoC temperature and the firmware
throttle flags, then decides which stream tier the camera should run.
Tier transitions step DOWN immediately and step UP only after the
node has been comfortably cool for a dwell period (hysteresis), so the
stream never oscillates.
"""
from __future__ import annotations
import subprocess
import time

TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"

# vcgencmd get_throttled bits
UNDERVOLT_NOW = 1 << 0
FREQ_CAPPED_NOW = 1 << 1
THROTTLED_NOW = 1 << 2
SOFT_TEMP_NOW = 1 << 3

# Ordered hottest-tolerant first. 'enter' is the temperature (C) at or
# above which this tier (or a lower one) is required.
TIERS = [
    {"name": "full",     "enter": 0.0,  "width": 1280, "height": 720, "fps": 5,  "bitrate": 500_000},
    {"name": "warm",     "enter": 63.0, "width": 960,  "height": 540, "fps": 5,  "bitrate": 350_000},
    {"name": "hot",      "enter": 68.0, "width": 768,  "height": 432, "fps": 5,  "bitrate": 250_000},
    {"name": "critical", "enter": 73.0, "width": 640,  "height": 360, "fps": 5,  "bitrate": 150_000},
]
EXIT_MARGIN_C = 4.0     # must be this far below a tier's enter temp...
UP_DWELL_S = 120.0      # ...for this long, before stepping back up


def read_temp_c() -> float:
    try:
        with open(TEMP_PATH) as f:
            return int(f.read().strip()) / 1000.0
    except OSError:
        return 0.0


def read_throttled() -> int:
    try:
        out = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        return int(out.strip().split("=")[1], 16)
    except Exception:
        return 0


class Governor:
    def __init__(self) -> None:
        self.idx = 0                 # current tier index into TIERS
        self.override: int | None = None  # manual tier index, or None=auto
        self.fps_override: int | None = None
        self._cool_since: float | None = None

    def effective_tier(self) -> dict:
        tier = dict(TIERS[self.idx])
        if self.fps_override is not None:
            tier["fps"] = self.fps_override
        return tier

    def required_idx(self, temp: float, throttled: int) -> int:
        idx = 0
        for i, tier in enumerate(TIERS):
            if temp >= tier["enter"]:
                idx = i
        # Power instability: drop one extra tier while under-voltage or
        # actively throttled, even if temperature alone looks fine.
        if throttled & (UNDERVOLT_NOW | THROTTLED_NOW | SOFT_TEMP_NOW):
            idx = min(idx + 1, len(TIERS) - 1)
        return idx

    def step(self, temp: float, throttled: int) -> int | None:
        """Returns a new tier index if a change is needed, else None."""
        if self.override is not None:
            if self.idx != self.override:
                self.idx = self.override
                return self.idx
            return None
        need = self.required_idx(temp, throttled)
        if need > self.idx:                       # hotter: drop NOW
            self.idx = need
            self._cool_since = None
            return self.idx
        if need < self.idx:                       # cooler: dwell first
            gate = TIERS[self.idx]["enter"] - EXIT_MARGIN_C
            if temp < gate and not throttled & 0xF:
                if self._cool_since is None:
                    self._cool_since = time.monotonic()
                elif time.monotonic() - self._cool_since >= UP_DWELL_S:
                    self.idx -= 1                 # one tier at a time
                    self._cool_since = None
                    return self.idx
            else:
                self._cool_since = None
        return None

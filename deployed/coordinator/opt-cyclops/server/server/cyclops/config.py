from __future__ import annotations
import os
import tomllib
from dataclasses import dataclass, field

CONFIG_PATH = os.environ.get("CYCLOPS_CONFIG", "/opt/cyclops/config.toml")
DATA_DIR = os.environ.get("CYCLOPS_DATA", "/opt/cyclops/data")


@dataclass
class TwilioCfg:
    account_sid: str = ""
    auth_token: str = ""
    from_number: str = ""
    to_number: str = ""
    public_media_base: str = ""   # optional public HTTPS base for MMS media


@dataclass
class DetectCfg:
    hef_path: str = "/opt/cyclops/models/yolov8s.hef"
    score_threshold: float = 0.45
    consecutive_hits: int = 2      # frames in a row before alerting
    sample_fps: float = 4.0        # frames/sec pulled per camera
    cooldown_s: float = 120.0      # min seconds between alerts per camera
    ui_hold_s: float = 10.0        # secs the /stream presence light stays lit


@dataclass
class Cfg:
    enroll_token: str = "CHANGE-ME"
    bind_host: str = "0.0.0.0"
    bind_port: int = 8080
    public_base: str = "http://cyclops:8080"   # used in SMS snapshot links
    mediamtx_api: str = "http://127.0.0.1:9997/v3"
    node_offline_after_s: float = 60.0
    twilio: TwilioCfg = field(default_factory=TwilioCfg)
    detect: DetectCfg = field(default_factory=DetectCfg)


def load() -> Cfg:
    cfg = Cfg()
    try:
        with open(CONFIG_PATH, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError:
        return cfg
    for k in ("enroll_token", "bind_host", "bind_port", "public_base",
              "mediamtx_api", "node_offline_after_s"):
        if k in raw:
            setattr(cfg, k, raw[k])
    for k, v in raw.get("twilio", {}).items():
        if hasattr(cfg.twilio, k):
            setattr(cfg.twilio, k, v)
    for k, v in raw.get("detect", {}).items():
        if hasattr(cfg.detect, k):
            setattr(cfg.detect, k, v)
    return cfg

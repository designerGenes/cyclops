"""camnode agent — runs on each Zero 2 W. Stdlib only, by design:
fewer dependencies, fewer ways to die, ~15 MB RSS.

Responsibilities:
  1. Register with Cyclops on startup; heartbeat every 15 s with
     temperature / throttle flags / current tier.
  2. Thermal governor loop: poll every 5 s, hot-patch MediaMTX stream
     parameters through its local API when the tier changes.
  3. sd_notify watchdog pings so systemd restarts us if we hang.
  4. Connectivity dead-man switch: if the brain is unreachable for
     reboot_after_unreachable_s (default 600), reboot the node — it
     comes back, rejoins the tailnet, and re-registers.
  5. Tiny control HTTP server (:8800) so Cyclops can set a manual tier
     override or query health. Authenticated by the shared token.

Config: /opt/camnode/camnode.toml
"""
from __future__ import annotations
import json
import os
import socket
import subprocess
import threading
import time
import tomllib
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import mediamtx_api, thermal

CONFIG_PATH = os.environ.get("CAMNODE_CONFIG", "/opt/camnode/camnode.toml")
START = time.monotonic()


class _NodeUnknown(Exception):
    """Raised when the brain reports it doesn't know this node (HTTP 404/410).
    This — and only this — should trigger a re-register."""


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def sd_notify(msg: str) -> None:
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.sendto(msg.encode(), addr)
        s.close()
    except OSError:
        pass


def lan_ip() -> str | None:
    """This node's LAN IPv4 (not Tailscale, not Docker/link-local), so the
    brain can pull RTSP over the LAN instead of encrypting every frame
    through tailscaled — a big CPU (and therefore heat) saving on the eye."""
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:
        return None
    for ip in out.split():
        if ip.count(".") != 3:
            continue
        first = int(ip.split(".")[0])
        if first in (100, 127, 172, 169):   # tailnet CGNAT / loopback / docker / link-local
            continue
        return ip
    return None


def post_json(url: str, payload: dict, timeout: float = 8.0) -> dict | None:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return json.loads(body) if body else None


class Agent:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.gov = thermal.Governor()
        self.last_brain_contact = time.monotonic()
        self.registered = False
        self._cam_unready_since: float | None = None
        self._last_cam_restart = 0.0

    # ---- brain (Cyclops) communication ----
    def register(self) -> None:
        c = self.cfg
        payload = {
            "name": c["name"],
            "token": c["enroll_token"],
            "host": c.get("advertise_host") or socket.gethostname(),
            "lan_host": lan_ip() or "",
            "rtsp_port": 8554,
            "streams": {"primary": "cam", "detect": "detect"},
        }
        post_json(f"{c['cyclops_url']}/api/nodes/register", payload)
        self.registered = True
        self.last_brain_contact = time.monotonic()
        print(f"[agent] registered with {c['cyclops_url']} as {c['name']}", flush=True)

    def heartbeat(self) -> None:
        c = self.cfg
        payload = {
            "name": c["name"],
            "token": c["enroll_token"],
            "temp_c": thermal.read_temp_c(),
            "throttled": hex(thermal.read_throttled()),
            "tier": self.gov.effective_tier()["name"],
            "uptime_s": int(time.monotonic() - START),
            "lan_host": lan_ip() or "",
        }
        try:
            post_json(f"{c['cyclops_url']}/api/nodes/heartbeat", payload)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise _NodeUnknown() from e
            raise  # other HTTP status: transient, do not re-register
        self.last_brain_contact = time.monotonic()

    # ---- loops ----
    def thermal_loop(self) -> None:
        while True:
            try:
                temp = thermal.read_temp_c()
                flags = thermal.read_throttled()
                new_idx = self.gov.step(temp, flags)
                if new_idx is not None:
                    tier = self.gov.effective_tier()
                    print(f"[thermal] {temp:.1f}C flags={hex(flags)} -> tier {tier['name']}", flush=True)
                    try:
                        mediamtx_api.apply_tier(tier)
                    except Exception as e:
                        print(f"[thermal] mediamtx patch failed: {e}", flush=True)
                # Config-drift guard: a mediamtx restart (encoder-wedge
                # recovery, operator action, reboot) reloads the on-disk file
                # at full-tier parameters even while the governor is demoted.
                # No tier transition will fire to correct that, so detect and
                # re-apply the effective tier here — otherwise a hot node
                # keeps running the full-load pipeline (1280x720 @ 600kbps)
                # and re-wedges the hardware encoder in a death spiral.
                try:
                    if mediamtx_api.apply_tier_if_drifted(self.gov.effective_tier()):
                        print(f"[thermal] runtime params drifted from tier — re-applied tier {self.gov.effective_tier()['name']}", flush=True)
                except Exception as e:
                    print(f"[thermal] drift check failed: {e}", flush=True)
            except Exception as e:
                print(f"[thermal] loop error: {e}", flush=True)
            try:
                self.check_camera()
            except Exception as e:
                print(f"[camera] check failed: {e}", flush=True)
            sd_notify("WATCHDOG=1")
            time.sleep(5)

    def brain_loop(self) -> None:
        c = self.cfg
        deadline = float(c.get("reboot_after_unreachable_s", 600))
        while True:
            try:
                if not self.registered:
                    self.register()
                else:
                    self.heartbeat()
            except _NodeUnknown:
                # The brain genuinely doesn't know us (e.g. it lost its
                # registry). Re-register on the next loop. This is the ONLY
                # path that re-registers, so a routine heartbeat hiccup can
                # no longer restart our proxy and kick live viewers.
                print("[agent] brain does not know us — re-registering", flush=True)
                self.registered = False
            except Exception as e:
                # Transient: timeout, refused, 5xx, DNS blip. Stay registered
                # and keep trying; only the dead-man switch reboots us.
                print(f"[agent] brain contact failed (transient): {e}", flush=True)
                silent = time.monotonic() - self.last_brain_contact
                if silent > deadline:
                    print(f"[agent] brain silent {silent:.0f}s — rebooting node", flush=True)
                    subprocess.run(["systemctl", "reboot"])
            time.sleep(15)

    def check_camera(self) -> None:
        """Self-heal the camera pipeline. The agent staying alive while the
        camera has silently stopped publishing is exactly the 'online but no
        video' failure Cyclops must not tolerate — so if the local primary
        path isn't ready for a sustained window, restart MediaMTX. Also catch
        the Pi hardware H.264 encoder wedge where MediaMTX still reports the
        path ready while logs spam VIDIOC_QBUF failures and no decodable frames
        reach the brain."""
        c = self.cfg
        grace = float(c.get("camera_unready_restart_s", 20))
        cooldown = float(c.get("camera_restart_cooldown_s", 120))
        now = time.monotonic()
        encoder_failed = self._encoder_failed_recently()
        if mediamtx_api.path_ready("cam") and not encoder_failed:
            self._cam_unready_since = None
            return
        if self._cam_unready_since is None:
            self._cam_unready_since = now
            return
        if (now - self._cam_unready_since) < grace:
            return
        if (now - self._last_cam_restart) < cooldown:
            return
        reason = "hardware encoder failed" if encoder_failed else "camera path not ready"
        print(f"[agent] {reason} — restarting mediamtx", flush=True)
        subprocess.run(["systemctl", "restart", "mediamtx"])
        self._last_cam_restart = now
        self._cam_unready_since = None

    def _encoder_failed_recently(self) -> bool:
        try:
            r = subprocess.run(
                ["journalctl", "-u", "mediamtx", "--since", "30 seconds ago", "--no-pager"],
                text=True, capture_output=True, timeout=4,
            )
        except Exception:
            return False
        return "encoder_hardware_h264_encode(): ioctl(VIDIOC_QBUF) failed" in r.stdout

    # ---- control server ----
    def make_handler(agent):  # noqa: N805 — closure over agent
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _auth(self) -> bool:
                return self.headers.get("X-Camnode-Token") == agent.cfg["enroll_token"]

            def _send(self, code: int, obj: dict) -> None:
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health":
                    self._send(200, {
                        "name": agent.cfg["name"],
                        "temp_c": thermal.read_temp_c(),
                        "throttled": hex(thermal.read_throttled()),
                        "tier": agent.gov.effective_tier()["name"],
                        "fps": agent.gov.effective_tier()["fps"],
                        "override": agent.gov.override,
                        "mediamtx": mediamtx_api.healthy(),
                        "uptime_s": int(time.monotonic() - START),
                    })
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                if not self._auth():
                    self._send(403, {"error": "bad token"})
                    return
                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    self._send(400, {"error": "bad json"})
                    return
                if self.path == "/tier":
                    want = body.get("tier", "auto")
                    if want == "auto":
                        agent.gov.override = None
                        try:
                            mediamtx_api.apply_tier(agent.gov.effective_tier())
                        except Exception as e:
                            self._send(502, {"error": f"mediamtx patch failed: {e}"})
                            return
                        self._send(200, {"tier": "auto"})
                        return
                    for i, t in enumerate(thermal.TIERS):
                        if t["name"] == want:
                            agent.gov.override = i
                            try:
                                mediamtx_api.apply_tier(agent.gov.effective_tier())
                            except Exception as e:
                                self._send(502, {"error": f"mediamtx patch failed: {e}"})
                                return
                            self._send(200, {"tier": want})
                            return
                    self._send(400, {"error": f"unknown tier {want!r}"})
                elif self.path == "/fps":
                    want = body.get("fps", "auto")
                    if want == "auto":
                        agent.gov.fps_override = None
                    else:
                        try:
                            fps = int(want)
                        except (TypeError, ValueError):
                            self._send(400, {"error": f"bad fps {want!r}"})
                            return
                        if fps < 5 or fps > 25:
                            self._send(400, {"error": "fps must be between 5 and 25"})
                            return
                        agent.gov.fps_override = fps
                    try:
                        mediamtx_api.apply_tier(agent.gov.effective_tier())
                    except Exception as e:
                        self._send(502, {"error": f"mediamtx patch failed: {e}"})
                        return
                    self._send(200, {"fps": agent.gov.effective_tier()["fps"], "override": agent.gov.fps_override})
                else:
                    self._send(404, {"error": "not found"})
        return Handler

    def run(self) -> None:
        sd_notify("READY=1")
        threading.Thread(target=self.thermal_loop, daemon=True).start()
        threading.Thread(target=self.brain_loop, daemon=True).start()
        srv = ThreadingHTTPServer(("0.0.0.0", 8800), self.make_handler())
        srv.serve_forever()


def main() -> None:
    agent = Agent(load_config())
    agent.run()


if __name__ == "__main__":
    main()

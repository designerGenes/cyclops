#!/usr/bin/env bash
# Install the Cyclops brain on a Pi 5 (Raspberry Pi OS Trixie 64-bit).
# Prereq (AI HAT+): sudo apt install dkms && sudo apt install hailo-all && reboot
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v hailortcli >/dev/null; then
  echo "WARNING: hailortcli not found. Detection will run in motion-fallback"
  echo "mode until you: sudo apt install dkms && sudo apt install hailo-all && reboot"
fi

apt-get update
apt-get install -y python3-venv curl ffmpeg

# MediaMTX (latest arm64)
if [ ! -x /opt/mediamtx/mediamtx ]; then
  mkdir -p /opt/mediamtx && cd /tmp
  url=$(curl -fsSL https://api.github.com/repos/bluenviron/mediamtx/releases/latest \
        | grep browser_download_url | grep linux_arm64 | grep -o 'https://[^"]*')
  curl -fsSL -o mediamtx.tgz "$url"
  tar xzf mediamtx.tgz -C /opt/mediamtx mediamtx
  cd - >/dev/null
fi

mkdir -p /opt/cyclops/models /opt/cyclops/data/alerts
cp -r server/cyclops /opt/cyclops/
cp -r server/static /opt/cyclops/
cp server/mediamtx.server.yml /opt/cyclops/
[ -f /opt/cyclops/config.toml ] || cp server/config.toml.example /opt/cyclops/config.toml

# venv with system site packages => hailo_platform visible
python3 -m venv --system-site-packages /opt/cyclops/venv
/opt/cyclops/venv/bin/pip install -r server/requirements.txt

cp server/systemd/mediamtx-central.service /etc/systemd/system/
cp server/systemd/cyclops.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mediamtx-central cyclops

echo
echo "Cyclops is up: http://$(hostname):8080/stream"
echo "Next: drop your model at /opt/cyclops/models/yolov8s.hef"
echo "      (Hailo-8L users: download the _h8l build) and edit"
echo "      /opt/cyclops/config.toml (enroll_token, Twilio), then:"
echo "      systemctl restart cyclops"

# Cyclops Eye firmware for LuckFox Pico Pro

This is the current camera-eye firmware for LuckFox Pico Pro/Max (RV1106) boards. It replaces the earlier Raspberry Pi Zero 2 W implementation and uses the vendor-supported Rockchip media stack directly.

## Design

The Raspberry Pi Eye depended on Python, `picamera2`, `vcgencmd`, and MediaMTX's `rpiCamera` source. Those interfaces do not exist on the LuckFox Pico Pro's Buildroot image. This implementation uses the vendor-supported Rockchip Media Process Platform directly:

- MPP VI receives ISP output through DMABUF and binds it to the RV1106 H.264 VENC hardware.
- The vendor `rtsp_demo` library publishes `/cam` (primary) and `/detect` (NPU/detection) streams. Cyclops retains its current `cam` and `detect` node contract and port `8554`.
- The primary pipeline starts at 1920×1080/15fps/2Mbps; the detection pipeline is independently capped at 640×360/4fps/250Kbps so analytics do not burn encoder capacity unnecessarily.
- The thermal governor reads Linux thermal sysfs rather than Raspberry Pi `vcgencmd`. It downshifts immediately at 70°C, 78°C, and 84°C, requires 120 seconds of cool dwell to recover, and prevents manual FPS/tier requests from overriding a thermal reduction.
- Registration and heartbeat payloads match the existing Cyclops `/api/nodes/register` and `/api/nodes/heartbeat` contract. They advertise the local LAN address so the coordinator can keep using LAN-direct RTSP.
- A Buildroot/SysV init file is included because the stock LuckFox image does not use the Raspberry Pi's systemd unit model.

The MPP pipeline is based on the public LuckFox SDK `simple_vi_bind_venc_rtsp.c` and `simple_vi_bind_venc_change_resolution_rv1106.c` examples, rather than guessing Raspberry Pi abstractions. Tier changes tear down and recreate the VI→VENC bindings, which is the SDK-supported resolution-change sequence.

## Host verification

The portable core has no vendor SDK dependency and can be verified locally:

```bash
cmake -S firmware/luckfox-pico-pro -B firmware/luckfox-pico-pro/build
cmake --build firmware/luckfox-pico-pro/build
ctest --test-dir firmware/luckfox-pico-pro/build --output-on-failure
```

`cyclops-eye-config-check` is the host build's only executable; it validates a configuration file and deliberately cannot access camera hardware.

## Board integration checklist

1. Start from the exact LuckFox SDK and camera sensor image selected for the boards. Confirm the installed `rk_mpi_*`, `rtsp_demo`, and ISP IQ files match that image.
2. Cross-compile and stage, but do not deploy, with `firmware/luckfox-pico-pro/install.sh --stage-dir /absolute/stage/path --sdk-root /path/to/luckfox/sysroot`.
3. On a sacrificial board, verify camera sensor ID, the `iq_dir` files, RTSP-over-TCP, `/cam` and `/detect` decoding, and all thermal tiers before enrolling it in Cyclops.
4. Only after an explicit rollout decision should the stock `rkipc` camera owner be stopped and the staged SysV file enabled. Never run both camera owners simultaneously.

The example configuration contains no usable credentials. Create one distinct enrollment token per board when provisioning it.

'use strict';

const MTX = `${location.protocol}//${location.hostname}:8889`;
const HLS = `${location.protocol}//${location.hostname}:8888`;
const transportPref = new URLSearchParams(location.search).get('transport') || 'auto';
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const stack = document.getElementById('stack');
const tray = document.getElementById('tray');
const trayItems = document.getElementById('trayItems');
const tpl = document.getElementById('tileTpl');
const sysline = document.getElementById('sysline');
const sysIris = document.getElementById('sysIris');

const tiles = new Map();
let layout = { order: [], hidden: [] };
/* Timestamp color presets; the per-tile color button advances through these. */
const OSD_COLOR_NAMES = ['white', 'yellow', 'black', 'red'];

/* ---------------- list / grid view ---------------- */
const viewToggle = document.getElementById('viewToggle');
const VIEW_KEY = 'cyclops.view';
let viewMode = localStorage.getItem(VIEW_KEY) === 'grid' ? 'grid' : 'list';
function applyView() {
  stack.classList.toggle('grid', viewMode === 'grid');
  viewToggle.textContent = viewMode === 'grid' ? 'list' : 'grid';
  viewToggle.setAttribute('aria-pressed', viewMode === 'grid' ? 'true' : 'false');
}
viewToggle.addEventListener('click', () => {
  viewMode = viewMode === 'grid' ? 'list' : 'grid';
  try { localStorage.setItem(VIEW_KEY, viewMode); } catch { /* private mode */ }
  applyView();
});

const WHEP_FAIL_THRESHOLD = 3;
const STALL_MS = 15000;
const FIRST_FRAME_TIMEOUT = 20000;
const RECONNECT_BASE_MS = 3000;
const RECONNECT_MAX_MS = 30000;

/* ---------------- WHEP ---------------- */
function waitForIceGathering(pc, timeoutMs) {
  return new Promise((resolve) => {
    if (pc.iceGatheringState === 'complete') { resolve(); return; }
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    pc.addEventListener('icegatheringstatechange', () => {
      if (pc.iceGatheringState === 'complete') finish();
    });
    setTimeout(finish, timeoutMs);
  });
}

async function whepConnect(video, path) {
  const pc = new RTCPeerConnection({ iceServers: [] });
  pc.addTransceiver('video', { direction: 'recvonly' });
  pc.ontrack = (e) => {
    video.srcObject = e.streams[0];
    video.play().catch(() => {});
  };
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  await waitForIceGathering(pc, 2000);
  const sdp = pc.localDescription.sdp;
  const ctrl = new AbortController();
  const abort = setTimeout(() => ctrl.abort(), 8000);
  const res = await fetch(`${MTX}/${path}/whep?nocache=${Date.now()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/sdp' },
    body: sdp,
    signal: ctrl.signal,
  });
  clearTimeout(abort);
  if (!res.ok) { pc.close(); throw new Error(`WHEP ${res.status}`); }
  await pc.setRemoteDescription({ type: 'answer', sdp: await res.text() });
  return pc;
}

async function hlsConnect(video, path) {
  return await new Promise((resolve, reject) => {
    const url = `${HLS}/${path}/index.m3u8?nocache=${Date.now()}`;
    let settled = false;
    const cleanup = () => {
      video.removeEventListener('loadedmetadata', onLoaded);
      video.removeEventListener('canplay', onLoaded);
      video.removeEventListener('playing', onLoaded);
      video.removeEventListener('timeupdate', onLoaded);
      video.removeEventListener('error', onError);
    };
    const onLoaded = () => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve({
        close() {
          video.pause();
          video.removeAttribute('src');
          video.load();
        },
      });
    };
    const onError = () => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(new Error('HLS failed'));
    };
    video.addEventListener('loadedmetadata', onLoaded, { once: true });
    video.addEventListener('canplay', onLoaded, { once: true });
    video.addEventListener('playing', onLoaded, { once: true });
    video.addEventListener('timeupdate', onLoaded, { once: true });
    video.addEventListener('error', onError, { once: true });
    video.src = url;
    video.load();
    video.play().catch(() => {});
    setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(new Error('HLS timeout'));
    }, 8000);
  });
}

/* ---------------- liveness helpers ---------------- */
function waitForFirstFrame(video, timeoutMs) {
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (ok) => {
      if (done) return; done = true;
      video.removeEventListener('timeupdate', onTU);
      video.removeEventListener('playing', onPlay);
      clearInterval(playRetry);
      clearTimeout(timer);
      ok ? resolve() : reject(new Error('no frame'));
    };
    const onTU = () => { if (video.currentTime > 0) finish(true); };
    const onPlay = () => { if (video.currentTime > 0) finish(true); };
    video.addEventListener('timeupdate', onTU);
    video.addEventListener('playing', onPlay);
    const playRetry = setInterval(() => {
      if (video.srcObject && video.paused) video.play().catch(() => {});
      if (video.readyState >= 2) finish(true);
    }, 500);
    if (video.srcObject && 'requestVideoFrameCallback' in video)
      video.requestVideoFrameCallback(() => finish(true));
    const timer = setTimeout(() => finish(false), timeoutMs);
  });
}

function startFrameWatchdog(video, stallMs, onStall) {
  let last = -1, lastChange = Date.now();
  const id = setInterval(() => {
    const t = video.currentTime;
    if (t !== last) { last = t; lastChange = Date.now(); return; }
    if (Date.now() - lastChange > stallMs) onStall();
  }, 2000);
  return () => clearInterval(id);
}

function applyState(t) {
  const n = t.node || {};
  let msg = null;
  if (!t.connected) msg = 'DISCONNECTED';
  else if (t.paused) msg = 'PAUSED';
  else if (!n.online) msg = 'EYE OFFLINE';
  else if (t.connState === 'live') msg = null;
  else if (t.connState === 'connecting') msg = 'CONNECTING…';
  else if (t.connState === 'nosignal') msg = 'NO SIGNAL — RETRYING';
  else msg = 'RECONNECTING';
  t.veil.hidden = !msg;
  if (msg) t.veilMsg.textContent = msg;
}

/* ---------------- tiles ---------------- */
function irisClass(t) {
  const node = t.node || {};
  if (!node.online) return 'offline';
  if (!t.connected) return 'disconnected';
  if (t.connState === 'error') return 'error';
  if (t.connState === 'live') {
    if (node.power_warn || node.temp_c >= 68) return 'hot';
    if (node.temp_c >= 60) return 'warm';
    return 'ok';
  }
  if (node.stream_ready === false || node.stream_ready === undefined) return 'idle';
  return 'idle';
}

function makeTile(node) {
  const el = tpl.content.firstElementChild.cloneNode(true);
  el.dataset.name = node.name;
  el.querySelector('.cam-name').textContent = node.name;

  const t = {
    el, node, pc: null, paused: false, retry: null,
    connected: true, connecting: false,
    connState: 'idle', downGrace: null, stopWatch: null,
    whepFails: 0, useHlsFallback: false,
    zoom: 1, panX: 0, panY: 0,
    rotation: ((node.rotation || 0) % 360),
    osdScale: 6, osdColor: 0,
    video: el.querySelector('video'),
    canvas: el.querySelector('canvas'),
    source: null, raf: null, rotatePipeline: false,
    veil: el.querySelector('.veil'),
    veilMsg: el.querySelector('.veil-msg'),
    viewport: el.querySelector('.viewport'),
    iris: el.querySelector('.iris'),
    telemetry: el.querySelector('.telemetry'),
    zoomval: el.querySelector('.zoomval'),
  };

  /* Rotation → native Picture-in-Picture. The browser's PiP window plays the
     raw <video> frames and ignores any CSS transform, so a rotated camera must
     be pre-rotated before the frames reach the element. When display rotation
     is non-zero we decode into a hidden source video, draw it rotated through
     the tile's <canvas>, and let the visible video play canvas.captureStream(). */
  const enableRotatePipeline = () => {
    if (t.rotatePipeline) return;
    /* iOS Safari can't play a canvas.captureStream() alongside native HLS
     * reliably - it renders a blank tile. iOS keyboard/pointer rotation is
     * handled by the CSS transform branch in applyZoom() instead. */
    if (isIOS) return;
    t.source = document.createElement('video');
    t.source.autoplay = true;
    t.source.muted = true;
    t.source.playsInline = true;
    t.source.setAttribute('aria-hidden', 'true');
    t.source.style.cssText =
      'position:absolute;left:-9999px;top:0;width:2px;height:2px;opacity:0;pointer-events:none;';
    t.viewport.appendChild(t.source);
    if (t.video.srcObject) {
      t.source.srcObject = t.video.srcObject;
    } else if (t.video.currentSrc || t.video.getAttribute('src')) {
      const url = t.video.currentSrc || t.video.getAttribute('src');
      t.video.removeAttribute('src');
      t.video.load();
      t.source.src = url;
      t.source.load();
    }
    t.source.play().catch(() => {});
    t.video.srcObject = t.canvas.captureStream(30);
    t.video.muted = true;
    t.video.play().catch(() => {});
    t.ctx = t.canvas.getContext('2d');
    t.rotatePipeline = true;
    const draw = () => {
      t.raf = requestAnimationFrame(draw);
      const s = t.source;
      if (!s || !s.videoWidth || !s.videoHeight || s.readyState < 2) return;
      const rot = ((t.rotation % 360) + 360) % 360;
      const swap = rot === 90 || rot === 270;
      const cw = swap ? s.videoHeight : s.videoWidth;
      const ch = swap ? s.videoWidth : s.videoHeight;
      if (t.canvas.width !== cw || t.canvas.height !== ch) {
        t.canvas.width = cw;
        t.canvas.height = ch;
      }
      const ctx = t.ctx;
      ctx.save();
      ctx.clearRect(0, 0, cw, ch);
      ctx.translate(cw / 2, ch / 2);
      ctx.rotate((rot * Math.PI) / 180);
      ctx.drawImage(s, -s.videoWidth / 2, -s.videoHeight / 2, s.videoWidth, s.videoHeight);
      ctx.restore();
    };
    t.raf = requestAnimationFrame(draw);
  };
  const disableRotatePipeline = () => {
    if (!t.rotatePipeline) return;
    if (t.raf) { cancelAnimationFrame(t.raf); t.raf = null; }
    if (t.source) {
      if (t.source.srcObject) {
        t.video.srcObject = t.source.srcObject;
      } else if (t.source.currentSrc || t.source.getAttribute('src')) {
        const url = t.source.currentSrc || t.source.getAttribute('src');
        t.video.removeAttribute('src');
        t.video.load();
        t.video.src = url;
        t.video.load();
      }
      t.source.removeAttribute('src');
      t.source.srcObject = null;
      t.source.load();
      t.source.remove();
      t.source = t.video;
    }
    t.video.play().catch(() => {});
    t.rotatePipeline = false;
  };
  const applyRotationPipeline = () => {
    if (((t.rotation % 360) + 360) % 360 !== 0) enableRotatePipeline();
    else disableRotatePipeline();
  };

  /* presence-alert mute (persisted per camera) */
  const bNotify = el.querySelector('.b-notify');
  const applyNotify = (on) => {
    t.node.notify = on;
    bNotify.classList.toggle('off', !on);
    bNotify.textContent = on ? 'alerts' : 'alerts off';
    bNotify.title = on ? 'presence alerts on (click to mute)'
                       : 'presence alerts muted (click to enable)';
  };
  bNotify.addEventListener('click', async () => {
    const want = !(t.node.notify !== false);
    applyNotify(want);
    try {
      await fetch(`/api/nodes/${node.name}/notify`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: want }),
      });
    } catch { /* telemetry poll reconciles */ }
  });
  applyNotify(node.notify !== false);

  const teardown = () => {
    clearTimeout(t.retry);
    clearTimeout(t.downGrace); t.downGrace = null;
    if (t.stopWatch) { t.stopWatch(); t.stopWatch = null; }
    if (t.pc) { try { t.pc.close(); } catch { /* */ } t.pc = null; }
    if (t.rotatePipeline && t.source && t.source !== t.video) {
      t.source.srcObject = null;
      t.source.removeAttribute('src');
      t.source.load();
    } else {
      t.video.srcObject = null;
    }
    t.connecting = false;
  };

  const setConn = (s) => { t.connState = s; applyState(t); t.iris.className = `iris ${irisClass(t)}`; };

  const reconnectDelay = () => {
    const attempt = t.whepFails;
    return Math.min(RECONNECT_BASE_MS * Math.pow(1.5, attempt), RECONNECT_MAX_MS);
  };

  const reconnect = (nosignal) => {
    teardown();
    if (!t.connected || t.paused) return;
    setConn(nosignal ? 'nosignal' : 'reconnecting');
    t.retry = setTimeout(connect, reconnectDelay());
  };

  const connect = async () => {
    if (!t.connected || t.paused || t.connecting) return;
    teardown();
    t.connecting = true;
    setConn('connecting');
    try {
      const forceHls = transportPref === 'hls' || t.useHlsFallback ||
        (transportPref === 'auto' && isIOS);
      if (forceHls) {
        t.pc = await hlsConnect(t.source, node.whep_path);
      } else {
        t.pc = await whepConnect(t.source, node.whep_path);
        t.whepFails = 0;
      }

      if (!forceHls && t.pc && t.pc.addEventListener) {
        t.pc.addEventListener('connectionstatechange', () => {
          const s = t.pc.connectionState;
          if (s === 'failed' || s === 'closed') {
            reconnect(false);
          } else if (s === 'disconnected') {
            clearTimeout(t.downGrace);
            t.downGrace = setTimeout(() => {
              if (t.pc && t.pc.connectionState !== 'connected') reconnect(false);
            }, 8000);
          } else if (s === 'connected') {
            clearTimeout(t.downGrace); t.downGrace = null;
          }
        });
      }

      await waitForFirstFrame(t.source, FIRST_FRAME_TIMEOUT);
      setConn('live');
      t.stopWatch = startFrameWatchdog(t.source, STALL_MS, () => reconnect(false));
    } catch {
      if (!forceHls) {
        t.whepFails++;
        if (t.whepFails >= WHEP_FAIL_THRESHOLD) {
          t.useHlsFallback = true;
          console.warn(`[cyclops] ${node.name}: WHEP failed ${t.whepFails}x, falling back to HLS`);
        }
      }
      setConn('error');
      reconnect(true);
    } finally {
      t.connecting = false;
    }
  };
  t.connect = connect;

  const bConnect = el.querySelector('.b-connect');
  bConnect.addEventListener('click', () => {
    t.connected = !t.connected;
    bConnect.textContent = t.connected ? 'connect' : 'disconnect';
    bConnect.classList.toggle('off', !t.connected);
    if (t.connected) {
      if (t.node.stream_ready === true) connect();
      else setConn('idle');
    } else {
      teardown();
      setConn('idle');
    }
    applyState(t);
    t.iris.className = `iris ${irisClass(t)}`;
  });

  const bStream = el.querySelector('.b-stream');
  bStream.addEventListener('click', () => {
    t.paused = !t.paused;
    bStream.textContent = t.paused ? 'play' : 'stream';
    bStream.classList.toggle('off', t.paused);
    if (t.paused) {
      if (t.source) t.source.pause();
      if (t.rotatePipeline && t.video) t.video.pause();
      applyState(t);
    } else {
      if (t.source && (t.source.srcObject || t.source.currentSrc || t.source.getAttribute('src'))) {
        t.source.play().catch(() => {});
        if (t.rotatePipeline && t.video) t.video.play().catch(() => {});
        applyState(t);
      } else if (t.connected && t.node.stream_ready === true) {
        connect();
      }
    }
  });

  /* zoom + pan */
  const applyZoom = () => {
    const m = (t.zoom - 1) / (2 * t.zoom);
    t.panX = Math.max(-m, Math.min(m, t.panX));
    t.panY = Math.max(-m, Math.min(m, t.panY));
    if (t.rotatePipeline) {
      // Frames are already rotated into the video element; zoom/pan only.
      t.video.style.transform =
        `scale(${t.zoom.toFixed(4)}) translate(${t.panX * 100}%, ${t.panY * 100}%)`;
    } else {
      const rot = ((t.rotation % 360) + 360) % 360;
      const r = t.viewport.getBoundingClientRect();
      // A 90°/270° turn makes the frame tall; scale it to fit the wide viewport.
      const fit = (rot === 90 || rot === 270) && r.width ? r.height / r.width : 1;
      t.video.style.transform =
        `rotate(${rot}deg) scale(${(t.zoom * fit).toFixed(4)}) ` +
        `translate(${t.panX * 100}%, ${t.panY * 100}%)`;
    }
    t.zoomval.textContent = `${t.zoom.toFixed(1)}×`;
    t.viewport.classList.toggle('zoomed', t.zoom > 1);
  };
  const setZoom = (z) => { t.zoom = Math.max(1, Math.min(4, z)); if (t.zoom === 1) { t.panX = t.panY = 0; } applyZoom(); };
  el.querySelector('.b-zoom-in').addEventListener('click', () => setZoom(t.zoom + 0.5));
  el.querySelector('.b-zoom-out').addEventListener('click', () => setZoom(t.zoom - 0.5));
  el.querySelector('.b-fit').addEventListener('click', () => setZoom(1));

  /* display rotation — persisted server-side per node, shared across clients */
  const bRot = el.querySelector('.b-rot');
  const rotval = el.querySelector('.rotval');
  const setRotation = (deg, persist) => {
    t.rotation = ((Math.round(deg / 90) * 90) % 360 + 360) % 360;
    rotval.textContent = `${t.rotation}°`;
    applyRotationPipeline();
    applyZoom();
    if (persist) {
      fetch(`/api/nodes/${node.name}/rotation`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rotation: t.rotation }),
      }).catch(() => { /* telemetry poll reconciles */ });
    }
  };
  t.setRotation = setRotation;
  bRot.addEventListener('click', () => setRotation(t.rotation + 90, true));
  rotval.textContent = `${t.rotation}°`;
  t.viewport.addEventListener('dblclick', () => setZoom(t.zoom > 1 ? 1 : 2));
  t.viewport.addEventListener('wheel', (e) => {
    e.preventDefault();
    setZoom(t.zoom + (e.deltaY < 0 ? 0.25 : -0.25));
  }, { passive: false });
  let pan = null;
  t.viewport.addEventListener('pointerdown', (e) => {
    if (t.zoom <= 1) return;
    pan = { x: e.clientX, y: e.clientY, px: t.panX, py: t.panY };
    t.viewport.classList.add('panning');
    t.viewport.setPointerCapture(e.pointerId);
  });
  t.viewport.addEventListener('pointermove', (e) => {
    if (!pan) return;
    const r = t.viewport.getBoundingClientRect();
    t.panX = pan.px + (e.clientX - pan.x) / (r.width * t.zoom);
    t.panY = pan.py + (e.clientY - pan.y) / (r.height * t.zoom);
    applyZoom();
  });
  ['pointerup', 'pointercancel'].forEach(ev =>
    t.viewport.addEventListener(ev, () => { pan = null; t.viewport.classList.remove('panning'); }));

  /* tier override */
  el.querySelector('.tiersel select').addEventListener('change', async (e) => {
    try {
      await fetch(`/api/nodes/${node.name}/tier`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: e.target.value }),
      });
    } catch { /* telemetry will show reality */ }
  });

  el.querySelector('.fpssel select').addEventListener('change', async (e) => {
    try {
      await fetch(`/api/nodes/${node.name}/fps`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fps: e.target.value }),
      });
    } catch { /* telemetry will show reality */ }
  });

  /* timestamp overlay color + size (per-eye, persisted server-side) */
  const osdColorBtn = el.querySelector('.b-osdcolor');
  const osdSize = el.querySelector('.osdsize');
  const setOsd = (scale, color, persist) => {
    t.osdScale = Math.max(3, Math.min(12, Number(scale) || 6));
    t.osdColor = Math.max(0, Math.min(OSD_COLOR_NAMES.length - 1, Number(color) || 0));
    osdSize.textContent = String(t.osdScale);
    osdColorBtn.textContent = `ts: ${OSD_COLOR_NAMES[t.osdColor]}`;
    if (persist) {
      fetch(`/api/nodes/${node.name}/osd`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scale: t.osdScale, color: t.osdColor }),
      }).catch(() => { /* telemetry will show reality */ });
    }
  };
  osdColorBtn.addEventListener('click', () =>
    setOsd(t.osdScale, (t.osdColor + 1) % OSD_COLOR_NAMES.length, true));
  el.querySelector('.b-osd-inc').addEventListener('click', () =>
    setOsd(t.osdScale + 1, t.osdColor, true));
  el.querySelector('.b-osd-dec').addEventListener('click', () =>
    setOsd(t.osdScale - 1, t.osdColor, true));
  setOsd(node.osd_scale, node.osd_color, false);

  /* hide */
  el.querySelector('.b-hide').addEventListener('click', () => {
    if (!layout.hidden.includes(node.name)) layout.hidden.push(node.name);
    saveLayout(); render();
  });

  /* drag reorder */
  const handle = el.querySelector('.drag');
  handle.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', node.name);
    el.classList.add('dragging');
  });
  handle.addEventListener('dragend', () => el.classList.remove('dragging'));
  el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('dropline'); });
  el.addEventListener('dragleave', () => el.classList.remove('dropline'));
  el.addEventListener('drop', (e) => {
    e.preventDefault(); el.classList.remove('dropline');
    const from = e.dataTransfer.getData('text/plain');
    if (!from || from === node.name) return;
    const order = currentOrder().filter(n => n !== from);
    order.splice(order.indexOf(node.name), 0, from);
    layout.order = order;
    saveLayout(); render();
  });

  t.source = t.video;
  applyRotationPipeline();
  applyZoom();
  return t;
}

function updateTile(t, node) {
  const prevReady = t.node?.stream_ready;
  t.node = node;
  const notifyOn = node.notify !== false;
  const bN = t.el.querySelector('.b-notify');
  if (bN) {
    bN.classList.toggle('off', !notifyOn);
    bN.textContent = notifyOn ? 'alerts' : 'alerts off';
    bN.title = notifyOn ? 'presence alerts on (click to mute)'
                        : 'presence alerts muted (click to enable)';
  }
  if (typeof node.rotation === 'number' && node.rotation !== t.rotation) {
    t.setRotation(node.rotation, false);   // reflect changes from other clients
  }
  if (node.osd_scale !== undefined && node.osd_color !== undefined &&
      (node.osd_scale !== t.osdScale || node.osd_color !== t.osdColor)) {
    t.osdScale = Math.max(3, Math.min(12, Number(node.osd_scale) || 6));
    t.osdColor = Math.max(0, Math.min(OSD_COLOR_NAMES.length - 1, Number(node.osd_color) || 0));
    t.el.querySelector('.osdsize').textContent = String(t.osdScale);
    t.el.querySelector('.b-osdcolor').textContent = `ts: ${OSD_COLOR_NAMES[t.osdColor]}`;
  }
  t.iris.className = `iris ${irisClass(t)}`;
  t.el.classList.toggle('seen', !!node.person && node.online);
  t.el.classList.toggle('powerwarn', !!node.power_warn && node.online);
  if (node.online) {
    let s = `${node.temp_c.toFixed(1)}°C · ${node.tier} · up ${fmtUp(node.uptime_s)}`;
    if (node.heartbeat_age_s !== undefined) s += ` · hb ${node.heartbeat_age_s.toFixed(1)}s`;
    if (node.power_warn) s += ' · ⚡LOW PWR';
    if (t.useHlsFallback) s += ' · HLS';
    t.telemetry.textContent = s;
  } else {
    t.telemetry.textContent = 'OFFLINE';
  }
  applyState(t);
  if (node.stream_ready === true && prevReady !== true && t.connected && !t.paused && !t.pc && !t.connecting) {
    t.connect();
  }
}

const fmtUp = (s) => s >= 3600 ? `${(s / 3600).toFixed(1)}h` : `${Math.floor(s / 60)}m`;
const currentOrder = () =>
  [...new Set([...layout.order, ...tiles.keys()])].filter(n => tiles.has(n));

/* ---------------- layout / render ---------------- */
async function saveLayout() {
  layout.order = currentOrder();
  await fetch('/api/layout', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(layout),
  }).catch(() => {});
}

function render() {
  const order = currentOrder();
  for (const name of order) {
    const t = tiles.get(name);
    const hidden = layout.hidden.includes(name);
    if (hidden) {
      if (t.el.parentNode) t.el.remove();
      if (t.pc) { t.pc.close(); t.pc = null; }
    } else {
      stack.appendChild(t.el);
      if (!t.pc && !t.paused && t.connected && !t.connecting && t.node.stream_ready === true) t.connect();
    }
  }
  trayItems.innerHTML = '';
  tray.hidden = layout.hidden.length === 0;
  for (const name of layout.hidden) {
    const b = document.createElement('button');
    b.textContent = `show ${name}`;
    b.addEventListener('click', () => {
      layout.hidden = layout.hidden.filter(n => n !== name);
      saveLayout(); render();
    });
    trayItems.appendChild(b);
  }
}

/* ---------------- poll loop ---------------- */
async function poll() {
  let nodes;
  try {
    nodes = await (await fetch('/api/nodes')).json();
  } catch {
    sysline.textContent = 'brain unreachable';
    sysIris.className = 'iris iris-lg offline';
    return;
  }
  let added = false;
  for (const node of nodes) {
    if (!tiles.has(node.name)) {
      tiles.set(node.name, makeTile(node));
      if (!layout.order.includes(node.name)) layout.order.push(node.name);
      added = true;
    }
    updateTile(tiles.get(node.name), node);
  }
  if (added) render();
  const online = nodes.filter(n => n.online).length;
  const streaming = nodes.filter(n => n.online && n.stream_ready).length;
  const blind = online - streaming;
  const hot = nodes.filter(n => n.online && (n.temp_c >= 68 || n.power_warn)).length;
  const connected = [...tiles.values()].filter(t => t.connected && t.connState === 'live').length;
  sysline.textContent =
    `${connected}/${nodes.length} connected` +
    (blind ? ` · ${blind} no-signal` : '') +
    (hot ? ` · ${hot} hot` : '');
  sysIris.className = `iris iris-lg ${
    connected === 0 ? 'offline'
    : blind ? 'idle'
    : hot ? 'hot'
    : connected < nodes.length ? 'warm' : 'ok'}`;
}

(async function init() {
  applyView();
  try { layout = await (await fetch('/api/layout')).json(); } catch { /* defaults */ }
  await poll();
  render();
  setInterval(poll, 3000);
})();

/* CYCLOPS stream wall.
 * - WHEP (WebRTC) playback from the central MediaMTX on :8889
 * - per-tile: pause, zoom+pan, hide, tier override, drag reorder
 * - layout persisted server-side; new eyes append to the bottom
 */
'use strict';

const MTX = `${location.protocol}//${location.hostname}:8889`;
const HLS = `${location.protocol}//${location.hostname}:8888`;
const transportPref = new URLSearchParams(location.search).get('transport') || 'auto';
const stack = document.getElementById('stack');
const tray = document.getElementById('tray');
const trayItems = document.getElementById('trayItems');
const tpl = document.getElementById('tileTpl');
const sysline = document.getElementById('sysline');
const sysIris = document.getElementById('sysIris');

const tiles = new Map();              // name -> tile state
let layout = { order: [], hidden: [] };

/* ---------------- WHEP ---------------- */
async function whepConnect(video, path) {
  const pc = new RTCPeerConnection({ iceServers: [] });
  pc.addTransceiver('video', { direction: 'recvonly' });
  pc.ontrack = (e) => { video.srcObject = e.streams[0]; };
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  const res = await fetch(`${MTX}/${path}/whep?nocache=${Date.now()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/sdp' },
    body: pc.localDescription.sdp,
  });
  if (!res.ok) { pc.close(); throw new Error(`WHEP ${res.status}`); }
  await pc.setRemoteDescription({ type: 'answer', sdp: await res.text() });
  return pc;
}

async function hlsConnect(video, path, onDown) {
  return await new Promise((resolve, reject) => {
    const url = `${HLS}/${path}/index.m3u8?nocache=${Date.now()}`;
    let settled = false;
    const cleanup = () => {
      video.removeEventListener('loadeddata', onLoaded);
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
    video.addEventListener('loadeddata', onLoaded, { once: true });
    video.addEventListener('error', onError, { once: true });
    video.src = url;
    video.load();
    video.play().catch(() => {});
    setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(new Error('HLS timeout'));
    }, 5000);
  });
}

/* ---------------- liveness helpers ---------------- */
// Resolve only once real frames are flowing — not merely when the SDP/HLS
// handshake succeeds. Rejects on timeout so a stuck connection becomes a retry
// instead of a permanently "connected" black tile.
function waitForFirstFrame(video, timeoutMs) {
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (ok) => {
      if (done) return; done = true;
      video.removeEventListener('timeupdate', onTU);
      clearTimeout(timer);
      ok ? resolve() : reject(new Error('no frame'));
    };
    const onTU = () => { if (video.currentTime > 0) finish(true); };
    if ('requestVideoFrameCallback' in video)
      video.requestVideoFrameCallback(() => finish(true));
    video.addEventListener('timeupdate', onTU);
    const timer = setTimeout(() => finish(false), timeoutMs);
  });
}

// Detect silent freezes: frames stop advancing while the connection still
// looks alive. Returns a stop function.
function startFrameWatchdog(video, stallMs, onStall) {
  let last = -1, lastChange = Date.now();
  const id = setInterval(() => {
    const t = video.currentTime;
    if (t !== last) { last = t; lastChange = Date.now(); return; }
    if (Date.now() - lastChange > stallMs) onStall();
  }, 1000);
  return () => clearInterval(id);
}

// SINGLE source of truth for the overlay. Both the poll (telemetry) and the
// connection state machine call this; nothing else writes the veil. Heartbeat
// state and stream state can no longer contradict each other.
function applyState(t) {
  const n = t.node || {};
  let msg = null;
  if (t.paused) msg = 'PAUSED';
  else if (!n.online) msg = 'EYE OFFLINE';
  else if (t.connState === 'live') msg = null;
  else if (t.connState === 'connecting') msg = 'CONNECTING…';
  else if (t.connState === 'nosignal') msg = 'NO SIGNAL — RETRYING';
  else msg = 'RECONNECTING';
  t.veil.hidden = !msg;
  if (msg) t.veilMsg.textContent = msg;
}

/* ---------------- tiles ---------------- */
function irisClass(node) {
  if (!node.online) return 'offline';        // heartbeat lost
  // stream_ready is undefined on first load (not yet polled), treat as nosig
  if (node.stream_ready === false || node.stream_ready === undefined) return 'nosig';  // alive, but no video
  if (node.power_warn || node.temp_c >= 68) return 'hot';
  if (node.temp_c >= 60) return 'warm';
  return 'ok';
}

function makeTile(node) {
  const el = tpl.content.firstElementChild.cloneNode(true);
  el.dataset.name = node.name;
  el.querySelector('.cam-name').textContent = node.name;

  const t = {
    el, node, pc: null, paused: false, retry: null,
    connState: 'connecting', downGrace: null, stopWatch: null,
    zoom: 1, panX: 0, panY: 0,
    video: el.querySelector('video'),
    veil: el.querySelector('.veil'),
    veilMsg: el.querySelector('.veil-msg'),
    viewport: el.querySelector('.viewport'),
    iris: el.querySelector('.iris'),
    telemetry: el.querySelector('.telemetry'),
    zoomval: el.querySelector('.zoomval'),
  };

  const teardown = () => {
    clearTimeout(t.retry);
    clearTimeout(t.downGrace); t.downGrace = null;
    if (t.stopWatch) { t.stopWatch(); t.stopWatch = null; }
    if (t.pc) { try { t.pc.close(); } catch { /* */ } t.pc = null; }
    t.video.srcObject = null;
  };

  const setConn = (s) => { t.connState = s; applyState(t); };

  const reconnect = (ms, nosignal) => {
    teardown();
    if (t.paused) return;
    setConn(nosignal ? 'nosignal' : 'reconnecting');
    t.retry = setTimeout(connect, ms);
  };

  const connect = async () => {
    if (t.paused) return;
    teardown();
    setConn('connecting');
    try {
      const useHls = transportPref === 'hls';
      // WHEP for everyone by default (sub-second); HLS only via ?transport=hls.
      t.pc = useHls ? await hlsConnect(t.video, node.whep_path, () => {})
                    : await whepConnect(t.video, node.whep_path);

      if (!useHls && t.pc.addEventListener) {
        t.pc.addEventListener('connectionstatechange', () => {
          const s = t.pc.connectionState;
          if (s === 'failed' || s === 'closed') {
            reconnect(3000, false);
          } else if (s === 'disconnected') {
            // Transient on WiFi — let ICE try to self-heal for a few seconds
            // before tearing down, so a blip doesn't cause churn.
            clearTimeout(t.downGrace);
            t.downGrace = setTimeout(() => {
              if (t.pc && t.pc.connectionState !== 'connected') reconnect(2000, false);
            }, 5000);
          } else if (s === 'connected') {
            clearTimeout(t.downGrace); t.downGrace = null;
          }
        });
      }

      // Only declare success once frames actually arrive.
      await waitForFirstFrame(t.video, 9000);
      setConn('live');

      // Catch silent freezes (frames stop while the PC still looks connected).
      t.stopWatch = startFrameWatchdog(t.video, 6000, () => reconnect(1000, false));
    } catch {
      reconnect(4000, true);
    }
  };
  t.connect = connect;

  /* pause */
  const bPause = el.querySelector('.b-pause');
  bPause.addEventListener('click', () => {
    t.paused = !t.paused;
    bPause.textContent = t.paused ? 'resume' : 'pause';
    if (t.paused) {
      teardown();
      applyState(t);
    } else { connect(); }
  });

  /* zoom + pan */
  const applyZoom = () => {
    const m = (t.zoom - 1) / (2 * t.zoom);
    t.panX = Math.max(-m, Math.min(m, t.panX));
    t.panY = Math.max(-m, Math.min(m, t.panY));
    t.video.style.transform =
      `scale(${t.zoom}) translate(${t.panX * 100}%, ${t.panY * 100}%)`;
    t.zoomval.textContent = `${t.zoom.toFixed(1)}×`;
    t.viewport.classList.toggle('zoomed', t.zoom > 1);
  };
  const setZoom = (z) => { t.zoom = Math.max(1, Math.min(4, z)); if (t.zoom === 1) { t.panX = t.panY = 0; } applyZoom(); };
  el.querySelector('.b-zoom-in').addEventListener('click', () => setZoom(t.zoom + 0.5));
  el.querySelector('.b-zoom-out').addEventListener('click', () => setZoom(t.zoom - 0.5));
  el.querySelector('.b-fit').addEventListener('click', () => setZoom(1));
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

  /* tier override -> node agent via Cyclops */
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

  applyZoom();
  return t;
}

function updateTile(t, node) {
  const prevReady = t.node?.stream_ready;
  t.node = node;
  t.iris.className = `iris ${irisClass(node)}`;
  t.el.classList.toggle('seen', !!node.person && node.online);
  t.el.classList.toggle('powerwarn', !!node.power_warn && node.online);
  if (node.online) {
    let s = `${node.temp_c.toFixed(1)}°C · ${node.tier} · up ${fmtUp(node.uptime_s)}`;
    if (node.heartbeat_age_s !== undefined) s += ` · hb ${node.heartbeat_age_s.toFixed(1)}s`;
    if (node.power_warn) s += ' · ⚡LOW PWR';
    t.telemetry.textContent = s;
  } else {
    t.telemetry.textContent = 'OFFLINE';
  }
  applyState(t);   // veil reflects heartbeat + connection together
  // If stream just became ready and we're not paused, connect
  if (node.stream_ready === true && prevReady !== true && !t.paused && !t.pc) {
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
      stack.appendChild(t.el);              // append order == stack order
      // Only connect if stream_ready is true (not undefined/false)
      if (!t.pc && !t.paused && t.node.stream_ready === true) t.connect();
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
      if (!layout.order.includes(node.name)) layout.order.push(node.name); // new eyes: bottom
      added = true;
    }
    updateTile(tiles.get(node.name), node);
  }
  if (added) render();
  const online = nodes.filter(n => n.online).length;
  const streaming = nodes.filter(n => n.online && n.stream_ready).length;
  const blind = online - streaming;
  const hot = nodes.filter(n => n.online && (n.temp_c >= 68 || n.power_warn)).length;
  sysline.textContent =
    `${streaming}/${nodes.length} streaming` +
    (blind ? ` · ${blind} no-signal` : '') +
    (hot ? ` · ${hot} hot` : '');
  sysIris.className = `iris iris-lg ${
    streaming === 0 ? 'offline'
    : blind ? 'nosig'
    : hot ? 'hot'
    : streaming < nodes.length ? 'warm' : 'ok'}`;
}

(async function init() {
  try { layout = await (await fetch('/api/layout')).json(); } catch { /* defaults */ }
  await poll();
  render();
  setInterval(poll, 3000);
})();

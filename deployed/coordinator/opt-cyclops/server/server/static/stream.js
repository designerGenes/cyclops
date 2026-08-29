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
async function whepConnect(video, path, onDown) {
  const pc = new RTCPeerConnection({ iceServers: [] });
  pc.addTransceiver('video', { direction: 'recvonly' });
  pc.ontrack = (e) => { video.srcObject = e.streams[0]; };
  pc.onconnectionstatechange = () => {
    if (['failed', 'disconnected', 'closed'].includes(pc.connectionState)) onDown();
  };
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

function canUseNativeHls(video) {
  return video.canPlayType('application/vnd.apple.mpegurl') !== '' && false;
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

/* ---------------- tiles ---------------- */
function irisClass(node) {
  if (!node.online) return 'offline';
  if (node.temp_c >= 68) return 'hot';
  if (node.temp_c >= 60) return 'warm';
  return 'ok';
}

function makeTile(node) {
  const el = tpl.content.firstElementChild.cloneNode(true);
  el.dataset.name = node.name;
  el.querySelector('.cam-name').textContent = node.name;

  const t = {
    el, node, pc: null, paused: false, retry: null,
    zoom: 1, panX: 0, panY: 0,
    video: el.querySelector('video'),
    veil: el.querySelector('.veil'),
    veilMsg: el.querySelector('.veil-msg'),
    viewport: el.querySelector('.viewport'),
    iris: el.querySelector('.iris'),
    telemetry: el.querySelector('.telemetry'),
    zoomval: el.querySelector('.zoomval'),
  };

  const veil = (msg) => {
    t.veil.hidden = !msg;
    if (msg) t.veilMsg.textContent = msg;
  };

  const connect = async () => {
    if (t.paused) return;
    clearTimeout(t.retry);
    try {
      const preferHls = transportPref === 'hls' || (transportPref === 'auto' && canUseNativeHls(t.video));
      const connector = preferHls ? hlsConnect : whepConnect;
      t.pc = await connector(t.video, node.whep_path, () => {
        if (t.pc) { t.pc.close(); t.pc = null; }
        veil('RECONNECTING');
        t.retry = setTimeout(connect, 3000);
      });
      veil(null);
    } catch {
      veil('NO SIGNAL — RETRYING');
      t.retry = setTimeout(connect, 4000);
    }
  };
  t.connect = connect;

  /* pause */
  const bPause = el.querySelector('.b-pause');
  bPause.addEventListener('click', () => {
    t.paused = !t.paused;
    bPause.textContent = t.paused ? 'resume' : 'pause';
    if (t.paused) {
      clearTimeout(t.retry);
      if (t.pc) { t.pc.close(); t.pc = null; }
      t.video.srcObject = null;
      veil('PAUSED');
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
  t.node = node;
  t.iris.className = `iris ${irisClass(node)}`;
  t.el.classList.toggle('seen', !!node.person && node.online);
  t.telemetry.textContent = node.online
    ? `${node.temp_c.toFixed(1)}°C · ${node.tier} · up ${fmtUp(node.uptime_s)}`
    : 'OFFLINE';
  if (!node.online && !t.paused) {
    t.veil.hidden = false; t.veilMsg.textContent = 'EYE OFFLINE';
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
      if (!t.pc && !t.paused) t.connect();
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
  const hot = nodes.filter(n => n.online && n.temp_c >= 68).length;
  sysline.textContent =
    `${online}/${nodes.length} eyes online${hot ? ` · ${hot} hot` : ''}`;
  sysIris.className = `iris iris-lg ${online === 0 ? 'offline' : hot ? 'hot' : online < nodes.length ? 'warm' : 'ok'}`;
}

(async function init() {
  try { layout = await (await fetch('/api/layout')).json(); } catch { /* defaults */ }
  await poll();
  render();
  setInterval(poll, 3000);
})();

import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import type { CameraNode, CameraSettings, LayoutTile } from '@cyclops/contracts';
import { apiClient } from '../api/client';
import { OfflineTile } from './OfflineTile';

type PictureInPictureWindow = Window & {
  documentPictureInPicture?: {
    requestWindow: (options?: { width?: number; height?: number }) => Promise<Window>;
  };
};

interface CameraTileProps {
  camera: CameraNode;
  tile: LayoutTile;
  index: number;
  total: number;
  fillViewport?: boolean;
  onMove: (fromIndex: number, toIndex: number) => void;
  onResize: (cameraId: string, heightPx: number) => void;
  onHide: (cameraId: string) => void;
}

export function CameraTile({ camera, tile, index, total, fillViewport = false, onMove, onResize, onHide }: CameraTileProps) {
  const dragStartY = useRef<number | null>(null);
  const resizeStart = useRef<{ y: number; height: number } | null>(null);
  const [streamFailed, setStreamFailed] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [settings, setSettings] = useState<CameraSettings | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [paused, setPaused] = useState(false);
  const [rewindSeconds, setRewindSeconds] = useState(0);
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null);
  const [controlMessage, setControlMessage] = useState<string | null>(null);

  const cameraBaseUrl = camera.stream_url.replace(/\/stream$/, '');
  const frameSrc = paused || rewindSeconds > 0
    ? snapshotUrl ?? `${cameraBaseUrl}/api/v1/frame?seconds_ago=${rewindSeconds}&t=${now}`
    : `${camera.stream_url}?t=${now}`;

  useEffect(() => {
    setStreamFailed(false);
  }, [camera.stream_url, camera.status]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    apiClient.getCameraSettings(cameraBaseUrl).then((next) => {
      if (active) setSettings(next);
    }).catch(() => {
      if (active) setControlMessage('Camera settings unavailable');
    });
    return () => {
      active = false;
    };
  }, [cameraBaseUrl]);

  useEffect(() => {
    if (!paused && rewindSeconds === 0) {
      setSnapshotUrl(null);
      return;
    }
    let active = true;
    const nextUrl = `${cameraBaseUrl}/api/v1/frame?seconds_ago=${rewindSeconds}&t=${Date.now()}`;
    if (active) setSnapshotUrl(nextUrl);
    return () => {
      active = false;
    };
  }, [cameraBaseUrl, paused, rewindSeconds, now]);

  const statusClass = camera.status === 'online' ? 'badge--online' : camera.status === 'degraded' ? 'badge--degraded' : 'badge--offline';
  const showOffline = camera.status !== 'online' || streamFailed;
  const heartbeatText = camera.last_seen_at
    ? `${Math.max(0, Math.round((now - new Date(camera.last_seen_at).getTime()) / 1000))}s since coordinator heartbeat`
    : 'Awaiting heartbeat';

  const openFloatingView = async () => {
    const renderFloatingDocument = (targetWindow: Window) => {
      targetWindow.document.title = `${camera.name} live view`;
      targetWindow.document.body.innerHTML = '';
      targetWindow.document.body.style.margin = '0';
      targetWindow.document.body.style.background = '#020617';
      targetWindow.document.body.style.color = '#f8fafc';
      targetWindow.document.body.style.fontFamily = 'Inter, system-ui, sans-serif';
      const wrapper = targetWindow.document.createElement('div');
      wrapper.style.display = 'grid';
      wrapper.style.gridTemplateRows = 'auto 1fr';
      wrapper.style.height = '100vh';
      const header = targetWindow.document.createElement('div');
      header.style.padding = '12px';
      header.style.background = 'rgba(15, 23, 42, 0.95)';
      header.style.borderBottom = '1px solid #1e293b';
      header.innerHTML = `<strong>${camera.name}</strong><div style="font-size:12px;color:#cbd5e1;">${heartbeatText}</div>`;
      const image = targetWindow.document.createElement('img');
      image.src = frameSrc;
      image.alt = `${camera.name} live stream`;
      image.style.width = '100%';
      image.style.height = '100%';
      image.style.objectFit = 'contain';
      image.style.background = '#000';
      wrapper.append(header, image);
      targetWindow.document.body.append(wrapper);
    };

    const topWindow = window as PictureInPictureWindow;
    if (topWindow.documentPictureInPicture) {
      const pipWindow = await topWindow.documentPictureInPicture.requestWindow({ width: 420, height: 380 });
      renderFloatingDocument(pipWindow);
      return;
    }

    const popup = window.open('', `cyclops-pip-${camera.id}`, 'popup=yes,width=420,height=380');
    if (popup) {
      renderFloatingDocument(popup);
    }
  };

  const onDragPointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    dragStartY.current = event.clientY;
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onDragPointerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (dragStartY.current === null) return;
    const delta = event.clientY - dragStartY.current;
    if (delta > 48 && index < total - 1) {
      onMove(index, index + 1);
      dragStartY.current = event.clientY;
    }
    if (delta < -48 && index > 0) {
      onMove(index, index - 1);
      dragStartY.current = event.clientY;
    }
  };

  const onResizePointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    resizeStart.current = { y: event.clientY, height: tile.height_px };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onResizePointerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!resizeStart.current) return;
    onResize(camera.id, resizeStart.current.height + (event.clientY - resizeStart.current.y));
  };

  const requestFullscreen = async () => {
    const tile = document.querySelector(`[data-testid="tile-${camera.id}"]`) as HTMLElement | null;
    if (!tile) return;
    if (document.fullscreenElement === tile) {
      await document.exitFullscreen();
      return;
    }
    await tile.requestFullscreen();
  };

  const applyQuickSettings = async (patch: Partial<CameraSettings>) => {
    if (!settings) return;
    const next = { ...settings, ...patch };
    const response = await apiClient.updateCameraSettings(cameraBaseUrl, next);
    setSettings(response.settings);
    setControlMessage(response.restart_required ? 'Camera settings applied and restarted' : 'Camera settings applied');
    setPaused(false);
    setRewindSeconds(0);
    setNow(Date.now());
  };

  const restartStream = async () => {
    const response = await apiClient.restartCameraStream(cameraBaseUrl);
    setPaused(false);
    setRewindSeconds(0);
    setNow(Date.now());
    setControlMessage(response.detail);
  };

  return (
    <article
      className="camera-tile"
      style={{ height: fillViewport ? 'calc(100vh - 112px)' : `${tile.height_px}px` }}
      data-testid={`tile-${camera.id}`}
    >
      <div className="camera-tile__header">
        <div>
          <h2>{camera.name}</h2>
          <p>{camera.last_seen_at ? `Last seen ${new Date(camera.last_seen_at).toLocaleString()}` : 'Never seen online'}</p>
        </div>
        <div className="camera-tile__actions">
          <span className={`badge ${statusClass}`}>{camera.status}</span>
          <button
            type="button"
            aria-label={`Move ${camera.name} up`}
            className="control-button"
            disabled={index === 0}
            onClick={() => onMove(index, index - 1)}
          >
            ↑
          </button>
          <button
            type="button"
            aria-label={`Move ${camera.name} down`}
            className="control-button"
            disabled={index === total - 1}
            onClick={() => onMove(index, index + 1)}
          >
            ↓
          </button>
          <button type="button" aria-label={`Picture in picture ${camera.name}`} className="control-button" onClick={() => { void openFloatingView(); }}>
            PiP
          </button>
          <button type="button" aria-label={`Fullscreen ${camera.name}`} className="control-button" onClick={() => { void requestFullscreen(); }}>
            Full
          </button>
          <button
            type="button"
            aria-label={`Hide ${camera.name}`}
            className="control-button control-button--ghost"
            onClick={() => onHide(camera.id)}
          >
            Hide
          </button>
          <button
            type="button"
            aria-label={`Reorder ${camera.name}`}
            className="handle-button"
            data-testid={`drag-handle-${camera.id}`}
            onPointerDown={onDragPointerDown}
            onPointerMove={onDragPointerMove}
            onPointerUp={() => {
              dragStartY.current = null;
            }}
          >
            ☰ Drag
          </button>
        </div>
      </div>

      <div className="camera-tile__body">
        <div className="stream-stage">
        {showOffline ? (
          <OfflineTile camera={{ ...camera, status: streamFailed ? 'offline' : camera.status }} />
        ) : (
            <img
              src={frameSrc}
              alt={`${camera.name} live stream`}
              className="stream-image"
              onError={() => setStreamFailed(true)}
            />
        )}
          <div className="stream-overlay">
            <div className="live-pill">
              <span className="live-pill__dot" />
              <span>
                {showOffline
                  ? 'Reconnecting'
                  : paused
                    ? `Paused ${rewindSeconds > 0 ? `-${rewindSeconds}s` : ''}`
                    : `Live ${new Date(now).toLocaleTimeString([], { hour12: false })}`}
              </span>
            </div>
            <div className="stream-overlay__meta">
              <span>{camera.hostname ?? camera.tailscale_ip ?? camera.id}</span>
              <span>{heartbeatText}</span>
              <span>{camera.software_version ? `v${camera.software_version}` : 'version unknown'}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="camera-tile__footer">
        <div className="camera-tile__control-strip">
          <button type="button" className="control-button" onClick={() => { setPaused((value) => !value); setRewindSeconds(0); setNow(Date.now()); }}>
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button type="button" className="control-button" onClick={() => { setPaused(true); setRewindSeconds((value) => value + 5); setNow(Date.now()); }}>
            -5s
          </button>
          <button type="button" className="control-button" onClick={() => { setPaused(false); setRewindSeconds(0); setNow(Date.now()); setControlMessage('Stream reloaded'); }}>
            Reload
          </button>
          <button type="button" className="control-button" onClick={() => { void restartStream(); }}>
            Restart
          </button>
          <button
            type="button"
            className="control-button"
            aria-label={`Open camera controls ${camera.name}`}
            onClick={() => setSettingsOpen((value) => !value)}
          >
            Camera
          </button>
        </div>
        <a href={camera.settings_url} target="_blank" rel="noreferrer">Open Settings</a>
        <a href={camera.stream_url} target="_blank" rel="noreferrer">Open Stream</a>
      </div>

      {settingsOpen && settings ? (
        <div className="camera-tile__settings-panel">
          <div className="camera-tile__settings-grid">
            <label>
              Resolution
              <select
                value={`${settings.stream_width}x${settings.stream_height}`}
                onChange={(event) => {
                  const [width, height] = event.target.value.split('x').map(Number);
                  void applyQuickSettings({ stream_width: width, stream_height: height });
                }}
              >
                <option value="640x360">640x360</option>
                <option value="960x540">960x540</option>
                <option value="1280x720">1280x720</option>
              </select>
            </label>
            <label>
              Codec
              <select value="MJPEG" onChange={() => setControlMessage('MJPEG is the only current stream codec in phase 1')}>
                <option value="MJPEG">MJPEG</option>
                <option value="H264">H264 (planned)</option>
              </select>
            </label>
            <label>
              Frame rate
              <select value={settings.frame_rate} onChange={(event) => { void applyQuickSettings({ frame_rate: Number(event.target.value) }); }}>
                <option value={3}>3 fps</option>
                <option value={5}>5 fps</option>
                <option value={8}>8 fps</option>
                <option value={10}>10 fps</option>
              </select>
            </label>
            <label>
              Quality
              <select value={settings.jpeg_quality} onChange={(event) => { void applyQuickSettings({ jpeg_quality: Number(event.target.value) }); }}>
                <option value={60}>60</option>
                <option value={75}>75</option>
                <option value={85}>85</option>
                <option value={92}>92</option>
              </select>
            </label>
            <label>
              Tile height
              <input
                type="range"
                min={180}
                max={720}
                step={10}
                value={tile.height_px}
                onChange={(event) => onResize(camera.id, Number(event.target.value))}
              />
            </label>
          </div>
          {controlMessage ? <div className="camera-tile__message">{controlMessage}</div> : null}
        </div>
      ) : null}

      <button
        type="button"
        aria-label={`Resize ${camera.name}`}
        className="resize-handle"
        data-testid={`resize-handle-${camera.id}`}
        onPointerDown={onResizePointerDown}
        onPointerMove={onResizePointerMove}
        onPointerUp={() => {
          resizeStart.current = null;
        }}
      >
        ↕ Resize
      </button>
    </article>
  );
}

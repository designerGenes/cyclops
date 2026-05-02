import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import type { CameraNode, LayoutTile } from '@cyclops/contracts';
import { OfflineTile } from './OfflineTile';

interface CameraTileProps {
  camera: CameraNode;
  tile: LayoutTile;
  index: number;
  total: number;
  fillViewport?: boolean;
  onMove: (fromIndex: number, toIndex: number) => void;
  onResize: (cameraId: string, heightPx: number) => void;
}

export function CameraTile({ camera, tile, index, total, fillViewport = false, onMove, onResize }: CameraTileProps) {
  const dragStartY = useRef<number | null>(null);
  const resizeStart = useRef<{ y: number; height: number } | null>(null);
  const [streamFailed, setStreamFailed] = useState(false);

  useEffect(() => {
    setStreamFailed(false);
  }, [camera.stream_url, camera.status]);

  const statusClass = camera.status === 'online' ? 'badge--online' : camera.status === 'degraded' ? 'badge--degraded' : 'badge--offline';
  const showOffline = camera.status !== 'online' || streamFailed;

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
        {showOffline ? (
          <OfflineTile camera={{ ...camera, status: streamFailed ? 'offline' : camera.status }} />
        ) : (
          <img
            src={camera.stream_url}
            alt={`${camera.name} live stream`}
            className="stream-image"
            onError={() => setStreamFailed(true)}
          />
        )}
      </div>

      <div className="camera-tile__footer">
        <a href={camera.settings_url} target="_blank" rel="noreferrer">Open Settings</a>
        <a href={camera.stream_url} target="_blank" rel="noreferrer">Open Stream</a>
      </div>

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

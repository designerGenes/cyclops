import type { CameraNode, Layout } from '@cyclops/contracts';
import { CameraTile } from './CameraTile';
import { mergeTilesWithCameras, moveTile, resizeTile, toggleTileVisibility } from '../state/layout';

interface CameraTileListProps {
  cameras: CameraNode[];
  layout: Layout;
  setLayout: (layout: Layout) => void;
}

export function CameraTileList({ cameras, layout, setLayout }: CameraTileListProps) {
  const merged = mergeTilesWithCameras(cameras, layout);
  const cameraMap = new Map(cameras.map((camera) => [camera.id, camera]));
  const hiddenCameras = layout.tiles
    .filter((tile) => !tile.visible)
    .map((tile) => cameraMap.get(tile.camera_id))
    .filter(Boolean) as CameraNode[];

  if (cameras.length === 0) {
    return <div className="empty-state">No cameras are registered yet.</div>;
  }

  return (
    <>
      <section className="tile-list" data-testid="tile-list">
        {merged.map((camera, index) => (
          <CameraTile
            key={camera.id}
            camera={camera}
            tile={camera.tile}
            index={index}
            total={merged.length}
            fillViewport={merged.length === 1}
            onMove={(fromIndex, toIndex) => setLayout(moveTile(layout, fromIndex, toIndex))}
            onResize={(cameraId, heightPx) => setLayout(resizeTile(layout, cameraId, heightPx))}
            onHide={(cameraId) => setLayout(toggleTileVisibility(layout, cameraId, false))}
          />
        ))}
      </section>
      {hiddenCameras.length > 0 ? (
        <section className="hidden-tray" data-testid="hidden-tray">
          <div>
            <strong>Hidden cameras</strong>
            <p>Restore any feed without losing its order or height.</p>
          </div>
          <div className="hidden-tray__actions">
            {hiddenCameras.map((camera) => (
              <button
                key={camera.id}
                type="button"
                className="control-button"
                data-testid={`show-camera-${camera.id}`}
                onClick={() => setLayout(toggleTileVisibility(layout, camera.id, true))}
              >
                Show {camera.name}
              </button>
            ))}
            <button
              type="button"
              className="control-button control-button--ghost"
              onClick={() => {
                let nextLayout = layout;
                hiddenCameras.forEach((camera) => {
                  nextLayout = toggleTileVisibility(nextLayout, camera.id, true);
                });
                setLayout(nextLayout);
              }}
            >
              Show all
            </button>
          </div>
        </section>
      ) : null}
    </>
  );
}

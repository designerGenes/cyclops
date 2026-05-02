import type { CameraNode, Layout } from '@cyclops/contracts';
import { CameraTile } from './CameraTile';
import { mergeTilesWithCameras, moveTile, resizeTile } from '../state/layout';

interface CameraTileListProps {
  cameras: CameraNode[];
  layout: Layout;
  setLayout: (layout: Layout) => void;
}

export function CameraTileList({ cameras, layout, setLayout }: CameraTileListProps) {
  const merged = mergeTilesWithCameras(cameras, layout);

  if (cameras.length === 0) {
    return <div className="empty-state">No cameras are registered yet.</div>;
  }

  return (
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
        />
      ))}
    </section>
  );
}

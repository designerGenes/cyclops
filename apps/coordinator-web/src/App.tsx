import { CameraTileList } from './components/CameraTileList';
import { LayoutToolbar } from './components/LayoutToolbar';
import { useCameraRegistry } from './hooks/useCameraRegistry';
import { useLayoutPersistence } from './hooks/useLayoutPersistence';

export default function App() {
  const { cameras, loading, error: cameraError } = useCameraRegistry();
  const { layout, setLayout, error: layoutError } = useLayoutPersistence(cameras);
  const onlineCount = cameras.filter((camera) => camera.status === 'online').length;
  const hiddenCount = layout.tiles.filter((tile) => !tile.visible).length;

  return (
    <main className="app-shell">
      <LayoutToolbar
        cameraCount={cameras.length}
        onlineCount={onlineCount}
        hiddenCount={hiddenCount}
        error={cameraError ?? layoutError}
      />
      {loading ? <div className="empty-state">Loading cameras…</div> : null}
      {!loading && cameraError ? <div className="empty-state">Coordinator API unavailable: {cameraError}</div> : null}
      {!loading && !cameraError ? <CameraTileList cameras={cameras} layout={layout} setLayout={setLayout} /> : null}
    </main>
  );
}

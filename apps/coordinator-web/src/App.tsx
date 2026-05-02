import { CameraTileList } from './components/CameraTileList';
import { LayoutToolbar } from './components/LayoutToolbar';
import { useCameraRegistry } from './hooks/useCameraRegistry';
import { useLayoutPersistence } from './hooks/useLayoutPersistence';

export default function App() {
  const { cameras, loading, error: cameraError } = useCameraRegistry();
  const { layout, setLayout, error: layoutError } = useLayoutPersistence(cameras);

  return (
    <main className="app-shell">
      <LayoutToolbar cameraCount={cameras.length} error={cameraError ?? layoutError} />
      {loading ? <div className="empty-state">Loading cameras…</div> : null}
      {!loading && cameraError ? <div className="empty-state">Coordinator API unavailable: {cameraError}</div> : null}
      {!loading && !cameraError ? <CameraTileList cameras={cameras} layout={layout} setLayout={setLayout} /> : null}
    </main>
  );
}

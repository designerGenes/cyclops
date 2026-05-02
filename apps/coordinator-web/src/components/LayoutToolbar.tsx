interface LayoutToolbarProps {
  cameraCount: number;
  error: string | null;
}

export function LayoutToolbar({ cameraCount, error }: LayoutToolbarProps) {
  return (
    <header className="toolbar">
      <div>
        <h1>Cyclops</h1>
        <p>{cameraCount} camera{cameraCount === 1 ? '' : 's'}</p>
      </div>
      <div className="toolbar__status" aria-live="polite">
        {error ? <span className="badge badge--error">{error}</span> : <span className="badge">Layout synced</span>}
      </div>
    </header>
  );
}

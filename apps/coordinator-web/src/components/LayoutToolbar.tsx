interface LayoutToolbarProps {
  cameraCount: number;
  onlineCount: number;
  hiddenCount: number;
  error: string | null;
}

export function LayoutToolbar({ cameraCount, onlineCount, hiddenCount, error }: LayoutToolbarProps) {
  return (
    <header className="toolbar">
      <div>
        <h1>Cyclops</h1>
        <p>
          {onlineCount} live / {cameraCount} camera{cameraCount === 1 ? '' : 's'}
          {hiddenCount > 0 ? ` / ${hiddenCount} hidden` : ''}
        </p>
      </div>
      <div className="toolbar__status" aria-live="polite">
        {error ? <span className="badge badge--error">{error}</span> : <span className="badge">Layout synced</span>}
      </div>
    </header>
  );
}

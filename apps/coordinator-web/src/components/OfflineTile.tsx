import type { CameraNode } from '@cyclops/contracts';

export function OfflineTile({ camera }: { camera: CameraNode }) {
  return (
    <div className="offline-panel" data-testid={`offline-${camera.id}`}>
      <strong>{camera.status === 'unknown' ? 'camera status unknown' : 'stream unavailable'}</strong>
      <span>{camera.last_seen_at ? `Last seen ${new Date(camera.last_seen_at).toLocaleString()}` : 'No successful health check yet'}</span>
    </div>
  );
}

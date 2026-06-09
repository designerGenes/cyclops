import { useEffect, useState } from 'react';
import type { CameraNode } from '@cyclops/contracts';
import { apiClient } from '../api/client';

export function useCameraRegistry() {
  const [cameras, setCameras] = useState<CameraNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        const next = await apiClient.getCameras();
        if (!active) return;
        setCameras(next);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Coordinator API unavailable');
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void load();
    const interval = window.setInterval(() => void load(), 10_000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return { cameras, loading, error };
}

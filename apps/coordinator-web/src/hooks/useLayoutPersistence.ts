import { useEffect, useMemo, useRef, useState } from 'react';
import type { CameraNode, Layout } from '@cyclops/contracts';
import { apiClient } from '../api/client';
import { LAYOUT_STORAGE_KEY, reconcileLayout } from '../state/layout';

export function useLayoutPersistence(cameras: CameraNode[]) {
  const [layout, setLayout] = useState<Layout | null>(null);
  const [error, setError] = useState<string | null>(null);
  const saveTimer = useRef<number | null>(null);
  const initialized = useRef(false);

  useEffect(() => {
    let active = true;

    const bootstrap = async () => {
      const stored = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
      const localLayout = stored ? (JSON.parse(stored) as Layout) : null;

      if (cameras.length === 0) {
        setLayout((current) => current ?? reconcileLayout(localLayout, cameras));
        return;
      }

      setLayout((current) => reconcileLayout(current ?? localLayout, cameras));

      try {
        const remote = await apiClient.getLayout();
        if (!active) return;
        const resolved = reconcileLayout(remote, cameras);
        setLayout(resolved);
        window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(resolved));
        setError(null);
      } catch {
        if (!active) return;
        const resolved = reconcileLayout(localLayout, cameras);
        setLayout(resolved);
      } finally {
        if (active) {
          initialized.current = true;
        }
      }
    };

    void bootstrap();

    return () => {
      active = false;
    };
  }, [cameras]);

  useEffect(() => {
    if (!layout || !initialized.current) {
      return;
    }

    window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
    if (saveTimer.current) {
      window.clearTimeout(saveTimer.current);
    }
    saveTimer.current = window.setTimeout(async () => {
      try {
        await apiClient.saveLayout(layout);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to persist layout');
      }
    }, 500);

    return () => {
      if (saveTimer.current) {
        window.clearTimeout(saveTimer.current);
      }
    };
  }, [layout]);

  const value = useMemo(() => layout ?? reconcileLayout(null, cameras), [layout, cameras]);

  return { layout: value, setLayout, error };
}

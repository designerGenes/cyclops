import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CameraNode, Layout } from '@cyclops/contracts';
import { useLayoutPersistence } from '../hooks/useLayoutPersistence';
import { LAYOUT_STORAGE_KEY, generateDefaultLayout, moveTile, reconcileLayout, resizeTile } from '../state/layout';

const cameras: CameraNode[] = [
  {
    id: 'a',
    name: 'A',
    hostname: null,
    tailscale_ip: null,
    stream_url: '/a',
    settings_url: '/a/settings',
    health_url: '/a/healthz',
    status: 'online',
    last_seen_at: null,
    software_version: '0.1.0',
    capabilities: { provider: 'mock', stream_kind: 'mjpeg', supports_settings: true, supports_future_analytics_ingest: true },
  },
  {
    id: 'b',
    name: 'B',
    hostname: null,
    tailscale_ip: null,
    stream_url: '/b',
    settings_url: '/b/settings',
    health_url: '/b/healthz',
    status: 'offline',
    last_seen_at: null,
    software_version: '0.1.0',
    capabilities: { provider: 'mock', stream_kind: 'mjpeg', supports_settings: true, supports_future_analytics_ingest: true },
  },
];

describe('layout state', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === 'PUT') {
          return new Response(init.body as BodyInit, { status: 200 });
        }
        return new Response(JSON.stringify(generateDefaultLayout(cameras)), { status: 200 });
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('updates drag reorder state', () => {
    const layout = generateDefaultLayout(cameras);
    expect(moveTile(layout, 0, 1).tiles.map((tile: Layout['tiles'][number]) => tile.camera_id)).toEqual(['b', 'a']);
  });

  it('updates resize state', () => {
    const layout = generateDefaultLayout(cameras);
    expect(resizeTile(layout, 'a', 999).tiles[0].height_px).toBe(720);
  });

  it('cleans up stale layout and appends new cameras', () => {
    const stale: Layout = {
      layout_id: 'default',
      updated_at: new Date().toISOString(),
      tiles: [{ camera_id: 'missing', order: 0, height_px: 200, visible: true }],
    };
    expect(reconcileLayout(stale, cameras).tiles.map((tile: Layout['tiles'][number]) => tile.camera_id)).toEqual(['a', 'b']);
  });

  it('persists layout to localStorage', async () => {
    const { result } = renderHook(() => useLayoutPersistence(cameras));
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      result.current.setLayout(moveTile(result.current.layout, 0, 1));
      vi.advanceTimersByTime(500);
      await Promise.resolve();
    });
    expect(JSON.parse(window.localStorage.getItem(LAYOUT_STORAGE_KEY) ?? '{}').tiles[0].camera_id).toBe('b');
  });

  it('reconciles layouts when cameras arrive after an empty bootstrap', async () => {
    let resolveLayout: ((value: Response) => void) | null = null;
    const layoutRequest = new Promise<Response>((resolve) => {
      resolveLayout = resolve;
    });

    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === 'PUT') {
          return new Response(init.body as BodyInit, { status: 200 });
        }

        return layoutRequest;
      }),
    );

    const { result, rerender } = renderHook(({ currentCameras }: { currentCameras: CameraNode[] }) => useLayoutPersistence(currentCameras), {
      initialProps: { currentCameras: [] as CameraNode[] },
    });

    expect(result.current.layout.tiles).toHaveLength(0);

    await act(async () => {
      rerender({ currentCameras: cameras });
      await Promise.resolve();
    });

    expect(result.current.layout.tiles.map((tile: Layout['tiles'][number]) => tile.camera_id)).toEqual(['a', 'b']);

    await act(async () => {
      resolveLayout?.(new Response(JSON.stringify(generateDefaultLayout(cameras)), { status: 200 }));
      await Promise.resolve();
    });
  });
});

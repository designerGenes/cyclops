import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

const cameras = Array.from({ length: 5 }, (_, index) => ({
  id: `cam-${index + 1}`,
  name: `Camera ${index + 1}`,
  hostname: null,
  tailscale_ip: null,
  stream_url: `/stream/${index + 1}`,
  settings_url: `/settings/${index + 1}`,
  health_url: `/health/${index + 1}`,
  status: index === 3 ? 'offline' : 'online',
  last_seen_at: null,
  software_version: '0.1.0',
  capabilities: {
    provider: 'mock',
    stream_kind: 'mjpeg',
    supports_settings: true,
    supports_future_analytics_ingest: true,
  },
}));

function mockResponses(nextCameras = cameras) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/cameras')) {
        return new Response(JSON.stringify(nextCameras), { status: 200 });
      }
      if (url.includes('/api/v1/layouts/default')) {
        return new Response(
          JSON.stringify({
            layout_id: 'default',
            updated_at: new Date().toISOString(),
            tiles: nextCameras.map((camera, index) => ({ camera_id: camera.id, order: index, height_px: 240, visible: true })),
          }),
          { status: 200 },
        );
      }
      return new Response('{}', { status: 200 });
    }),
  );
}

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockResponses();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders 1, 2, 3, 4, and N tiles from api data', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('tile-list')).toBeInTheDocument());
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(5);
  });

  it('renders single camera view', async () => {
    mockResponses([cameras[0]]);
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(1));
  });

  it('renders two camera view', async () => {
    mockResponses(cameras.slice(0, 2));
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(2));
  });

  it('renders three camera view', async () => {
    mockResponses(cameras.slice(0, 3));
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(3));
  });

  it('renders four camera view', async () => {
    mockResponses(cameras.slice(0, 4));
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(4));
  });

  it('renders offline tile state', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('offline-cam-4')).toBeInTheDocument());
    expect(screen.getByText(/stream unavailable/i)).toBeInTheDocument();
  });

  it('can hide and restore a camera tile', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('tile-list')).toBeInTheDocument());
    await user.click(screen.getByLabelText('Hide Camera 1'));
    expect(screen.getByTestId('hidden-tray')).toBeInTheDocument();
    expect(screen.queryByText('Camera 1')).not.toBeInTheDocument();
    await user.click(screen.getByTestId('show-camera-cam-1'));
    expect(await screen.findByText('Camera 1')).toBeInTheDocument();
  });
});

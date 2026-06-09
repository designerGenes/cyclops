import type { CameraNode, CameraSettings, Layout } from '@cyclops/contracts';

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? response.statusText);
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  getCameras: () => requestJson<CameraNode[]>('/api/v1/cameras'),
  getLayout: () => requestJson<Layout>('/api/v1/layouts/default'),
  saveLayout: (layout: Layout) =>
    requestJson<Layout>('/api/v1/layouts/default', {
      method: 'PUT',
      body: JSON.stringify(layout),
    }),
  getCameraSettings: (baseUrl: string) => requestJson<CameraSettings>(`${baseUrl}/api/v1/settings`),
  updateCameraSettings: (baseUrl: string, settings: CameraSettings) =>
    requestJson<{ settings: CameraSettings; restart_required: boolean; restart_performed: boolean }>(`${baseUrl}/api/v1/settings`, {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  restartCameraStream: (baseUrl: string) =>
    requestJson<{ detail: string }>(`${baseUrl}/api/v1/stream/restart`, {
      method: 'POST',
    }),
};

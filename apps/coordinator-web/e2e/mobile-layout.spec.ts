import { expect, test } from '@playwright/test';

test('mobile stacked layout persists reorder and resize while offline tile remains visible', async ({ page }) => {
  let layout = {
    layout_id: 'default',
    updated_at: new Date().toISOString(),
    tiles: [
      { camera_id: 'nilescrane', order: 0, height_px: 240, visible: true },
      { camera_id: 'daphnemoon', order: 1, height_px: 240, visible: true },
    ],
  };

  await page.route('**/api/v1/cameras', async (route) => {
    await route.fulfill({
      json: [
        {
          id: 'nilescrane',
          name: 'Niles Crane',
          hostname: 'nilescrane.local',
          tailscale_ip: '100.64.0.10',
          stream_url: 'http://127.0.0.1:9/stream',
          settings_url: 'http://127.0.0.1:9/settings',
          health_url: 'http://127.0.0.1:9/healthz',
          status: 'online',
          last_seen_at: null,
          software_version: '0.1.0',
          capabilities: { provider: 'mock', stream_kind: 'mjpeg', supports_settings: true, supports_future_analytics_ingest: true },
        },
        {
          id: 'daphnemoon',
          name: 'Daphne Moon',
          hostname: 'daphnemoon.local',
          tailscale_ip: '100.64.0.11',
          stream_url: 'http://127.0.0.1:9/stream',
          settings_url: 'http://127.0.0.1:9/settings',
          health_url: 'http://127.0.0.1:9/healthz',
          status: 'offline',
          last_seen_at: '2026-01-01T00:00:00+00:00',
          software_version: '0.1.0',
          capabilities: { provider: 'mock', stream_kind: 'mjpeg', supports_settings: true, supports_future_analytics_ingest: true },
        },
      ],
    });
  });

  await page.route('**/api/v1/layouts/default', async (route) => {
    if (route.request().method() === 'PUT') {
      layout = JSON.parse(route.request().postData() ?? '{}');
      await route.fulfill({ body: JSON.stringify(layout), contentType: 'application/json' });
      return;
    }

    await route.fulfill({
      json: layout,
    });
  });

  await page.goto('/');
  await expect(page.getByTestId('tile-list')).toBeVisible();
  await expect(page.getByTestId('offline-daphnemoon')).toBeVisible();

  const firstTile = page.getByTestId('tile-nilescrane');
  const dragHandle = page.getByTestId('drag-handle-nilescrane');
  const resizeHandle = page.getByTestId('resize-handle-nilescrane');

  const dragBox = await dragHandle.boundingBox();
  if (!dragBox) throw new Error('missing drag handle');
  await page.mouse.move(dragBox.x + dragBox.width / 2, dragBox.y + dragBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(dragBox.x + dragBox.width / 2, dragBox.y + dragBox.height / 2 + 80);
  await page.mouse.up();

  const before = await firstTile.evaluate((element) => element.clientHeight);
  const resizeBox = await resizeHandle.boundingBox();
  if (!resizeBox) throw new Error('missing resize handle');
  await page.mouse.move(resizeBox.x + resizeBox.width / 2, resizeBox.y + resizeBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(resizeBox.x + resizeBox.width / 2, resizeBox.y + resizeBox.height / 2 + 120);
  await page.mouse.up();

  await expect
    .poll(async () => firstTile.evaluate((element) => element.clientHeight))
    .toBeGreaterThan(before);
  await page.reload();
  await expect(page.getByTestId('offline-daphnemoon')).toBeVisible();
});

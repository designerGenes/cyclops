import type { CameraNode, Layout, LayoutTile } from '@cyclops/contracts';

export const LAYOUT_STORAGE_KEY = 'cyclops.layout.default';
export const MIN_TILE_HEIGHT = 180;
export const MAX_TILE_HEIGHT = 720;

export function clampTileHeight(heightPx: number): number {
  return Math.max(MIN_TILE_HEIGHT, Math.min(MAX_TILE_HEIGHT, Math.round(heightPx)));
}

export function generateDefaultLayout(cameras: CameraNode[]): Layout {
  return {
    layout_id: 'default',
    updated_at: new Date().toISOString(),
    tiles: cameras.map((camera, index) => ({
      camera_id: camera.id,
      order: index,
      height_px: 240,
      visible: true,
    })),
  };
}

export function reconcileLayout(layout: Layout | null | undefined, cameras: CameraNode[]): Layout {
  if (!layout) {
    return generateDefaultLayout(cameras);
  }

  const cameraIds = new Set(cameras.map((camera) => camera.id));
  const existingTiles: LayoutTile[] = layout.tiles.filter((tile: LayoutTile) => cameraIds.has(tile.camera_id));
  const existingIds = new Set(existingTiles.map((tile: LayoutTile) => tile.camera_id));
  const appended: LayoutTile[] = cameras
    .filter((camera) => !existingIds.has(camera.id))
    .map((camera) => ({
      camera_id: camera.id,
      order: 0,
      height_px: 240,
      visible: true,
    }));

  const tiles = [...existingTiles, ...appended]
    .sort((a, b) => a.order - b.order)
    .map((tile: LayoutTile, index: number) => ({
      ...tile,
      order: index,
      height_px: clampTileHeight(tile.height_px),
    }));

  return {
    layout_id: 'default',
    updated_at: new Date().toISOString(),
    tiles,
  };
}

export function moveTile(layout: Layout, fromIndex: number, toIndex: number): Layout {
  const tiles = [...layout.tiles];
  const [tile] = tiles.splice(fromIndex, 1);
  tiles.splice(toIndex, 0, tile);
  return {
    ...layout,
    updated_at: new Date().toISOString(),
    tiles: tiles.map((item, index) => ({ ...item, order: index })),
  };
}

export function resizeTile(layout: Layout, cameraId: string, heightPx: number): Layout {
  return {
    ...layout,
    updated_at: new Date().toISOString(),
    tiles: layout.tiles.map((tile: LayoutTile) =>
      tile.camera_id === cameraId ? { ...tile, height_px: clampTileHeight(heightPx) } : tile,
    ),
  };
}

export function mergeTilesWithCameras(cameras: CameraNode[], layout: Layout): Array<CameraNode & { tile: LayoutTile }> {
  const cameraMap = new Map(cameras.map((camera) => [camera.id, camera]));
  return layout.tiles
    .filter((tile: LayoutTile) => tile.visible)
    .map((tile: LayoutTile) => cameraMap.get(tile.camera_id) && { ...cameraMap.get(tile.camera_id)!, tile })
    .filter(Boolean) as Array<CameraNode & { tile: LayoutTile }>;
}

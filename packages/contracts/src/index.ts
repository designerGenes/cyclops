export type CameraStatus = 'unknown' | 'online' | 'offline' | 'degraded';
export type CameraProvider = 'mock' | 'picamera2';

export interface CameraCapabilities {
  provider: CameraProvider;
  stream_kind: 'mjpeg';
  supports_settings: boolean;
  supports_future_analytics_ingest: boolean;
}

export interface CameraNode {
  id: string;
  name: string;
  hostname: string | null;
  tailscale_ip: string | null;
  stream_url: string;
  settings_url: string;
  health_url: string;
  status: CameraStatus;
  last_seen_at: string | null;
  software_version: string | null;
  capabilities: CameraCapabilities;
}

export interface CameraSettings {
  rotation_degrees: 0 | 90 | 180 | 270;
  hflip: boolean;
  vflip: boolean;
  brightness: number;
  contrast: number;
  saturation: number;
  jpeg_quality: number;
  frame_rate: number;
  stream_width: number;
  stream_height: number;
}

export interface CameraHealth {
  camera_id: string;
  status: 'online' | 'offline' | 'degraded';
  provider: CameraProvider;
  camera_ready: boolean;
  stream_ready: boolean;
  last_frame_at: string | null;
  uptime_seconds: number;
  software_version: string;
}

export interface LayoutTile {
  camera_id: string;
  order: number;
  height_px: number;
  visible: boolean;
}

export interface Layout {
  layout_id: 'default';
  tiles: LayoutTile[];
  updated_at: string;
}

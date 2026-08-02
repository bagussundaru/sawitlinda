// Mirrors the JSON contract defined in CLAUDE.md. Keep in sync with
// backend/app/schemas.py — these two are the single source of truth.

export type Severity = "ringan" | "sedang" | "berat";

export interface Gps {
  lat: number;
  lng: number;
}

export interface Detection {
  id: number;
  /** [x, y, w, h] in image pixel coordinates */
  bbox: [number, number, number, number];
  disease: string;
  severity: Severity;
  confidence: number;
  gps: Gps | null;
}

export interface DetectionSummary {
  total: number;
  healthy: number;
  infected: number;
  severe: number;
}

export interface DetectionResult {
  image_id: string;
  filename: string;
  captured_at: string | null;
  gps: Gps | null;
  summary: DetectionSummary;
  detections: Detection[];
}

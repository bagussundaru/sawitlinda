// Mirrors the JSON contract defined in CLAUDE.md. Keep in sync with
// backend/app/schemas.py — these two are the single source of truth.

// "sehat" marks a detected tree with no condition — healthy trees are part of the
// detections array too, since the result screen and map draw every tree.
export type Severity = "sehat" | "ringan" | "sedang" | "berat";

export interface Gps {
  lat: number;
  lng: number;
}

export interface Detection {
  id: number;
  /** [x, y, w, h] in image pixel coordinates */
  bbox: [number, number, number, number];
  condition: string;
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
  block: string | null;
  area_ha: number | null;
  gps: Gps | null;
  summary: DetectionSummary;
  detections: Detection[];
}

export type ImageStatus = "uploaded" | "analyzed";

export interface ImageItem {
  image_id: string;
  filename: string;
  captured_at: string | null;
  block: string | null;
  area_ha: number | null;
  gps: Gps | null;
  status: ImageStatus;
  created_at: string;
}

/** History entry; `summary` is null while the image has not been analysed. */
export interface ResultListItem extends ImageItem {
  summary: DetectionSummary | null;
}

/** One detected tree with coordinates, for the spread map. */
export interface MapPoint {
  detection_id: number;
  image_id: string;
  filename: string;
  block: string | null;
  captured_at: string | null;
  condition: string;
  severity: Severity;
  confidence: number;
  gps: Gps;
}

/** Reference entry: how to read a condition and what to do about it. */
export interface ConditionInfo {
  key: string;
  label: string;
  appearance: string;
  interpretation: string;
  action: string;
}

/** One plantation block as described by the uploads. */
export interface BlockInfo {
  block: string | null;
  images: number;
  analyzed: number;
  trees: number;
  affected: number;
  area_ha: number | null;
}

export interface NamedCount {
  label: string;
  count: number;
}

export interface Dashboard {
  images_total: number;
  images_analyzed: number;
  summary: DetectionSummary;
  by_condition: NamedCount[];
  by_severity: NamedCount[];
}

/** What the backend actually runs right now. */
export interface SystemInfo {
  version: string;
  inference_mode: "mock" | "model";
  model_loaded: boolean;
  model_name: string | null;
  max_upload_mb: number;
  condition_count: number;
  severities: Severity[];
}

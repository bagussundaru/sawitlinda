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

/** Penilaian tingkat citra dari model vision — pendapat kedua di samping
 *  deteksi per pohon, bukan penggantinya. */
export interface AiAssessment {
  summary: string;
  recommendation: string;
  dominant_condition: string;
  confidence: number;
  affected_share: number;
  notes: string[];
  model: string;
  created_at: string;
  /** Selisih perkiraan model vision dengan hasil deteksi, dalam poin persen. */
  disagreement_pp: number | null;
}

export interface DetectionResult {
  image_id: string;
  filename: string;
  /** Nama yang diberikan pengunggah; identitas citra di seluruh aplikasi. */
  label: string | null;
  captured_at: string | null;
  gps: Gps | null;
  summary: DetectionSummary;
  detections: Detection[];
  ai: AiAssessment | null;
}

export type ImageStatus = "uploaded" | "analyzed";

export interface ImageItem {
  image_id: string;
  filename: string;
  label: string | null;
  captured_at: string | null;
  gps: Gps | null;
  status: ImageStatus;
  created_at: string;
  has_ai: boolean;
}

/** History entry; `summary` is null while the image has not been analysed. */
export interface ResultListItem extends ImageItem {
  summary: DetectionSummary | null;
}

/** Reference entry: how to read a condition and what to do about it. */
export interface ConditionInfo {
  key: string;
  label: string;
  appearance: string;
  interpretation: string;
  action: string;
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
  /** Set when the model file exists but the engine could not be loaded. */
  model_error: string | null;
  /** "rule" means severity is derived from a fixed rule, not predicted. */
  severity_source: "rule" | "model";
  /** Thresholds actually used at inference time, reported by the server so
   *  the methodology note on screen can never drift from the code. */
  confidence_threshold: number;
  nms_iou_threshold: number;
  tile_size: number;
  ai_enabled: boolean;
  ai_model: string | null;
  max_upload_mb: number;
  condition_count: number;
  severities: Severity[];
}

/** Metrik satu kelas kondisi pada evaluasi. */
export interface ClassMetrics {
  label: string;
  support: number;
  predicted: number;
  true_positive: number;
  false_positive: number;
  false_negative: number;
  precision: number;
  recall: number;
  f1: number;
  average_precision: number;
}

/** Hasil satu kali evaluasi terhadap anotasi ground truth. */
export interface Evaluation {
  id: string;
  created_at: string;
  source_filename: string;
  iou_threshold: number;
  /** "mock" berarti angka ini tidak mengukur model apa pun. */
  inference_mode: "mock" | "model";
  model_name: string | null;
  images: number;
  ground_truths: number;
  predictions: number;
  map50: number;
  micro_precision: number;
  micro_recall: number;
  micro_f1: number;
  per_class: ClassMetrics[];
  confusion: Record<string, Record<string, number>>;
}

/** Keadaan lapisan analisis AI. Kunci API tidak pernah ikut dikembalikan. */
export interface AiSettings {
  configured: boolean;
  source: "aplikasi" | "environment" | null;
  /** Empat karakter terakhir kunci, sekadar penanda. */
  key_hint: string | null;
  model: string;
}

// --- Autentikasi ---
export interface AuthUser {
  username: string;
  full_name: string | null;
}

export interface AuthState {
  authenticated: boolean;
  /** False berarti belum ada akun sama sekali di server. */
  ready: boolean;
  user: AuthUser | null;
}

// --- Training ---
export interface TrainingConfig {
  configured: boolean;
  base_models: string[];
  max_epochs: number;
  max_dataset_mb: number;
  active_model: string | null;
}

export interface TrainingRun {
  id: string;
  job_id: string;
  run_name: string;
  base_model: string;
  epochs: number;
  dataset_filename: string | null;
  status: "queued" | "running" | "done" | "failed";
  started_by: string | null;
  created_at: string;
  finished_at: string | null;
  final_map50: number | null;
  final_map50_95: number | null;
  last_epoch: number | null;
  error: string | null;
  is_active: boolean;
}

/** Satu epoch. Nilai bisa null: metrik validasi tidak selalu ada tiap epoch. */
export interface TrainingPoint {
  epoch: number;
  box_loss: number | null;
  cls_loss: number | null;
  dfl_loss: number | null;
  map50: number | null;
  map50_95: number | null;
  precision?: number | null;
  recall?: number | null;
}

export interface TrainingStatus {
  job_id: string;
  status: "queued" | "running" | "done" | "failed";
  epoch: number | null;
  total_epochs: number | null;
  history: TrainingPoint[];
  latest: TrainingPoint | null;
  error: string | null;
  run_name: string | null;
  is_active: boolean;
}

/** Kolom yang boleh dipakai mengurutkan riwayat. Harus sama dengan
 *  SORT_COLUMNS di backend. */
export type ResultSort =
  | "created_at"
  | "label"
  | "captured_at"
  | "trees"
  | "affected";

/** Satu halaman riwayat. `total` mengikuti penyaringan yang sedang aktif. */
export interface ResultPage {
  items: ResultListItem[];
  total: number;
  limit: number;
  offset: number;
}

// --- Spatial ---

/** One of the five sample villages in Kotawaringin Timur. */
export interface VillageInfo {
  key: string;
  name: string;
  district: string;
  /** Approximate area centre — used only to position the map view. */
  lat: number;
  lng: number;
  images: number;
  analyzed: number;
  trees: number;
  affected: number;
}

/** One image on the map. Markers are per image, not per tree. */
export interface MapImagePoint {
  image_id: string;
  filename: string;
  label: string | null;
  village: string | null;
  captured_at: string | null;
  gps: Gps;
  summary: DetectionSummary;
  dominant_condition: string | null;
  /** Share of trees that are not healthy, 0..1 — drives marker colour. */
  affected_share: number;
}

/** An analysed image that carries no coordinates, so it cannot be mapped. */
export interface MapImageWithoutGps {
  image_id: string;
  filename: string;
  label: string | null;
  village: string | null;
  captured_at: string | null;
  summary: DetectionSummary;
}

/** Contents of the map screen: what can be placed, and what cannot. */
export interface MapData {
  points: MapImagePoint[];
  without_gps: MapImageWithoutGps[];
  analyzed_total: number;
}

// --- Background jobs ---

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface JobProgress {
  current: number;
  total: number;
  message: string;
}

export interface Job {
  id: string;
  kind: "roboflow_evaluate" | "reanalyse";
  status: JobStatus;
  progress: JobProgress;
  result: Record<string, unknown> | null;
  error: string | null;
  created_by: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RoboflowSettings {
  configured: boolean;
  key_hint: string | null;
}

/** Catatan eksperimen. Sekali hasilnya dilampirkan, tidak ada yang mengubahnya. */
export interface Experiment {
  id: string;
  experiment_id: string;
  kind: "validation" | "test";
  /** Kosong sampai checkpoint terbaik dipilih. */
  model_id: string | null;
  model_name: string | null;
  dataset_name: string;
  dataset_test_hash: string;
  dataset_val_hash: string | null;
  hypothesis: string | null;
  training_config: Record<string, unknown>;
  git_commit: string | null;
  status: ExperimentStatus;
  metrics: Record<string, unknown> | null;
  results_at: string | null;
  created_by: string | null;
  created_at: string;
}

export type ExperimentStatus =
  | "draft"
  | "locked"
  | "training"
  | "ready_for_final_test"
  | "final_tested";

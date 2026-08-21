// All REST calls live here. Components never call fetch() directly.

import type {
  AiSettings,
  AuthState,
  AuthUser,
  TrainingConfig,
  TrainingRun,
  TrainingStatus,
  Evaluation,
  ConditionInfo,
  Dashboard,
  DetectionResult,
  ImageItem,
  ResultPage,
  ResultSort,
  SystemInfo,
  Job,
  MapData,
  Experiment,
  ExperimentStatus,
  RoboflowSettings,
  VillageInfo,
} from "@/types/detection";

export const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      cache: "no-store",
      // Cookie sesi harus ikut terkirim. Tanpa ini setiap permintaan dijawab
      // 401 walaupun pengguna sudah masuk — fetch() tidak mengirim cookie
      // lintas asal secara bawaan, dan dev menjalankan frontend & backend di
      // port yang berbeda.
      credentials: "include",
      ...init,
    });
  } catch {
    throw new ApiError(
      "Could not reach the server. Check that the backend is running.",
      0,
    );
  }
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // Fall through to the generic message below.
  }
  return `Request failed (${response.status}).`;
}

/** Unggah satu kiriman citra beserta labelnya.
 *
 * `labels` harus sejajar dengan `files`. Nilai kosong dibiarkan terkirim supaya
 * urutannya tidak bergeser — server yang memutuskan memakai nama berkas. */
export function uploadImages(
  files: File[],
  labels: string[] = [],
  village?: string | null,
): Promise<{ images: ImageItem[] }> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  files.forEach((file, i) => form.append("labels", labels[i] ?? ""));
  if (village) form.append("village", village);
  return apiFetch("/api/upload", { method: "POST", body: form });
}

/** Batas ukuran satu kiriman. Reverse proxy membatasi badan permintaan, dan
 *  100 bingkai UAV berukuran sekitar 400 MB — jauh di atas batas itu. */
const BATAS_KIRIMAN_MB = 30;

/** Batas jumlah berkas per kiriman, untuk citra yang kecil-kecil. Tanpa ini,
 *  seribu ubin dataset masuk dalam satu permintaan yang sangat panjang. */
const BATAS_BERKAS_PER_KIRIMAN = 12;

/** Bagi berkas menjadi kiriman yang muat di batas proxy. */
export function batchFiles<T extends { file: File }>(items: T[]): T[][] {
  const kiriman: T[][] = [];
  let sekarang: T[] = [];
  let ukuran = 0;

  for (const item of items) {
    const besar = item.file.size;
    const penuh =
      sekarang.length >= BATAS_BERKAS_PER_KIRIMAN ||
      (sekarang.length > 0 && ukuran + besar > BATAS_KIRIMAN_MB * 1024 * 1024);
    if (penuh) {
      kiriman.push(sekarang);
      sekarang = [];
      ukuran = 0;
    }
    sekarang.push(item);
    ukuran += besar;
  }
  if (sekarang.length) kiriman.push(sekarang);
  return kiriman;
}

export interface UploadProgress {
  /** Berkas yang sudah berhasil diunggah. */
  done: number;
  total: number;
}

/** Unggah banyak citra dengan memecahnya menjadi beberapa kiriman.
 *
 * Mengirim 100 bingkai dalam satu permintaan berarti satu gangguan jaringan
 * membatalkan seluruhnya, tanpa cara mengetahui sejauh mana ia sempat sampai.
 * Dipecah begini, kegagalan hanya mengenai kiriman terakhir dan yang sudah
 * masuk tetap terpakai.
 */
export async function uploadImagesInBatches(
  items: { file: File; label: string }[],
  onProgress?: (p: UploadProgress) => void,
  village?: string | null,
): Promise<{ images: ImageItem[]; failedFrom: number | null; error?: string }> {
  const kiriman = batchFiles(items);
  const images: ImageItem[] = [];
  let selesai = 0;

  for (const kelompok of kiriman) {
    try {
      const hasil = await uploadImages(
        kelompok.map((x) => x.file),
        kelompok.map((x) => x.label),
        village,
      );
      images.push(...hasil.images);
      selesai += kelompok.length;
      onProgress?.({ done: selesai, total: items.length });
    } catch (err) {
      // Yang sudah masuk dikembalikan apa adanya, beserta titik gagalnya —
      // pemanggil dapat menganalisis yang berhasil dan mencoba ulang sisanya.
      return {
        images,
        failedFrom: selesai,
        error: err instanceof ApiError ? err.message : "Upload interrupted.",
      };
    }
  }

  return { images, failedFrom: null };
}

export function analyzeImage(imageId: string): Promise<DetectionResult> {
  return apiFetch(`/api/analyze/${imageId}`, { method: "POST" });
}

/** Minta penilaian model vision untuk satu citra. Lambat (beberapa detik) dan
 *  bisa gagal — karena itu terpisah dari analyze. */
export function runAiReview(imageId: string): Promise<DetectionResult> {
  return apiFetch(`/api/analyze/${imageId}/ai`, { method: "POST" });
}

export function getResult(imageId: string): Promise<DetectionResult> {
  return apiFetch(`/api/results/${imageId}`);
}

export interface ResultQuery {
  /** Cari pada label atau nama berkas. */
  q?: string;
  status?: "uploaded" | "analyzed";
  sort?: ResultSort;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export function listResults(params: ResultQuery = {}): Promise<ResultPage> {
  const cari = new URLSearchParams();
  for (const [kunci, nilai] of Object.entries(params)) {
    if (nilai !== undefined && nilai !== null && `${nilai}` !== "") {
      cari.set(kunci, String(nilai));
    }
  }
  const sisipan = cari.toString();
  return apiFetch(`/api/results${sisipan ? `?${sisipan}` : ""}`);
}

/** `search` menyaring berdasarkan label yang diberikan pengunggah. */
export function getDashboard(search?: string | null): Promise<Dashboard> {
  const q = search?.trim() ? `?q=${encodeURIComponent(search.trim())}` : "";
  return apiFetch(`/api/dashboard${q}`);
}

export function listConditions(): Promise<ConditionInfo[]> {
  return apiFetch("/api/conditions");
}

export function getSystemInfo(): Promise<SystemInfo> {
  return apiFetch("/api/system");
}

export function runEvaluation(
  file: File,
  iouThreshold = 0.5,
): Promise<Evaluation> {
  const form = new FormData();
  form.append("file", file);
  form.append("iou_threshold", String(iouThreshold));
  return apiFetch("/api/evaluate", { method: "POST", body: form });
}

export function listEvaluations(): Promise<Evaluation[]> {
  return apiFetch("/api/evaluations");
}

export function getAiSettings(): Promise<AiSettings> {
  return apiFetch("/api/settings/ai");
}

export function saveAiKey(apiKey: string, model?: string): Promise<AiSettings> {
  return apiFetch("/api/settings/ai", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, model: model?.trim() || null }),
  });
}

export function saveAiModel(model: string): Promise<AiSettings> {
  return apiFetch("/api/settings/ai/model", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
}

export function clearAiKey(): Promise<AiSettings> {
  return apiFetch("/api/settings/ai", { method: "DELETE" });
}

export function imageFileUrl(imageId: string): string {
  return `${BASE_URL}/api/images/${imageId}/file`;
}

export function exportUrl(imageId: string, format: "pdf" | "csv"): string {
  return `${BASE_URL}/api/results/${imageId}/export.${format}`;
}

// --- Autentikasi -----------------------------------------------------------

/** Status sesi. Tidak melempar saat 401 — "belum masuk" adalah jawaban yang
 *  sah, bukan kegagalan. */
export async function getAuthState(): Promise<AuthState> {
  try {
    return await apiFetch<AuthState>("/api/auth/state");
  } catch {
    return { authenticated: false, ready: true, user: null };
  }
}

export function login(username: string, password: string): Promise<AuthUser> {
  return apiFetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await fetch(`${BASE_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// --- Training --------------------------------------------------------------

export function getTrainingConfig(): Promise<TrainingConfig> {
  return apiFetch("/api/train/config");
}

export function listTrainingRuns(): Promise<TrainingRun[]> {
  return apiFetch("/api/train/runs");
}

export function startTraining(
  dataset: File,
  epochs: number,
  baseModel: string,
  runName: string,
): Promise<TrainingRun> {
  const form = new FormData();
  form.append("dataset", dataset);
  form.append("epochs", String(epochs));
  form.append("base_model", baseModel);
  if (runName.trim()) form.append("run_name", runName.trim());
  return apiFetch("/api/train", { method: "POST", body: form });
}

export function getTrainingStatus(jobId: string): Promise<TrainingStatus> {
  return apiFetch(`/api/train/${jobId}/status`);
}

export function activateModel(jobId: string): Promise<TrainingRun> {
  return apiFetch(`/api/train/${jobId}/activate`, { method: "POST" });
}

// --- Spatial ---------------------------------------------------------------

export function listVillages(): Promise<VillageInfo[]> {
  return apiFetch("/api/villages");
}

export function getMapData(village?: string | null): Promise<MapData> {
  const q = village ? `?village=${encodeURIComponent(village)}` : "";
  return apiFetch(`/api/map${q}`);
}

// --- Background jobs -------------------------------------------------------

export function listJobs(): Promise<Job[]> {
  return apiFetch("/api/jobs");
}

export function getJob(jobId: string): Promise<Job> {
  return apiFetch(`/api/jobs/${jobId}`);
}

export function startRoboflowEvaluation(params: {
  workspace: string;
  project: string;
  version: number;
  split?: string;
  iou_threshold?: number;
}): Promise<Job> {
  return apiFetch("/api/jobs/roboflow-evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export function startReanalysis(): Promise<Job> {
  return apiFetch("/api/jobs/reanalyse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

// --- Roboflow key ----------------------------------------------------------

export function getRoboflowSettings(): Promise<RoboflowSettings> {
  return apiFetch("/api/settings/roboflow");
}

export function saveRoboflowKey(apiKey: string): Promise<RoboflowSettings> {
  return apiFetch("/api/settings/roboflow", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export function clearRoboflowKey(): Promise<RoboflowSettings> {
  return apiFetch("/api/settings/roboflow", { method: "DELETE" });
}

// --- Catatan eksperimen ---------------------------------------------------
// Tidak ada fungsi menghapus, menyunting hasil, atau memundurkan status:
// yang tidak ada di sini memang sengaja tidak ada.

export function listExperiments(): Promise<Experiment[]> {
  return apiFetch<Experiment[]>("/api/experiments");
}

export function createExperiment(body: Record<string, unknown>): Promise<Experiment> {
  return apiFetch<Experiment>("/api/experiments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Hanya berlaku selagi statusnya masih `draft`. */
export function editExperimentDraft(
  experimentId: string,
  body: Record<string, unknown>,
): Promise<Experiment> {
  return apiFetch<Experiment>(`/api/experiments/${encodeURIComponent(experimentId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Majukan status. Server menolak arah mundur.
 *
 * `checkpoint` hanya diterima saat maju ke `ready_for_final_test`, dan hanya
 * sekali — sesudah itu bobot yang diuji tidak dapat ditukar. */
export function advanceExperiment(
  experimentId: string,
  status: ExperimentStatus,
  checkpoint?: { model_id: string; model_name?: string },
): Promise<Experiment> {
  return apiFetch<Experiment>(
    `/api/experiments/${encodeURIComponent(experimentId)}/status`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, ...checkpoint }),
    },
  );
}

/** Hanya dapat dipanggil sekali per eksperimen. */
export function attachExperimentResults(
  experimentId: string,
  metrics: Record<string, unknown>,
): Promise<Experiment> {
  return apiFetch<Experiment>(
    `/api/experiments/${encodeURIComponent(experimentId)}/results`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ metrics }),
    },
  );
}

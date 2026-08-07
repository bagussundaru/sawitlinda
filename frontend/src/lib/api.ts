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
  ResultListItem,
  SystemInfo,
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
      "Tidak dapat menghubungi server. Pastikan backend berjalan.",
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
  return `Permintaan gagal (${response.status}).`;
}

/** Unggah citra beserta labelnya.
 *
 * `labels` harus sejajar dengan `files`. Nilai kosong dibiarkan terkirim supaya
 * urutannya tidak bergeser — server yang memutuskan memakai nama berkas. */
export function uploadImages(
  files: File[],
  labels: string[] = [],
): Promise<{ images: ImageItem[] }> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  files.forEach((file, i) => form.append("labels", labels[i] ?? ""));
  return apiFetch("/api/upload", { method: "POST", body: form });
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

export function listResults(): Promise<ResultListItem[]> {
  return apiFetch("/api/results");
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

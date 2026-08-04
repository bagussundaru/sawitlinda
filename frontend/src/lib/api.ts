// All REST calls live here. Components never call fetch() directly.

import type {
  BlockInfo,
  ConditionInfo,
  Dashboard,
  DetectionResult,
  ImageItem,
  MapPoint,
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
    response = await fetch(`${BASE_URL}${path}`, { cache: "no-store", ...init });
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

export interface UploadFields {
  /** Plantation block, e.g. "A-3". */
  block?: string;
  /** Area the frames cover, in hectares. */
  areaHa?: string;
  /** Only used when the frame carries no EXIF GPS. */
  lat?: string;
  lng?: string;
}

export function uploadImages(
  files: File[],
  fields: UploadFields = {},
): Promise<{ images: ImageItem[] }> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  if (fields.block?.trim()) form.append("block", fields.block.trim());
  if (fields.areaHa?.trim()) form.append("area_ha", fields.areaHa.trim());
  if (fields.lat?.trim() && fields.lng?.trim()) {
    form.append("lat", fields.lat.trim());
    form.append("lng", fields.lng.trim());
  }
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

export function getDashboard(block?: string | null): Promise<Dashboard> {
  const query = block ? `?block=${encodeURIComponent(block)}` : "";
  return apiFetch(`/api/dashboard${query}`);
}

export function listBlocks(): Promise<BlockInfo[]> {
  return apiFetch("/api/blocks");
}

export function listConditions(): Promise<ConditionInfo[]> {
  return apiFetch("/api/conditions");
}

export function listMapPoints(block?: string | null): Promise<MapPoint[]> {
  const query = block ? `?block=${encodeURIComponent(block)}` : "";
  return apiFetch(`/api/map${query}`);
}

export function getSystemInfo(): Promise<SystemInfo> {
  return apiFetch("/api/system");
}

export function imageFileUrl(imageId: string): string {
  return `${BASE_URL}/api/images/${imageId}/file`;
}

export function exportUrl(imageId: string, format: "pdf" | "csv"): string {
  return `${BASE_URL}/api/results/${imageId}/export.${format}`;
}

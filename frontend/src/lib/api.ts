// All REST calls live here. Components never call fetch() directly.

import type {
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

export function uploadImages(files: File[]): Promise<{ images: ImageItem[] }> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return apiFetch("/api/upload", { method: "POST", body: form });
}

export function analyzeImage(imageId: string): Promise<DetectionResult> {
  return apiFetch(`/api/analyze/${imageId}`, { method: "POST" });
}

export function getResult(imageId: string): Promise<DetectionResult> {
  return apiFetch(`/api/results/${imageId}`);
}

export function listResults(): Promise<ResultListItem[]> {
  return apiFetch("/api/results");
}

export function getDashboard(): Promise<Dashboard> {
  return apiFetch("/api/dashboard");
}

export function listConditions(): Promise<ConditionInfo[]> {
  return apiFetch("/api/conditions");
}

export function listMapPoints(): Promise<MapPoint[]> {
  return apiFetch("/api/map");
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

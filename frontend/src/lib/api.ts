// All REST calls live here. Components never call fetch() directly.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new ApiError(`Permintaan gagal: ${response.statusText}`, response.status);
  }
  return (await response.json()) as T;
}

export function health(): Promise<{ status: string; version: string }> {
  return apiFetch("/health");
}

// Stage 2+: uploadImage, analyzeImage, getResult, listResults, getDashboard.

export const API_BASE =
  process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export interface ApiHealth {
  status: string;
}

export async function fetchHealth(signal?: AbortSignal): Promise<ApiHealth> {
  const response = await fetch(`${API_BASE}/api/v1/health`, { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return (await response.json()) as ApiHealth;
}

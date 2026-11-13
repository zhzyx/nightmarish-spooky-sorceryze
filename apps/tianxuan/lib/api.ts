export const API_BASE =
  process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export interface ApiHealth {
  status: string;
}

export interface ApiDoc {
  id: string;
  title: string;
  kind: string;
  version: number;
  status: string;
}

export async function fetchHealth(signal?: AbortSignal): Promise<ApiHealth> {
  const response = await fetch(`${API_BASE}/api/v1/health`, { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return (await response.json()) as ApiHealth;
}

export interface ApiDocDetail extends ApiDoc {
  body_md: string;
}

export async function fetchDocs(actor: string): Promise<ApiDoc[]> {
  const response = await fetch(`${API_BASE}/api/v1/docs`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`docs request failed: ${response.status}`);
  }
  const body = (await response.json()) as { docs?: ApiDoc[] };
  return body.docs ?? [];
}

export async function fetchDoc(id: string, actor: string): Promise<ApiDocDetail> {
  const response = await fetch(`${API_BASE}/api/v1/docs/${encodeURIComponent(id)}`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`doc request failed: ${response.status}`);
  }
  return (await response.json()) as ApiDocDetail;
}

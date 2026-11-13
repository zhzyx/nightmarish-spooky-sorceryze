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

export class MergeConflict extends Error {
  conflicts: string[];

  constructor(conflicts: string[]) {
    super("merge conflict");
    this.conflicts = conflicts;
  }
}

export interface ApiMergeResult {
  status: "applied" | "merged";
  doc: ApiDocDetail;
  remote_version?: number;
}

export async function mergeDoc(
  id: string,
  actor: string,
  base_md: string,
  local_md: string,
  expected_version: number,
): Promise<ApiMergeResult> {
  const response = await fetch(`${API_BASE}/api/v1/docs/${encodeURIComponent(id)}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify({ base_md, local_md, expected_version }),
  });
  if (response.status === 409) {
    const body = (await response.json()) as { conflicts?: string[] };
    throw new MergeConflict(body.conflicts ?? []);
  }
  if (!response.ok) {
    throw new Error(`merge failed: ${response.status}`);
  }
  return (await response.json()) as ApiMergeResult;
}

export interface ApiRepo {
  name: string;
  full_name: string;
  private: boolean;
  default_branch: string;
}

export async function fetchRepos(actor: string): Promise<ApiRepo[]> {
  const response = await fetch(`${API_BASE}/api/v1/repos`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`repos request failed: ${response.status}`);
  }
  const body = (await response.json()) as { repos?: ApiRepo[] };
  return body.repos ?? [];
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

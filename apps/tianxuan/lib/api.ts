function apiBase(): string {
  return typeof window === "undefined" ? API_BASE : "";
}

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
  const response = await fetch(`${apiBase()}/api/v1/health`, { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return (await response.json()) as ApiHealth;
}

export interface ApiDocDetail extends ApiDoc {
  body_md: string;
  visibility?: DocVisibility;
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
  const response = await fetch(`${apiBase()}/api/v1/docs/${encodeURIComponent(id)}/merge`, {
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
  const response = await fetch(`${apiBase()}/api/v1/repos`, {
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
  const response = await fetch(`${apiBase()}/api/v1/docs`, {
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
  const response = await fetch(`${apiBase()}/api/v1/docs/${encodeURIComponent(id)}`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`doc request failed: ${response.status}`);
  }
  return (await response.json()) as ApiDocDetail;
}

export type DocVisibility = "tenant" | "private";

export type SharePermission = "read" | "write";

export interface ApiShare {
  user_id: string;
  permission: SharePermission;
  created_at: string;
}

export async function fetchShares(id: string, actor: string): Promise<ApiShare[]> {
  const response = await fetch(`${apiBase()}/api/v1/docs/${encodeURIComponent(id)}/shares`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`shares request failed: ${response.status}`);
  }
  const body = (await response.json()) as { shares?: ApiShare[] };
  return body.shares ?? [];
}

export async function setDocVisibility(
  id: string,
  actor: string,
  visibility: DocVisibility,
): Promise<ApiDocDetail> {
  const response = await fetch(`${apiBase()}/api/v1/docs/${encodeURIComponent(id)}/visibility`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify({ visibility }),
  });
  if (!response.ok) {
    throw new Error(`visibility update failed: ${response.status}`);
  }
  return (await response.json()) as ApiDocDetail;
}

export async function shareDoc(
  id: string,
  actor: string,
  userId: string,
  permission: SharePermission,
): Promise<void> {
  const response = await fetch(`${apiBase()}/api/v1/docs/${encodeURIComponent(id)}/shares`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify({ user_id: userId, permission }),
  });
  if (!response.ok) {
    throw new Error(`share request failed: ${response.status}`);
  }
}

export async function unshareDoc(id: string, actor: string, userId: string): Promise<void> {
  const response = await fetch(
    `${apiBase()}/api/v1/docs/${encodeURIComponent(id)}/shares/${encodeURIComponent(userId)}`,
    {
      method: "DELETE",
      headers: { "X-Actor": actor },
    },
  );
  if (!response.ok) {
    throw new Error(`unshare request failed: ${response.status}`);
  }
}

export interface ApiGiteaStatus {
  configured: boolean;
  owner: string;
}

export async function fetchGiteaStatus(): Promise<ApiGiteaStatus> {
  const response = await fetch(`${apiBase()}/api/v1/gitea/status`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`gitea status failed: ${response.status}`);
  }
  return (await response.json()) as ApiGiteaStatus;
}

export interface ApiIssue {
  id: string;
  title: string;
  status: string;
  type: string;
  priority: string;
  number: number;
  requirement_id?: string | null;
}

export async function fetchIssues(actor: string, status?: string): Promise<ApiIssue[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await fetch(`${apiBase()}/api/v1/issues${query}`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`issues request failed: ${response.status}`);
  }
  const body = (await response.json()) as { issues?: ApiIssue[] };
  return body.issues ?? [];
}

export async function fetchBoard(actor: string): Promise<Record<string, ApiIssue[]>> {
  const response = await fetch(`${apiBase()}/api/v1/board`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`board request failed: ${response.status}`);
  }
  const body = (await response.json()) as { columns?: Record<string, ApiIssue[]> };
  return body.columns ?? {};
}

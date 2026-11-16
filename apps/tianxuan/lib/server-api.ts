import "server-only";
import { cookies } from "next/headers";
import { cache } from "react";
import type { ApiDoc, ApiDocDetail, ApiRepo, ApiIssue, ApiHealth, ApiGiteaStatus } from "./api";
import type { ApiRequirement } from "./requirements-api";
import type { ApiSearchResult } from "./search-api";
export type { ApiDoc, ApiDocDetail, ApiRepo, ApiIssue, ApiHealth, ApiGiteaStatus, ApiRequirement, ApiSearchResult };
export type { ApiRequirementProgress } from "./requirements-api";
export interface Identity { id: string; name: string; email: string; role: string }

async function read<T>(path: string): Promise<T> {
  const base = process.env.TIANXUAN_INTERNAL_API_BASE ?? process.env.NEXT_PUBLIC_TIANXUAN_API_BASE ?? "http://127.0.0.1:8000";
  const key = cookies().get("__Host-tianxuan_key")?.value;
  const headers: Record<string, string> = key ? { Authorization: `Bearer ${key}` } : {};
  if (!key && process.env.TIANXUAN_REQUIRE_KEYS !== "1" && process.env.TIANXUAN_ACTOR) headers["X-Actor"] = process.env.TIANXUAN_ACTOR;
  const response = await fetch(`${base.replace(/\/$/, "")}${path}`, { headers, cache: "no-store" });
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export const currentIdentity = cache(async (): Promise<Identity | null> => {
  try { return await read<Identity>("/api/v1/auth/me"); } catch {
    if (process.env.TIANXUAN_REQUIRE_KEYS !== "1" && process.env.TIANXUAN_ACTOR) {
      try {
        const members = await read<{users: Identity[]}>("/api/v1/users");
        return members.users.find(user => user.id === process.env.TIANXUAN_ACTOR) ?? null;
      } catch { return null; }
    }
    return null;
  }
});
export async function currentActor(): Promise<string> {
  return (await currentIdentity())?.id ?? (process.env.TIANXUAN_REQUIRE_KEYS === "1" ? "" : process.env.TIANXUAN_ACTOR ?? "");
}
export async function fetchHealth(): Promise<ApiHealth> { return read("/api/v1/health"); }
export async function fetchGiteaStatus(): Promise<ApiGiteaStatus> { return read("/api/v1/gitea/status"); }
export async function fetchDocs(_actor: string): Promise<ApiDoc[]> { return (await read<{docs: ApiDoc[]}>("/api/v1/docs")).docs; }
export async function fetchDoc(id: string, _actor: string): Promise<ApiDocDetail> { return read(`/api/v1/docs/${encodeURIComponent(id)}`); }
export async function fetchRepos(_actor: string): Promise<ApiRepo[]> { return (await read<{repos: ApiRepo[]}>("/api/v1/repos")).repos; }
export async function fetchIssues(_actor: string): Promise<ApiIssue[]> { return (await read<{issues: ApiIssue[]}>("/api/v1/issues")).issues; }
export async function fetchBoard(_actor: string): Promise<Record<string, ApiIssue[]>> { return (await read<{columns: Record<string, ApiIssue[]>}>("/api/v1/board")).columns; }
export async function fetchRequirements(_actor: string): Promise<ApiRequirement[]> { return (await read<{docs: ApiRequirement[]}>("/api/v1/docs?kind=requirement")).docs; }
export async function fetchRequirementProgress(_actor: string, id: string): Promise<ApiRequirement> { return read(`/api/v1/docs/${encodeURIComponent(id)}`); }
export async function fetchSearch(_actor: string, q: string, limit=20): Promise<ApiSearchResult[]> { return (await read<{results: ApiSearchResult[]}>(`/api/v1/search?${new URLSearchParams({q,limit:String(limit)})}`)).results; }

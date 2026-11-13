/**
 * 文曲检索 API 客户端。
 *
 * 与 lib/api.ts 分开，避免实时搜索接入时改动既有的文档 / 工单接口。
 */

const API_BASE =
  process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

function apiBase(): string {
  return typeof window === "undefined" ? API_BASE : "";
}

/**
 * GET /api/v1/search 的单条结果。
 *
 * 当前后端返回 id、score 与 snippet；title / kind 为可选兼容字段，
 * 页面渲染时需自行回退。
 */
export interface ApiSearchResult {
  id: string;
  title?: string;
  kind?: string;
  snippet?: string;
  score?: number;
}

export async function fetchSearch(
  actor: string,
  q: string,
  limit = 20,
): Promise<ApiSearchResult[]> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  const response = await fetch(`${apiBase()}/api/v1/search?${params.toString()}`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`search request failed: ${response.status}`);
  }
  const body = (await response.json()) as { results?: ApiSearchResult[] };
  return body.results ?? [];
}

/**
 * 多宝本地 Git 仓库浏览 API 客户端。
 *
 * 与 lib/api.ts 分开，避免本地裸仓库浏览改动既有的文档 / 工单 / Gitea 接口。
 * 浏览器端使用同源 `/api`（由 next.config.mjs 转发到后端），服务端渲染时
 * 直接访问 `NEXT_PUBLIC_TIANXUAN_API_BASE` 或默认的本地 FastAPI 地址。
 */

const API_BASE =
  process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

function apiBase(): string {
  return typeof window === "undefined" ? API_BASE : "";
}

/** `GET /api/v1/git/repos` 返回的单个本地仓库名，例如 `docs.git`。 */
export type ApiLocalRepo = string;

/**
 * `GET /api/v1/git/repos/{name}/log` 返回的单条提交。
 *
 * 字段与 `customizations/components/tianxuan/duobao/git_service.py` 的
 * `GitService.log()` 保持一致：`date` 为 ISO-8601 时间，`message` 为提交标题。
 */
export interface ApiCommit {
  sha: string;
  author: string;
  email?: string;
  date: string;
  message: string;
}

/** 列出 `TIANXUAN_REPO_ROOT` 下的本地裸仓库。 */
export async function fetchLocalRepos(actor: string): Promise<ApiLocalRepo[]> {
  const response = await fetch(`${apiBase()}/api/v1/git/repos`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`local repos request failed: ${response.status}`);
  }
  const body = (await response.json()) as { repos?: ApiLocalRepo[] };
  return body.repos ?? [];
}

/** 读取一个本地仓库的分支名；没有分支时返回空数组。 */
export async function fetchLocalBranches(actor: string, name: string): Promise<string[]> {
  const response = await fetch(
    `${apiBase()}/api/v1/git/repos/${encodeURIComponent(name)}/branches`,
    {
      headers: { "X-Actor": actor },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw new Error(`local branches request failed: ${response.status}`);
  }
  const body = (await response.json()) as { branches?: string[] };
  return body.branches ?? [];
}

/** 读取指定 ref 的最近提交，默认最多 10 条。 */
export async function fetchLocalLog(
  actor: string,
  name: string,
  ref: string,
  limit = 10,
): Promise<ApiCommit[]> {
  const query = `ref=${encodeURIComponent(ref)}&limit=${encodeURIComponent(String(limit))}`;
  const response = await fetch(
    `${apiBase()}/api/v1/git/repos/${encodeURIComponent(name)}/log?${query}`,
    {
      headers: { "X-Actor": actor },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw new Error(`local log request failed: ${response.status}`);
  }
  const body = (await response.json()) as { commits?: ApiCommit[] };
  return body.commits ?? [];
}

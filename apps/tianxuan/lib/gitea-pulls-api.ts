/**
 * 多宝 Gitea Pull Request API 客户端。
 *
 * 与 lib/api.ts、lib/local-git-api.ts 分开，避免 Pull Request 管理改动既有的
 * 文档 / 工单 / 本地仓库接口。浏览器端使用同源 `/api`（由 next.config.mjs
 * 转发到后端），服务端渲染时直接访问 `NEXT_PUBLIC_TIANXUAN_API_BASE` 或默认
 * 的本地 FastAPI 地址。
 */

const API_BASE =
  process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

function apiBase(): string {
  return typeof window === "undefined" ? API_BASE : "";
}

/** Pull Request 列表状态；后端透传给 Gitea。 */
export type PullState = "open" | "closed" | "all";

/** 合并方式，对应 Gitea 合并接口的 `Do` 字段。 */
export type MergeMethod = "merge" | "squash" | "rebase";

/** `GET /api/v1/repos/{owner}/{name}/branches` 返回的单个分支。 */
export interface ApiBranch {
  name: string;
  protected: boolean;
  commit_sha: string;
}

/**
 * `GET /api/v1/repos/{owner}/{name}/pulls` 返回的单个 Pull Request。
 *
 * 后端已把 Gitea 的 `head` / `base` 对象归一化为分支名。
 */
export interface ApiPull {
  number: number;
  title: string;
  state: string;
  html_url: string;
  head: string;
  base: string;
}

/** 创建 Pull Request 的请求体。 */
export interface CreatePullPayload {
  title: string;
  head: string;
  base: string;
  body?: string;
}

/** `POST /api/v1/repos/{owner}/{name}/pulls/{number}/merge` 的合并结果。 */
export interface ApiMergeResult {
  merged: boolean;
  sha: string | null;
}

function repoPath(owner: string, repo: string): string {
  return `/api/v1/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;
}

async function readJson<T>(response: Response, label: string): Promise<T> {
  if (!response.ok) {
    throw new Error(`${label} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

/** 读取仓库分支。 */
export async function fetchBranches(
  actor: string,
  owner: string,
  repo: string,
): Promise<ApiBranch[]> {
  const response = await fetch(`${apiBase()}${repoPath(owner, repo)}/branches`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  const body = await readJson<{ branches?: ApiBranch[] }>(response, "branches request");
  return body.branches ?? [];
}

/** 读取指定状态的 Pull Request。 */
export async function fetchPulls(
  actor: string,
  owner: string,
  repo: string,
  state: PullState,
): Promise<ApiPull[]> {
  const query = `?state=${encodeURIComponent(state)}`;
  const response = await fetch(`${apiBase()}${repoPath(owner, repo)}/pulls${query}`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  const body = await readJson<{ pulls?: ApiPull[] }>(response, "pulls request");
  return body.pulls ?? [];
}

/** 创建同仓库内 `head` -> `base` 的 Pull Request。 */
export async function createPull(
  actor: string,
  owner: string,
  repo: string,
  payload: CreatePullPayload,
): Promise<ApiPull> {
  const response = await fetch(`${apiBase()}${repoPath(owner, repo)}/pulls`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify({
      title: payload.title,
      head: payload.head,
      base: payload.base,
      body: payload.body ?? "",
    }),
    cache: "no-store",
  });
  return readJson<ApiPull>(response, "create pull request");
}

/** 以 `method` 合并指定 Pull Request。 */
export async function mergePull(
  actor: string,
  owner: string,
  repo: string,
  number: number,
  method: MergeMethod,
): Promise<ApiMergeResult> {
  const response = await fetch(
    `${apiBase()}${repoPath(owner, repo)}/pulls/${encodeURIComponent(String(number))}/merge`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Actor": actor },
      body: JSON.stringify({ method }),
      cache: "no-store",
    },
  );
  return readJson<ApiMergeResult>(response, "merge pull request");
}

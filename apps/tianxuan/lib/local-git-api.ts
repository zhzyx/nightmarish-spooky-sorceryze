import { authHeaders } from "@/lib/auth";

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
    headers: authHeaders(actor),
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
      headers: authHeaders(actor),
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
      headers: authHeaders(actor),
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw new Error(`local log request failed: ${response.status}`);
  }
  const body = (await response.json()) as { commits?: ApiCommit[] };
  return body.commits ?? [];
}

/** 文件树中的单个条目（对应 `GitService.list_tree`）。 */
export interface ApiTreeEntry {
  name: string;
  path: string;
  type: string;
  mode: string;
  sha: string;
  size: number | null;
}

/** 标签名与目标提交。 */
export interface ApiTag {
  name: string;
  sha: string;
}

async function jsonRequest<T>(
  actor: string,
  path: string,
  init?: { method?: string; body?: unknown },
): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    method: init?.method ?? "GET",
    headers: {
      ...authHeaders(actor),
      ...(init?.body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `local git request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

/** 读取目录树；`path` 为空表示仓库根。 */
export async function fetchLocalTree(
  actor: string,
  name: string,
  ref: string,
  path = "",
): Promise<ApiTreeEntry[]> {
  const query = `ref=${encodeURIComponent(ref)}${path ? `&path=${encodeURIComponent(path)}` : ""}`;
  const body = await jsonRequest<{ entries?: ApiTreeEntry[] }>(
    actor,
    `/api/v1/git/repos/${encodeURIComponent(name)}/tree?${query}`,
  );
  return body.entries ?? [];
}

/** 列出仓库标签。 */
export async function fetchLocalTags(actor: string, name: string): Promise<ApiTag[]> {
  const body = await jsonRequest<{ tags?: ApiTag[] }>(
    actor,
    `/api/v1/git/repos/${encodeURIComponent(name)}/tags`,
  );
  return body.tags ?? [];
}

/** 基于已有提交创建分支。 */
export async function createLocalBranch(
  actor: string,
  name: string,
  branch: string,
  start = "HEAD",
): Promise<{ branch: string; sha: string }> {
  return jsonRequest<{ branch: string; sha: string }>(
    actor,
    `/api/v1/git/repos/${encodeURIComponent(name)}/branches`,
    { method: "POST", body: { name: branch, start } },
  );
}

/** 删除分支（受保护分支需要 admin）。 */
export async function deleteLocalBranch(
  actor: string,
  name: string,
  branch: string,
): Promise<{ branch: string; deleted: boolean }> {
  return jsonRequest<{ branch: string; deleted: boolean }>(
    actor,
    `/api/v1/git/repos/${encodeURIComponent(name)}/branches/${encodeURIComponent(branch)}`,
    { method: "DELETE" },
  );
}

/** 导入结果（对应 `GitService.import_repo`）。 */
export interface ApiImportResult {
  path: string;
  name: string;
  source: string;
  default_branch: string;
  head: string | null;
  branches: string[];
  tags: ApiTag[];
  mirror: boolean;
}

/** 以镜像方式导入远端/本机仓库（仅 admin）。 */
export async function importLocalRepo(
  actor: string,
  name: string,
  source: string,
): Promise<ApiImportResult> {
  return jsonRequest<ApiImportResult>(actor, "/api/v1/git/import", {
    method: "POST",
    body: { name, source },
  });
}

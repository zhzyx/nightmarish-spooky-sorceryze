/**
 * 偃师需求 API 客户端。
 *
 * 与 lib/api.ts 分开，避免实时需求接入时改动既有的文档 / 工单接口。
 */

const API_BASE =
  process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

function apiBase(): string {
  return typeof window === "undefined" ? API_BASE : "";
}

/** 需求列表 `GET /api/v1/docs?kind=requirement` 的单条记录。 */
export interface ApiRequirement {
  id: string;
  title: string;
  kind: string;
  status: string;
  tags?: string[];
  version: number;
  updated_at?: string;
  /** 详情接口才返回：来源请求 ID。 */
  request_id?: string | null;
  /** 详情接口才返回：工单进度。 */
  progress?: ApiRequirementProgress | null;
}

/** 需求详情中的工单进度，`percent` 为 0–100 的百分比。 */
export interface ApiRequirementProgress {
  total: number;
  done: number;
  percent: number;
}

/** 列出全部需求文档。 */
export async function fetchRequirements(actor: string): Promise<ApiRequirement[]> {
  const response = await fetch(`${apiBase()}/api/v1/docs?kind=requirement`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`requirements request failed: ${response.status}`);
  }
  const body = (await response.json()) as { docs?: ApiRequirement[] };
  return body.docs ?? [];
}

/**
 * 读取单个需求详情，返回其中的 `progress` 与 `request_id`。
 *
 * 列表接口不携带进度，页面需为每条需求单独回读详情。
 */
export async function fetchRequirementProgress(
  actor: string,
  id: string,
): Promise<ApiRequirement> {
  const response = await fetch(`${apiBase()}/api/v1/docs/${encodeURIComponent(id)}`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`requirement detail request failed: ${response.status}`);
  }
  return (await response.json()) as ApiRequirement;
}

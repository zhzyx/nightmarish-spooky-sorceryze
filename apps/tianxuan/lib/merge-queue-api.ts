function apiBase(): string {
  return typeof window === "undefined"
    ? (process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000")
    : "";
}

export interface ApiMergeQueueItem {
  id: string;
  repo: string;
  source: string;
  target: string;
  title: string;
  priority: number;
  status: string;
  attempts: number;
  evidence: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface MergeQueueInput {
  repo: string;
  source: string;
  target: string;
  title?: string;
  priority?: number;
}

export async function fetchMergeQueue(actor: string): Promise<ApiMergeQueueItem[]> {
  const response = await fetch(`${apiBase()}/api/v1/merge-queue?limit=100`, {
    headers: { "X-Actor": actor },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`merge queue request failed: ${response.status}`);
  }
  const body = (await response.json()) as { items?: ApiMergeQueueItem[] };
  return body.items ?? [];
}

export async function enqueueMerge(actor: string, input: MergeQueueInput): Promise<ApiMergeQueueItem> {
  const response = await fetch(`${apiBase()}/api/v1/merge-queue`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify({
      repo: input.repo,
      source: input.source,
      target: input.target,
      title: input.title ?? "",
      priority: input.priority ?? 0,
    }),
  });
  if (!response.ok) {
    throw new Error(`merge enqueue failed: ${response.status}`);
  }
  return (await response.json()) as ApiMergeQueueItem;
}

export async function processMergeQueue(actor: string, limit = 5): Promise<ApiMergeQueueItem[]> {
  const response = await fetch(`${apiBase()}/api/v1/merge-queue/process?limit=${limit}`, {
    method: "POST",
    headers: { "X-Actor": actor },
  });
  if (!response.ok) {
    throw new Error(`merge process failed: ${response.status}`);
  }
  const body = (await response.json()) as { processed?: ApiMergeQueueItem[] };
  return body.processed ?? [];
}

export async function cancelMerge(actor: string, itemId: string): Promise<ApiMergeQueueItem> {
  const response = await fetch(
    `${apiBase()}/api/v1/merge-queue/${encodeURIComponent(itemId)}/cancel`,
    { method: "POST", headers: { "X-Actor": actor } },
  );
  if (!response.ok) {
    throw new Error(`merge cancel failed: ${response.status}`);
  }
  return (await response.json()) as ApiMergeQueueItem;
}

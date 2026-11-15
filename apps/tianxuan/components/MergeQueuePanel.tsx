"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getToken } from "@/lib/auth";
import {
  cancelMerge,
  enqueueMerge,
  fetchMergeQueue,
  fetchMergeQueueStatus,
  processMergeQueue,
  retryMerge,
  type ApiMergeQueueItem,
  type ApiMergeQueueStatus,
} from "@/lib/merge-queue-api";

const fieldStyle: CSSProperties = {
  background: "rgba(245, 242, 234, 0.06)",
  border: "1px solid rgba(245, 242, 234, 0.14)",
  borderRadius: 8,
  color: "inherit",
  font: "inherit",
  fontSize: 12,
  minWidth: 0,
  padding: "9px 10px",
};

const STATUS_LABEL: Record<string, string> = {
  queued: "排队中",
  validating: "检验中",
  merged: "已合入",
  conflict: "冲突",
  rejected: "已拒绝",
  cancelled: "已取消",
};

function evidenceText(item: ApiMergeQueueItem): string {
  const evidence = item.evidence ?? {};
  const error = evidence["error"];
  if (typeof error === "string" && error) {
    return error;
  }
  const sha = evidence["merge_sha"];
  if (typeof sha === "string" && sha) {
    return `merge ${sha.slice(0, 10)}`;
  }
  return "";
}

export function MergeQueuePanel() {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR;
  const [items, setItems] = useState<ApiMergeQueueItem[]>([]);
  const [status, setStatus] = useState<ApiMergeQueueStatus | null>(null);
  const [repo, setRepo] = useState("docs.git");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("main");
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("0");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [live, setLive] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const load = useCallback(async () => {
    if (!actor) {
      return;
    }
    const [nextItems, nextStatus] = await Promise.all([
      fetchMergeQueue(actor),
      fetchMergeQueueStatus(actor),
    ]);
    setItems(nextItems);
    setStatus(nextStatus);
  }, [actor]);

  useEffect(() => {
    if (!actor) {
      return;
    }
    let active = true;
    let poll: number | null = null;
    load().catch(() => undefined);
    const startPolling = () => {
      if (poll !== null) {
        return;
      }
      poll = window.setInterval(() => {
        load()
          .then(() => active && setError(""))
          .catch((cause: unknown) => active && setError(cause instanceof Error ? cause.message : "加载失败"));
      }, 5000);
    };
    const base =
      process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
    const token = getToken();
    const query = token ? `token=${encodeURIComponent(token)}` : `actor=${encodeURIComponent(actor)}`;
    const socket = new WebSocket(
      `${base.replace(/^http/, "ws")}/api/v1/ws/merge-queue?${query}`,
    );
    socket.onopen = () => {
      if (active) {
        setLive(true);
      }
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as { type?: string; items?: ApiMergeQueueItem[] };
        if (message.type === "snapshot") {
          setItems(message.items ?? []);
        }
      } catch {
        // 忽略非 JSON 消息
      }
    };
    socket.onerror = () => socket.close();
    socket.onclose = () => {
      if (!active) {
        return;
      }
      setLive(false);
      startPolling();
    };
    return () => {
      active = false;
      socket.close();
      if (poll !== null) {
        window.clearInterval(poll);
      }
    };
  }, [actor, load]);

  async function enqueue() {
    if (!actor || !repo.trim() || !source.trim() || !target.trim()) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await enqueueMerge(actor, {
        repo: repo.trim(),
        source: source.trim(),
        target: target.trim(),
        title: title.trim(),
        priority: Number(priority) || 0,
      });
      setSource("");
      setTitle("");
      await load();
      setNotice("已入队；worker 会自动处理");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "入队失败");
    } finally {
      setBusy(false);
    }
  }

  async function processNow() {
    if (!actor) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const processed = await processMergeQueue(actor, 5);
      await load();
      setNotice(`已处理 ${processed.length} 个候选`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "处理失败");
    } finally {
      setBusy(false);
    }
  }

  async function retry(item: ApiMergeQueueItem) {
    if (!actor) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await retryMerge(actor, item.id);
      await load();
      setNotice("已重新入队");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "重试失败");
    } finally {
      setBusy(false);
    }
  }

  async function cancel(item: ApiMergeQueueItem) {
    if (!actor) {
      return;
    }
    setBusy(true);
    try {
      await cancelMerge(actor, item.id);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "取消失败");
    } finally {
      setBusy(false);
    }
  }

  const visible = statusFilter === "all" ? items : items.filter((item) => item.status === statusFilter);

  return (
    <section className="panel" aria-labelledby="merge-queue-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker">DUOBAO · MERGE TRAIN</p>
          <h2 id="merge-queue-title">合入队列</h2>
        </div>
        <span className="section-note">
          <select
            aria-label="按状态筛选"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            style={{ ...fieldStyle, padding: "4px 8px", marginRight: 10 }}
          >
            <option value="all">全部状态</option>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {status?.worker ? "自动 worker" : "手动模式"} · {status?.queued ?? 0} 排队 · {visible.length} 个候选 ·{" "}
          {live ? "实时" : "轮询"}
          <button className="btn btn-ghost" type="button" disabled={busy} onClick={processNow} style={{ marginLeft: 10 }}>
            立即处理
          </button>
        </span>
      </div>
      {!actor ? (
        <p className="section-note" style={{ padding: "0 26px 22px" }}>
          未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，无法操作合入队列。
        </p>
      ) : (
        <>
          <div className="reading-list live-list">
            {visible.length === 0 ? (
              <p className="section-note" style={{ padding: "12px 16px" }}>
                队列为空。入队后由 worker 自动预检、检验并合入。
              </p>
            ) : (
              visible.map((item) => (
                <div className="reading-item" key={item.id}>
                  <span className="reading-index">{item.status.slice(0, 1).toUpperCase()}</span>
                  <span className="reading-copy">
                    <strong>
                      {item.title || `${item.source} → ${item.target}`}
                    </strong>
                    <span>
                      {item.repo} · {item.source} → {item.target} · 尝试 {item.attempts} ·{" "}
                      {STATUS_LABEL[item.status] ?? item.status}
                      {evidenceText(item) ? ` · ${evidenceText(item)}` : ""}
                    </span>
                  </span>
                  {item.status === "queued" ? (
                    <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => cancel(item)}>
                      取消
                    </button>
                  ) : ["rejected", "conflict", "cancelled"].includes(item.status) ? (
                    <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => retry(item)}>
                      重试
                    </button>
                  ) : null}
                </div>
              ))
            )}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) 80px auto",
              gap: "10px",
              alignItems: "center",
              padding: "0 26px 22px",
            }}
          >
            <input aria-label="仓库" style={fieldStyle} placeholder="docs.git" value={repo} onChange={(event) => setRepo(event.target.value)} />
            <input aria-label="源分支" style={fieldStyle} placeholder="feature" value={source} onChange={(event) => setSource(event.target.value)} />
            <input aria-label="目标分支" style={fieldStyle} placeholder="main" value={target} onChange={(event) => setTarget(event.target.value)} />
            <input aria-label="标题" style={fieldStyle} placeholder="合入标题（可选）" value={title} onChange={(event) => setTitle(event.target.value)} />
            <input aria-label="优先级" style={fieldStyle} placeholder="0" value={priority} onChange={(event) => setPriority(event.target.value)} />
            <button className="btn btn-primary" type="button" disabled={busy || !source.trim()} onClick={enqueue}>
              {busy ? "处理中…" : "入队"}
            </button>
          </div>
        </>
      )}
      {notice ? <p className="section-note" style={{ padding: "0 26px 16px" }}>{notice}</p> : null}
      {error ? <p className="section-note" style={{ padding: "0 26px 16px" }}>{error}</p> : null}
    </section>
  );
}

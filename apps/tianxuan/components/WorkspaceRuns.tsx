"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n-client";

type Run = {
  id: string;
  requirement_id: string;
  title: string;
  state: string;
  tasks: { id: string; issue_id: string; title: string; state: string }[];
  tasks_truncated: boolean;
};

type RunPage = { available: boolean; runs: Run[]; next_cursor: string | null };

const states: Record<string, [string, string]> = {
  pending: ["等待规划", "Awaiting plan"],
  planned: ["已规划", "Planned"],
  ready: ["等待执行", "Ready"],
  reserved: ["已分配", "Reserved"],
  running: ["运行中", "Running"],
  held: ["待核对", "Needs reconciliation"],
  produced: ["已产出", "Produced"],
  failed: ["执行失败", "Failed"],
  delivered: ["已交付", "Delivered"],
  accepted: ["已验收", "Accepted"],
  stopped: ["已停止", "Stopped"],
  superseded: ["已替代", "Superseded"],
  "closed-unresolved": ["关闭待解", "Closed unresolved"],
};

export function workspaceRunStatus(value: string, zh: boolean) {
  return states[value]?.[zh ? 0 : 1] ?? value;
}

export function workspaceEntryStatus(value: string, zh: boolean) {
  return value === "delivered" ? (zh ? "已派发" : "Dispatched") : workspaceRunStatus(value, zh);
}

export function WorkspaceRuns({ signedIn }: { signedIn: boolean }) {
  const { locale } = useI18n();
  const zh = locale === "zh";
  const [page, setPage] = useState<RunPage | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const [request, setRequest] = useState({ after: "", refresh: 0 });

  useEffect(() => {
    if (!signedIn) return;
    const controller = new AbortController();
    const url = "/api/v1/workspace/runs" +
      (request.after ? `/after/${encodeURIComponent(request.after)}` : "");
    setPending(true);
    setError(false);
    fetch(url, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("runs unavailable");
        const result: RunPage = await response.json();
        if (!controller.signal.aborted) {
          setPage((previous) => request.after && previous
            ? { ...result, runs: [...previous.runs, ...result.runs] } : result);
        }
      })
      .catch(() => { if (!controller.signal.aborted) setError(true); })
      .finally(() => { if (!controller.signal.aborted) setPending(false); });
    return () => controller.abort();
  }, [request, signedIn]);

  useEffect(() => {
    if (!signedIn) return;
    function update() {
      setRequest((previous) => ({ after: "", refresh: previous.refresh + 1 }));
    }
    window.addEventListener("tianxuan:execution-updated", update);
    return () => window.removeEventListener("tianxuan:execution-updated", update);
  }, [signedIn]);

  function load(after = "") {
    if (!after) setPage(null);
    setPending(true);
    setRequest((previous) => ({ after, refresh: previous.refresh + 1 }));
  }

  return (
    <section className="workspace-card workspace-lane" aria-labelledby="workspace-runs-title">
      <div className="workspace-chat-header">
        <h2 id="workspace-runs-title">{zh ? "执行任务" : "Execution runs"}</h2>
        {signedIn && <button className="workspace-refresh" type="button" disabled={pending} onClick={() => load()}>
          {zh ? "刷新" : "Refresh"}
        </button>}
      </div>
      {!signedIn ? <Link className="text-link" href="/login">{zh ? "登录后查看" : "Sign in to view"}</Link>
        : pending && !page ? <p role="status">{zh ? "读取执行记录…" : "Loading execution runs…"}</p>
        : page?.available === false ? <p>{zh ? "尚未配置执行服务。" : "Execution service is not configured."}</p>
        : page?.available && page.runs.length === 0 ? <p>{zh ? "暂无执行记录。" : "No execution runs."}</p>
        : null}
      {signedIn && error && <p role="alert">{zh ? "无法读取执行记录。" : "Execution runs could not be loaded."}</p>}
      {signedIn && page?.available && page.runs.length > 0 && <ul className="workspace-items">
        {page.runs.map((run) => (
          <li className="workspace-item" key={run.id}>
            <details>
              <summary><span>{run.title}</span><small>{workspaceEntryStatus(run.state, zh)}</small></summary>
              <div className="workspace-item-details">
                <Link className="text-link" href={`/docs/${encodeURIComponent(run.requirement_id)}`}>
                  {zh ? "查看需求" : "Open requirement"}
                </Link>
              </div>
              {run.tasks.length > 0 && <ul className="workspace-items">
                {run.tasks.map((task) => <li className="workspace-item-details" key={task.id}>
                  <Link className="text-link" href={`/issues/${encodeURIComponent(task.issue_id)}`}>
                    {task.title}
                  </Link>
                  <span>{workspaceRunStatus(task.state, zh)}</span>
                </li>)}
              </ul>}
              {run.tasks_truncated && <p>{zh ? "仅展示前 12 个可见执行工单。" : "Showing the first 12 visible execution work orders."}</p>}
            </details>
          </li>
        ))}
      </ul>}
      {signedIn && page?.next_cursor && <button className="workspace-refresh" type="button" disabled={pending}
        onClick={() => load(page.next_cursor ?? "")}>{zh ? "加载更多" : "Load more"}</button>}
    </section>
  );
}

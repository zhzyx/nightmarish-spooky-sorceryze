"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { AICommandBar } from "@/components/AICommandBar";
import { Icon } from "@/components/Icon";
import { WorkspaceRuns } from "@/components/WorkspaceRuns";
import { useI18n } from "@/lib/i18n-client";
import "./workspace.css";
import type { ApiIssue } from "@/lib/api";

const running = new Set(["in-progress", "progress"]);
const pending = new Set(["backlog", "planned", "blocked", "in-review", "review"]);
const priority: Record<string, number> = { p0: 0, urgent: 0, p1: 1, high: 1, p2: 2, normal: 2, p3: 3, low: 3 };
const statusLabels: Record<string, [string, string]> = {
  backlog: ["待安排", "Backlog"], planned: ["已计划", "Planned"], blocked: ["受阻", "Blocked"],
  "in-progress": ["进行中", "In progress"], progress: ["进行中", "In progress"],
  "in-review": ["待审查", "In review"], review: ["待审查", "In review"],
};

export function DashboardWorkspace({ issues, signedIn }: { issues: ApiIssue[] | null; signedIn: boolean }) {
  const { locale, t } = useI18n();
  const zh = locale === "zh";
  const router = useRouter();
  const [refreshing, refresh] = useTransition();
  const [lane, setLane] = useState<"pending" | "running">("pending");
  const ordered = [...(issues ?? [])].sort((a, b) =>
    (priority[a.priority.toLowerCase()] ?? 4) - (priority[b.priority.toLowerCase()] ?? 4) || b.number - a.number);
  const groups = {
    pending: { title: zh ? "待办" : "To do", items: ordered.filter((issue) => pending.has(issue.status)) },
    running: { title: zh ? "进行中工单" : "Work in progress", items: ordered.filter((issue) => running.has(issue.status)) },
  };
  const { items } = groups[lane];

  return (
    <div className="workspace-home">
      <header className="workspace-intro">
        <h1>{zh ? "天璇工作台" : "Tianxuan Workspace"}</h1>
        <Link className="workspace-board-link" href="/issues">
          <Icon name="grid" size={16} />{t("home.openBoard")}
        </Link>
      </header>
      <div className="workspace-columns">
        <AICommandBar />
        <div className="workspace-activity">
          <section className="workspace-card workspace-lane" aria-labelledby="workspace-orders-title">
            <div className="workspace-chat-header">
              <h2 id="workspace-orders-title">{zh ? "工单" : "Work orders"}</h2>
              {signedIn && <button type="button" className="workspace-refresh" disabled={refreshing}
                onClick={() => refresh(() => router.refresh())}>
                {refreshing ? (zh ? "刷新中…" : "Refreshing…") : (zh ? "刷新工单" : "Refresh work orders")}
              </button>}
            </div>
            {signedIn && <fieldset className="workspace-switcher">
              <legend className="sr-only">{zh ? "工单状态" : "Work order status"}</legend>
              {(["pending", "running"] as const).map((id) => (
                <label key={id}>
                  <input className="sr-only" type="radio" name="issue-lane" checked={lane === id}
                    onChange={() => setLane(id)} />
                  <span>{groups[id].title}{issues && <small>{groups[id].items.length}</small>}</span>
                </label>
              ))}
            </fieldset>}
            {!signedIn ? <Link className="text-link" href="/login">{zh ? "登录后查看" : "Sign in to view"}</Link>
              : !issues ? <p role="status">{zh ? "工单暂时无法读取。" : "Work orders are temporarily unavailable."}</p>
              : items.length === 0 ? <p>{zh ? "暂无工单。" : "No work orders."}</p>
              : <ul className="workspace-items">
                  {items.slice(0, 5).map((issue) => (
                    <li key={issue.id}>
                      <details className="workspace-item">
                        <summary>
                          <span>{issue.title}</span>
                          <small>{statusLabels[issue.status][zh ? 0 : 1]}</small>
                        </summary>
                        <div className="workspace-item-details">
                          <span>#{issue.number}</span>
                          <span>{issue.priority}</span>
                          <Link className="text-link" href={`/issues/${encodeURIComponent(issue.id)}`}>
                            {zh ? "查看工单" : "Open work order"}
                          </Link>
                          {issue.requirement_id && <Link className="text-link" href={`/docs/${encodeURIComponent(issue.requirement_id)}`}>
                            {zh ? "查看关联需求" : "Open linked requirement"}
                          </Link>}
                        </div>
                      </details>
                    </li>
                  ))}
                </ul>}
          </section>
          <WorkspaceRuns signedIn={signedIn} />
        </div>
      </div>
    </div>
  );
}

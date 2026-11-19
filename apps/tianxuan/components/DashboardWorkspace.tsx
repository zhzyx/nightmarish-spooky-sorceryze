"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { AICommandBar } from "@/components/AICommandBar";
import { Icon } from "@/components/Icon";
import { WorkspaceRuns } from "@/components/WorkspaceRuns";
import { useI18n } from "@/lib/i18n-client";
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
  const ordered = [...(issues ?? [])].sort((a, b) =>
    (priority[a.priority.toLowerCase()] ?? 4) - (priority[b.priority.toLowerCase()] ?? 4) || b.number - a.number);
  const groups = [
    { id: "pending", title: zh ? "待办" : "To do", items: ordered.filter((issue) => pending.has(issue.status)) },
    { id: "running", title: zh ? "进行中工单" : "Work in progress", items: ordered.filter((issue) => running.has(issue.status)) },
  ];

  return (
    <div className="workspace-home">
      <header className="workspace-intro">
        <h1>{zh ? "天璇工作台" : "Tianxuan Workspace"}</h1>
      </header>
      <div className="workspace-columns">
        <AICommandBar />
        <div className="workspace-activity">
          <div className="workspace-board-bar">
            <Link className="text-link" href="/issues">
              {t("home.openBoard")} <Icon name="arrowRight" size={14} />
            </Link>
            {signedIn && (
              <button type="button" className="workspace-refresh" disabled={refreshing}
                onClick={() => refresh(() => router.refresh())}>
                {refreshing ? (zh ? "刷新中…" : "Refreshing…") : (zh ? "刷新工单" : "Refresh work orders")}
              </button>
            )}
          </div>
          <div className="workspace-board">
            {groups.map(({ id, title, items }) => (
              <section className="workspace-card workspace-lane" key={id} aria-labelledby={`workspace-${id}`}>
                <h2 id={`workspace-${id}`}>{title}</h2>
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
            ))}
          </div>
          <WorkspaceRuns signedIn={signedIn} />
        </div>
      </div>
    </div>
  );
}

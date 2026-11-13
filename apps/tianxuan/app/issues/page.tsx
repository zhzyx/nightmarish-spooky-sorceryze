import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { IssueBoard } from "@/components/IssueBoard";
import { fetchBoard, fetchIssues, type ApiIssue } from "@/lib/api";
import { issues } from "@/lib/data";

export const metadata: Metadata = {
  title: "工单",
};

export const dynamic = "force-dynamic";

const liveColumns: {
  id: string;
  label: string;
  hint: string;
  statuses: readonly string[];
  toneClass?: string;
}[] = [
  { id: "backlog", label: "待梳理", hint: "进入迭代前", statuses: ["backlog"], toneClass: "status-backlog" },
  { id: "planned", label: "已规划", hint: "等待开始", statuses: ["planned"] },
  {
    id: "in-progress",
    label: "进行中",
    hint: "正在推进",
    statuses: ["in-progress", "progress", "blocked"],
    toneClass: "status-progress",
  },
  {
    id: "review",
    label: "评审中",
    hint: "等待判断",
    statuses: ["in-review", "review"],
    toneClass: "status-review",
  },
  { id: "done", label: "已完成", hint: "本周闭环", statuses: ["done"], toneClass: "status-done" },
  { id: "cancelled", label: "已取消", hint: "终止推进", statuses: ["cancelled"] },
];

const typeLabels: Record<string, string> = {
  requirement: "需求",
  task: "任务",
  bug: "缺陷",
  design: "设计",
  chore: "杂务",
};

const priorityLabels: Record<string, string> = {
  p0: "P0",
  p1: "P1",
  p2: "P2",
  urgent: "紧急",
  high: "高",
  normal: "普通",
  low: "低",
};

function typeLabel(type: string): string {
  return typeLabels[type] ?? type;
}

function priorityLabel(priority: string): string {
  return priorityLabels[priority.toLowerCase()] ?? priority;
}

function priorityClass(priority: string): string {
  const value = priority.toLowerCase();
  return value === "p0" || value === "p1" || value === "p2" ? ` priority-${value}` : "";
}

function collectColumnIssues(
  board: Record<string, ApiIssue[]>,
  allIssues: ApiIssue[],
  statuses: readonly string[],
): ApiIssue[] {
  const seen = new Set<string>();
  const collected: ApiIssue[] = [];
  for (const status of statuses) {
    for (const issue of board[status] ?? []) {
      if (!seen.has(issue.id)) {
        seen.add(issue.id);
        collected.push(issue);
      }
    }
  }
  // 看板可能漏掉某个状态，使用完整工单列表补齐，避免卡片丢失。
  for (const issue of allIssues) {
    if (statuses.includes(issue.status) && !seen.has(issue.id)) {
      seen.add(issue.id);
      collected.push(issue);
    }
  }
  return collected;
}

export default async function IssuesPage() {
  const done = issues.filter((issue) => issue.status === "done").length;
  const blocked = issues.filter((issue) => issue.blocked).length;
  const completion = Math.round((done / issues.length) * 100);

  const actor = process.env.TIANXUAN_ACTOR ?? "";
  let live: { board: Record<string, ApiIssue[]>; issues: ApiIssue[] } | null = null;
  if (actor) {
    try {
      const [board, liveIssues] = await Promise.all([fetchBoard(actor), fetchIssues(actor)]);
      live = { board, issues: liveIssues };
    } catch {
      live = null;
    }
  }

  const liveCounts = live
    ? liveColumns.map((column) => ({
        label: column.label,
        count: live.issues.filter((issue) => column.statuses.includes(issue.status)).length,
      }))
    : [];

  return (
    <div className="page-stack issues-page">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            SINAN · WORK ORDERS
          </p>
          <h1>
            工单<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            事件推进工作，而不是提醒推动人。看板保留每一步判断，列表保留每一个可以回读的编号。
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/docs/sinan-events">
            <Icon name="branch" size={16} />
            推进规则
          </Link>
          <Link className="btn btn-primary" href="/requirements">
            <Icon name="sparkles" size={16} />
            让偃师拆单
          </Link>
        </div>
      </header>

      {live ? (
        <section className="panel" aria-labelledby="live-issues-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">SINAN · LIVE BOARD</p>
              <h2 id="live-issues-title">实时工单</h2>
            </div>
            <span className="section-note">{live.issues.length} 个工单来自后端</span>
          </div>

          <div className="board-caption" style={{ padding: "0 26px 16px", flexWrap: "wrap" }}>
            <span>
              <span className="live-dot" aria-hidden="true" />
              实时数据 · 共 {live.issues.length} 个工单
            </span>
            <span>
              {liveCounts.map((item) => `${item.label} ${item.count}`).join(" · ")}
            </span>
          </div>

          {live.issues.length === 0 ? (
            <p className="section-note" style={{ padding: "0 26px 22px" }}>
              后端暂无工单，下面仍展示示例看板。
            </p>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
                gap: "11px",
                alignItems: "start",
                padding: "0 24px 24px",
              }}
            >
              {liveColumns.map((column) => {
                const cards = collectColumnIssues(live.board, live.issues, column.statuses);
                if (cards.length === 0) {
                  return null;
                }
                return (
                  <section
                    aria-labelledby={`live-column-${column.id}`}
                    className="kanban-column"
                    key={column.id}
                  >
                    <header className={`kanban-head${column.toneClass ? ` ${column.toneClass}` : ""}`}>
                      <div className="kanban-head-title">
                        <span className="status-dot" aria-hidden="true" />
                        <h2 id={`live-column-${column.id}`}>{column.label}</h2>
                        <span className="column-count">{cards.length}</span>
                      </div>
                      <span className="column-hint">{column.hint}</span>
                    </header>
                    <div className="kanban-cards">
                      {cards.map((issue) => (
                        <article className="issue-card" key={issue.id} style={{ cursor: "default" }}>
                          <span className="issue-card-top">
                            <span className="mono-key">#{issue.number}</span>
                            <span className={`priority${priorityClass(issue.priority)}`}>
                              {priorityLabel(issue.priority)}
                            </span>
                          </span>
                          <span className="issue-card-title">{issue.title}</span>
                          <span className="issue-tags">
                            <span className="kind-tag">{typeLabel(issue.type)}</span>
                            {issue.status === "blocked" ? (
                              <span
                                className="kind-tag"
                                style={{
                                  borderColor: "rgba(200, 64, 47, 0.3)",
                                  background: "rgba(200, 64, 47, 0.08)",
                                  color: "#CF8175",
                                }}
                              >
                                阻塞
                              </span>
                            ) : null}
                          </span>
                        </article>
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </section>
      ) : null}

      <section className="sprint-banner" aria-label="当前迭代">
        <div className="sprint-main">
          <p className="section-kicker">SPRINT 07 · 冬日切片</p>
          <h2>让文档与工单说同一种语言</h2>
          <span className="sprint-meta">
            <Icon name="clock" size={14} />
            11 月 11 日 — 11 月 20 日 · 还剩 6 天
          </span>
        </div>
        <div className="sprint-progress">
          <div className="sprint-stat">
            <strong>{completion}%</strong>
            <span>整体完成</span>
          </div>
          <div className="meter meter-lg" aria-hidden="true">
            <span style={{ width: `${completion}%` }} />
          </div>
          <small>
            {done} / {issues.length} 已完成
            {blocked > 0 ? ` · ${blocked} 个阻塞` : ""}
          </small>
        </div>
        <div className="sprint-people">
          <div className="avatar-stack">
            <span className="avatar avatar-sm avatar-jade">文</span>
            <span className="avatar avatar-sm avatar-gold">偃</span>
            <span className="avatar avatar-sm avatar-cinnabar">司</span>
            <span className="avatar avatar-sm avatar-mist">S</span>
          </div>
          <span>5 位协作者</span>
        </div>
      </section>

      <IssueBoard initialIssues={issues} />
    </div>
  );
}

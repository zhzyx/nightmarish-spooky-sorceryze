import { currentActor } from "@/lib/server-api";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { IssueBoard } from "@/components/IssueBoard";
import { issues as sampleIssues } from "@/lib/data";
import { Icon } from "@/components/Icon";
import { fetchBoard, fetchIssues, type ApiIssue } from "@/lib/server-api";
import { LOCALE_COOKIE, formatMessage, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "issues.title") };
}

export const dynamic = "force-dynamic";

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
    for (const issue of Object.hasOwn(board, status) ? board[status] : []) {
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
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);

  const liveColumns: {
    id: string;
    label: string;
    hint: string;
    statuses: readonly string[];
    toneClass?: string;
  }[] = [
    {
      id: "backlog",
      label: t("issues.colBacklog"),
      hint: t("issues.colBacklogHint"),
      statuses: ["backlog"],
      toneClass: "status-backlog",
    },
    {
      id: "planned",
      label: t("issues.colPlanned"),
      hint: t("issues.colPlannedHint"),
      statuses: ["planned"],
    },
    {
      id: "in-progress",
      label: t("issues.colProgress"),
      hint: t("issues.colProgressHint"),
      statuses: ["in-progress", "progress", "blocked"],
      toneClass: "status-progress",
    },
    {
      id: "review",
      label: t("issues.colReview"),
      hint: t("issues.colReviewHint"),
      statuses: ["in-review", "review"],
      toneClass: "status-review",
    },
    {
      id: "done",
      label: t("issues.colDone"),
      hint: t("issues.colDoneHint"),
      statuses: ["done"],
      toneClass: "status-done",
    },
    {
      id: "cancelled",
      label: t("issues.colCancelled"),
      hint: t("issues.colCancelledHint"),
      statuses: ["cancelled"],
    },
  ];

  const typeLabels: Record<string, string> = {
    requirement: t("issues.typeRequirement"),
    task: t("issues.typeTask"),
    bug: t("issues.typeBug"),
    design: t("issues.typeDesign"),
    chore: t("issues.typeChore"),
  };

  const priorityLabels: Record<string, string> = {
    p0: "P0",
    p1: "P1",
    p2: "P2",
    urgent: t("issues.priorityUrgent"),
    high: t("issues.priorityHigh"),
    normal: t("issues.priorityNormal"),
    low: t("issues.priorityLow"),
  };

  const typeLabel = (type: string): string => typeLabels[type] ?? type;
  const priorityLabel = (priority: string): string => priorityLabels[priority.toLowerCase()] ?? priority;

  const actor = await currentActor();
  let live: { board: Record<string, ApiIssue[]>; issues: ApiIssue[] } | null = null;
  if (actor) {
    try {
      const [board, liveIssues] = await Promise.all([fetchBoard(actor), fetchIssues(actor)]);
      live = { board, issues: liveIssues };
    } catch {
      live = null;
    }
  }

  const knownStatuses = new Set(liveColumns.flatMap(column => column.statuses));
  for (const status of new Set(live?.issues.map(issue => issue.status))) {
    if (!knownStatuses.has(status)) liveColumns.push({ id: "custom-" + status, label: status, hint: "", statuses: [status] });
  }

  return (
    <div className="page-stack issues-page">
      <header className="page-header">
        <div className="page-title-group">
          <h1>
            {t("issues.title")}
          </h1>
          <p className="page-lede">{t("issues.lede")}</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/issues/roadmap">{locale === "zh" ? "工单路线图" : "Roadmap"}</Link>
          <Link className="btn btn-ghost" href="/docs/sinan-events">
            <Icon name="branch" size={16} />
            {t("issues.rules")}
          </Link>
          <Link className="btn btn-primary" href="/requirements">
            <Icon name="sparkles" size={16} />
            {t("issues.split")}
          </Link>
        </div>
      </header>

      {live ? (
        <section className="panel" aria-labelledby="live-issues-title">
          <div className="section-heading">
            <div>
              <h2 id="live-issues-title">{t("issues.liveTitle")}</h2>
            </div>
            <span className="section-note">
              {formatMessage(t("issues.liveNote"), { count: live.issues.length })}
            </span>
          </div>

          {live.issues.length === 0 ? (
            <p className="section-note" style={{ padding: "0 26px 22px" }}>
              {t("issues.emptyLive")}
            </p>
          ) : (
            <div className="work-order-columns">
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
                          <Link className="issue-card-title" href={`/issues/${encodeURIComponent(issue.id)}`}>{issue.title}</Link>
                          <span className="issue-tags">
                            <span className="kind-tag">{typeLabel(issue.type)}</span>
                            {issue.status === "blocked" ? (
                              <span className="kind-tag issue-blocked">
                                {t("issues.blocked")}
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
      ) : (
        <section className="panel route-state">
          <p role="status">{actor
            ? (locale === "zh" ? "工单暂时无法读取。" : "Work orders are temporarily unavailable.")
            : (locale === "zh" ? "登录后查看工单看板。" : "Sign in to view the work order board.")}</p>
          {actor
            ? <a className="btn btn-ghost" href="/issues">{locale === "zh" ? "重新加载" : "Reload"}</a>
            : <Link className="btn btn-primary" href="/login">{locale === "zh" ? "登录" : "Sign in"}</Link>}
        </section>
      )}
      <details className="panel example-board">
        <summary>{locale === "zh" ? "试用示例看板" : "Try the sample board"}</summary>
        <p>{locale === "zh" ? "此处使用示例数据，移动工单仅在当前页面生效。" : "This board uses sample data. Changes last for this page visit."}</p>
        <IssueBoard initialIssues={sampleIssues} />
      </details>
    </div>
  );
}

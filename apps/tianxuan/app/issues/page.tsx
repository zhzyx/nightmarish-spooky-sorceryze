import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { IssueBoard } from "@/components/IssueBoard";
import { fetchBoard, fetchIssues, type ApiIssue } from "@/lib/api";
import { issues } from "@/lib/data";
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

  const done = issues.filter((issue) => issue.status === "done").length;
  const blocked = issues.filter((issue) => issue.blocked).length;
  const completion = Math.round((done / issues.length) * 100);

  const actor = process.env.TIANXUAN_ACTOR ?? "";
  let live: { board: Record<string, ApiIssue[]>; issues: ApiIssue[] } | null = null;
  if (actor || process.env.TIANXUAN_TOKEN) {
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
            {t("issues.title")}
            {locale === "zh" ? <span className="title-period">。</span> : null}
          </h1>
          <p className="page-lede">{t("issues.lede")}</p>
        </div>
        <div className="page-actions">
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
              <p className="section-kicker">SINAN · LIVE BOARD</p>
              <h2 id="live-issues-title">{t("issues.liveTitle")}</h2>
            </div>
            <span className="section-note">
              {formatMessage(t("issues.liveNote"), { count: live.issues.length })}
            </span>
          </div>

          <div className="board-caption" style={{ padding: "0 26px 16px", flexWrap: "wrap" }}>
            <span>
              <span className="live-dot" aria-hidden="true" />
              {formatMessage(t("issues.liveData"), { count: live.issues.length })}
            </span>
            <span>{liveCounts.map((item) => `${item.label} ${item.count}`).join(" · ")}</span>
          </div>

          {live.issues.length === 0 ? (
            <p className="section-note" style={{ padding: "0 26px 22px" }}>
              {t("issues.emptyLive")}
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
      ) : null}

      <section className="sprint-banner" aria-label={t("issues.sprintAria")}>
        <div className="sprint-main">
          <p className="section-kicker">{t("issues.sprintKicker")}</p>
          <h2>{t("issues.sprintTitle")}</h2>
          <span className="sprint-meta">
            <Icon name="clock" size={14} />
            {t("issues.sprintMeta")}
          </span>
        </div>
        <div className="sprint-progress">
          <div className="sprint-stat">
            <strong>{completion}%</strong>
            <span>{t("issues.overall")}</span>
          </div>
          <div className="meter meter-lg" aria-hidden="true">
            <span style={{ width: `${completion}%` }} />
          </div>
          <small>
            {formatMessage(t("issues.doneSummary"), { done, total: issues.length })}
            {blocked > 0 ? formatMessage(t("issues.blockedSummary"), { count: blocked }) : ""}
          </small>
        </div>
        <div className="sprint-people">
          <div className="avatar-stack">
            <span className="avatar avatar-sm avatar-jade">文</span>
            <span className="avatar avatar-sm avatar-gold">偃</span>
            <span className="avatar avatar-sm avatar-cinnabar">司</span>
            <span className="avatar avatar-sm avatar-mist">S</span>
          </div>
          <span>{formatMessage(t("issues.collaborators"), { count: 5 })}</span>
        </div>
      </section>

      <IssueBoard initialIssues={issues} />
    </div>
  );
}

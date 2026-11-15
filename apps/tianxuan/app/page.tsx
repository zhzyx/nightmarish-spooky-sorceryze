import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { AICommandBar } from "@/components/AICommandBar";
import { Icon, type IconName } from "@/components/Icon";
import {
  activityFeed,
  docs,
  getDoc,
  issues,
  recentDocIds,
  repos,
  type DocRecord,
  type IssueStatus,
} from "@/lib/data";
import { LOCALE_COOKIE, formatMessage, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "nav.home") };
}

export default function DashboardPage() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);

  const metrics: {
    label: string;
    value: string;
    note: string;
    icon: IconName;
    tone: string;
    trend: string;
  }[] = [
    {
      label: t("home.metricDocs"),
      value: "32",
      note: t("home.metricDocsNote"),
      icon: "docs",
      tone: "jade",
      trend: "+8",
    },
    {
      label: t("home.metricIssues"),
      value: "08",
      note: t("home.metricIssuesNote"),
      icon: "issues",
      tone: "cinnabar",
      trend: "3",
    },
    {
      label: t("home.metricRepos"),
      value: "04",
      note: t("home.metricReposNote"),
      icon: "repos",
      tone: "gold",
      trend: "6 PR",
    },
    {
      label: t("home.metricAi"),
      value: "12",
      note: t("home.metricAiNote"),
      icon: "sparkles",
      tone: "mist",
      trend: t("home.metricDemo"),
    },
  ];

  const issueStatusLabel: Record<IssueStatus, string> = {
    backlog: t("home.statusBacklog"),
    progress: t("home.statusProgress"),
    review: t("home.statusReview"),
    done: t("home.statusDone"),
  };

  const recentDocs = recentDocIds
    .map((id) => getDoc(id))
    .filter((doc): doc is DocRecord => Boolean(doc));
  const focusIssues = issues
    .filter((issue) => issue.status === "progress" || issue.status === "review")
    .slice(0, 4);
  const activeRepos = repos.filter((repo) => repo.status !== "只读").slice(0, 3);

  return (
    <div className="page-stack dashboard-page">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            {t("home.eyebrow")}
          </p>
          <h1>
            {t("home.heroA")}
            <br />
            <span>{t("home.heroB")}</span>
          </h1>
          <p className="hero-lede">{t("home.heroLede")}</p>
          <div className="hero-meta">
            <span className="hero-meta-item">
              <Icon name="docs" size={15} />
              {t("home.docsMeta")}
            </span>
            <span className="hero-meta-item">
              <Icon name="branch" size={15} />
              {t("home.reposMeta")}
            </span>
            <span className="hero-meta-item hero-meta-live">
              <span className="live-dot" aria-hidden="true" />
              {t("home.quiet")}
            </span>
          </div>
        </div>

        <div className="hero-aside" aria-hidden="true">
          <div className="hero-compass">
            <span className="compass-arc compass-arc-a" />
            <span className="compass-arc compass-arc-b" />
            <span className="compass-axis compass-axis-a" />
            <span className="compass-axis compass-axis-b" />
            <span className="compass-node compass-node-a" />
            <span className="compass-node compass-node-b" />
            <span className="compass-core">璇</span>
          </div>
          <div className="hero-aside-copy">
            <span>{t("home.workspace")}</span>
            <strong>{t("home.workspaceMeta")}</strong>
            <small>{t("home.workspaceMotto")}</small>
          </div>
        </div>
      </header>

      <AICommandBar />

      <section aria-label={t("home.summaryAria")} className="metric-grid">
        {metrics.map((metric) => (
          <article className={`metric-card tone-${metric.tone}`} key={metric.label}>
            <div className="metric-head">
              <span className="metric-icon">
                <Icon name={metric.icon} size={18} />
              </span>
              <span className="metric-trend">{metric.trend}</span>
            </div>
            <div className="metric-value-row">
              <strong>{metric.value}</strong>
              <span>{metric.label}</span>
            </div>
            <p>{metric.note}</p>
            <span className="metric-corner" aria-hidden="true" />
          </article>
        ))}
      </section>

      <div className="dashboard-columns">
        <div className="dashboard-primary">
          <section className="panel recent-panel" aria-labelledby="recent-docs-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">WENQU · KNOWLEDGE</p>
                <h2 id="recent-docs-title">{t("home.recentDocs")}</h2>
              </div>
              <Link className="text-link" href="/docs">
                {t("home.allDocs")}
                <Icon name="arrowRight" size={14} />
              </Link>
            </header>

            <div className="doc-list">
              {recentDocs.map((doc) => (
                <Link className="doc-row" href={`/docs/${doc.id}`} key={doc.id}>
                  <span className={`doc-glyph tone-${doc.spaceId === "sinan" ? "cinnabar" : doc.spaceId === "duobao" ? "gold" : "jade"}`}>
                    <Icon name="file" size={17} />
                  </span>
                  <span className="doc-row-main">
                    <span className="doc-row-title">
                      <strong>{doc.title}</strong>
                      <span className={`kind-tag kind-${doc.kind}`}>{doc.kind}</span>
                    </span>
                    <span className="doc-row-excerpt">{doc.excerpt}</span>
                    <span className="doc-row-sub">
                      {doc.spaceName} · {doc.updatedBy} · {doc.updated}
                    </span>
                  </span>
                  <span className="doc-row-side">
                    <span className="avatar avatar-sm avatar-mist" aria-hidden="true">
                      {doc.updatedBy.slice(0, 1)}
                    </span>
                    <span className="doc-read-time">{doc.readTime}</span>
                  </span>
                </Link>
              ))}
            </div>

            <footer className="panel-foot">
              <span>
                <Icon name="sparkles" size={14} />
                {t("home.aiAnchors")}
              </span>
              <span>{t("home.lastSync")}</span>
            </footer>
          </section>

          <section className="panel focus-panel" aria-labelledby="focus-issues-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">SINAN · MOMENTUM</p>
                <h2 id="focus-issues-title">{t("home.focus")}</h2>
              </div>
              <Link className="text-link" href="/issues">
                {t("home.openBoard")}
                <Icon name="arrowRight" size={14} />
              </Link>
            </header>

            <div className="focus-list">
              {focusIssues.map((issue) => (
                <Link className="focus-row" href="/issues" key={issue.id}>
                  <span className={`priority priority-${issue.priority.toLowerCase()}`}>{issue.priority}</span>
                  <span className="focus-main">
                    <span className="focus-title">
                      <span className="mono-key">{issue.key}</span>
                      {issue.title}
                      {issue.blocked ? (
                        <span className="blocked-mark">
                          <Icon name="alert" size={12} />
                          {t("home.blocked")}
                        </span>
                      ) : null}
                    </span>
                    <span className="focus-meta">
                      {issue.tags.map((tag) => (
                        <span className="micro-tag" key={tag}>
                          {tag}
                        </span>
                      ))}
                      <span>{issue.updated}</span>
                    </span>
                  </span>
                  <span className={`avatar avatar-sm avatar-${issue.assigneeTone}`} aria-hidden="true">
                    {issue.assignee.slice(0, 1)}
                  </span>
                  <span className={`issue-status issue-status-${issue.status}`}>
                    <span className="status-dot" aria-hidden="true" />
                    {issueStatusLabel[issue.status]}
                  </span>
                </Link>
              ))}
            </div>
          </section>
        </div>

        <aside className="dashboard-side">
          <section className="panel activity-panel" aria-labelledby="activity-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">DITING · SIGNALS</p>
                <h2 id="activity-title">{t("home.activity")}</h2>
              </div>
              <span className="live-tag">
                <span className="live-dot" aria-hidden="true" />
                {t("home.live")}
              </span>
            </header>

            <div className="activity-list">
              {activityFeed.slice(0, 4).map((activity) => (
                <Link className="activity-row" href={activity.href} key={activity.id}>
                  <span className={`avatar avatar-sm avatar-${activity.actorTone}`} aria-hidden="true">
                    {activity.actor.slice(0, 1)}
                  </span>
                  <span className="activity-main">
                    <span className="activity-text">
                      <strong>{activity.actor}</strong> {activity.action}
                    </span>
                    <span className="activity-target">{activity.target}</span>
                    <span className="activity-meta">{activity.meta}</span>
                  </span>
                  <time className="activity-time">{activity.time}</time>
                </Link>
              ))}
            </div>

            <footer className="panel-foot panel-foot-quiet">
              <span>{t("home.demoFeed")}</span>
              <span className="mono-small">SSE · idle</span>
            </footer>
          </section>

          <section className="panel repo-panel" aria-labelledby="repo-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">DUOBAO · CODE</p>
                <h2 id="repo-title">{t("home.activeRepos")}</h2>
              </div>
              <Link className="text-link" href="/repos">
                {t("home.browse")}
                <Icon name="arrowRight" size={14} />
              </Link>
            </header>

            <div className="repo-mini-list">
              {activeRepos.map((repo) => (
                <Link className="repo-mini" href="/repos" key={repo.id}>
                  <span className={`repo-mini-glyph tone-${repo.tone}`}>
                    <Icon name="repos" size={16} />
                  </span>
                  <span className="repo-mini-main">
                    <span className="repo-mini-head">
                      <strong>{repo.name}</strong>
                      <span className={`repo-state repo-state-${repo.status}`}>{repo.status}</span>
                    </span>
                    <span className="repo-mini-meta">
                      <span className={`language-dot tone-${repo.tone}`} aria-hidden="true" />
                      {repo.language}
                      <span>·</span>
                      <Icon name="branch" size={12} />
                      {repo.branch}
                    </span>
                  </span>
                  <span className="repo-mini-pr">
                    <Icon name="pullRequest" size={14} />
                    {repo.openPRs}
                  </span>
                </Link>
              ))}
            </div>

            <div className="repo-summary">
              <span>
                <strong>128</strong> {t("home.commitsSuffix")}
              </span>
              <span>
                <strong>6</strong> {t("home.pendingPRsSuffix")}
              </span>
              <span>
                <strong>0</strong> {t("home.conflictsSuffix")}
              </span>
            </div>
          </section>

          <section className="daily-note" aria-label={t("home.noteAria")}>
            <span className="note-seal" aria-hidden="true">
              静
            </span>
            <p>{t("home.noteText")}</p>
            <span className="note-caption">{t("home.noteCaption")}</span>
          </section>
        </aside>
      </div>

      <footer className="dashboard-footer">
        <span>
          <span className="footer-jade" aria-hidden="true" />
          {formatMessage(t("home.footer"), { count: docs.length })}
        </span>
        <span className="footer-mono">TIANXUAN / WEB SHELL / V0.1</span>
      </footer>
    </div>
  );
}

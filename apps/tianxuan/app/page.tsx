import type { Metadata } from "next";
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

export const metadata: Metadata = {
  title: "工作台",
};

const metrics: {
  label: string;
  value: string;
  note: string;
  icon: IconName;
  tone: string;
  trend: string;
}[] = [
  { label: "本周文档更新", value: "32", note: "分布在 4 个空间", icon: "docs", tone: "jade", trend: "+8" },
  { label: "进行中工单", value: "08", note: "2 项等待评审", icon: "issues", tone: "cinnabar", trend: "3" },
  { label: "活跃仓库", value: "04", note: "6 个合并请求", icon: "repos", tone: "gold", trend: "6 PR" },
  { label: "AI 协同次数", value: "12", note: "均待人工确认", icon: "sparkles", tone: "mist", trend: "演示" },
];

const issueStatusLabel: Record<IssueStatus, string> = {
  backlog: "待梳理",
  progress: "进行中",
  review: "评审中",
  done: "已完成",
};

export default function DashboardPage() {
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
            今日概览 · 共工工坊
          </p>
          <h1>
            把复杂留给系统，
            <br />
            <span>把清晰留给人。</span>
          </h1>
          <p className="hero-lede">
            文曲、司南与多宝，在同一张安静的工作台上。让每份文档都有去处，让每个决定都能被回读。
          </p>
          <div className="hero-meta">
            <span className="hero-meta-item">
              <Icon name="docs" size={15} />
              262 页文档
            </span>
            <span className="hero-meta-item">
              <Icon name="branch" size={15} />
              4 个活跃仓库
            </span>
            <span className="hero-meta-item hero-meta-live">
              <span className="live-dot" aria-hidden="true" />
              所有系统安静运行
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
            <span>当前工作区</span>
            <strong>单组织 · 首版</strong>
            <small>深色优先 · 扁平中国风</small>
          </div>
        </div>
      </header>

      <AICommandBar />

      <section aria-label="工作区摘要" className="metric-grid">
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
                <h2 id="recent-docs-title">近期文档</h2>
              </div>
              <Link className="text-link" href="/docs">
                全部文档
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
                AI 已为 8 份文档建立稳定锚点
              </span>
              <span>最后同步：刚刚</span>
            </footer>
          </section>

          <section className="panel focus-panel" aria-labelledby="focus-issues-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">SINAN · MOMENTUM</p>
                <h2 id="focus-issues-title">正在推进</h2>
              </div>
              <Link className="text-link" href="/issues">
                打开看板
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
                          阻塞
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
                <h2 id="activity-title">工作区动态</h2>
              </div>
              <span className="live-tag">
                <span className="live-dot" aria-hidden="true" />
                实时
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
              <span>所有动态均来自演示事件流</span>
              <span className="mono-small">SSE · idle</span>
            </footer>
          </section>

          <section className="panel repo-panel" aria-labelledby="repo-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">DUOBAO · CODE</p>
                <h2 id="repo-title">活跃仓库</h2>
              </div>
              <Link className="text-link" href="/repos">
                浏览
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
                <strong>128</strong> 次提交
              </span>
              <span>
                <strong>6</strong> 个待评审 PR
              </span>
              <span>
                <strong>0</strong> 个合入冲突
              </span>
            </div>
          </section>

          <section className="daily-note" aria-label="今日留白">
            <span className="note-seal" aria-hidden="true">
              静
            </span>
            <p>「留白不是空，是给下一步判断留下位置。」</p>
            <span className="note-caption">天璇 · 工作区札记</span>
          </section>
        </aside>
      </div>

      <footer className="dashboard-footer">
        <span>
          <span className="footer-jade" aria-hidden="true" />
          {docs.length} 份公开页面 · 数据为本地演示
        </span>
        <span className="footer-mono">TIANXUAN / WEB SHELL / V0.1</span>
      </footer>
    </div>
  );
}

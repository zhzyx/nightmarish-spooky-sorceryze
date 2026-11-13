import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { RepoBrowser } from "@/components/RepoBrowser";
import { fetchRepos, type ApiRepo } from "@/lib/api";
import { repos } from "@/lib/data";

export const metadata: Metadata = {
  title: "代码仓库",
};

export const dynamic = "force-dynamic";

const stats = [
  { label: "组织仓库", value: "04", note: "2 个活跃分支", icon: "repos" as const },
  { label: "本周提交", value: "128", note: "跨 3 个仓库", icon: "gitCommit" as const },
  { label: "待评审 PR", value: "06", note: "平均等待 2.4h", icon: "pullRequest" as const },
  { label: "合入冲突", value: "00", note: "队列运行正常", icon: "checkCircle" as const },
];

export default async function ReposPage() {
  const actor = process.env.TIANXUAN_ACTOR ?? "";
  let liveRepos: ApiRepo[] | null = null;
  if (actor) {
    try {
      liveRepos = await fetchRepos(actor);
    } catch {
      liveRepos = null;
    }
  }

  return (
    <div className="page-stack repos-page">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            DUOBAO · CODE &amp; MERGE
          </p>
          <h1>
            代码仓库<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            分支是工作的方法，合并回执是交付的证据。多宝复用可信 Git 服务，把评审、工单与精确候选放在同一条路径上。
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/docs/duobao-git">
            <Icon name="docs" size={16} />
            工程规范
          </Link>
          <Link className="btn btn-primary" href="/issues">
            <Icon name="issues" size={16} />
            查看合并队列
          </Link>
        </div>
      </header>

      {liveRepos && liveRepos.length > 0 ? (
        <section className="panel" aria-labelledby="live-repos-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">GITEA · LIVE</p>
              <h2 id="live-repos-title">实时仓库</h2>
            </div>
            <span className="section-note">{liveRepos.length} 个仓库来自 Gitea</span>
          </div>
          <div className="reading-list">
            {liveRepos.slice(0, 8).map((repo) => (
              <div className="reading-item" key={repo.full_name}>
                <span className="reading-index">{repo.private ? "私" : "公"}</span>
                <span className="reading-copy">
                  <strong>{repo.full_name}</strong>
                  <span>默认分支 {repo.default_branch}</span>
                </span>
                <Icon name="repos" size={14} />
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="repo-stat-strip" aria-label="仓库概览">
        {stats.map((stat) => (
          <article className="repo-stat" key={stat.label}>
            <span className="repo-stat-icon">
              <Icon name={stat.icon} size={16} />
            </span>
            <span className="repo-stat-copy">
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
              <small>{stat.note}</small>
            </span>
          </article>
        ))}
      </section>

      <RepoBrowser initialRepos={repos} />
    </div>
  );
}

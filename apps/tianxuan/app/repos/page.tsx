import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { LocalGitRepos } from "@/components/LocalGitRepos";
import { MergeQueuePanel } from "@/components/MergeQueuePanel";
import { RepoPulls } from "@/components/RepoPulls";
import { RepoTree } from "@/components/RepoTree";
import { fetchRepos, type ApiRepo } from "@/lib/api";

export const metadata: Metadata = {
  title: "代码仓库",
};

export const dynamic = "force-dynamic";

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

      <LocalGitRepos />

      <RepoTree />

      <MergeQueuePanel />

      <RepoPulls />

      {liveRepos && liveRepos.length > 0 ? (
        <section className="panel" aria-labelledby="live-repos-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">GITEA · LIVE</p>
              <h2 id="live-repos-title">实时仓库</h2>
            </div>
            <span className="section-note">{liveRepos.length} 个仓库来自 Gitea</span>
          </div>
          <div className="reading-list live-list">
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

    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { RepoBrowser } from "@/components/RepoBrowser";
import { repos } from "@/lib/data";

export const metadata: Metadata = {
  title: "代码仓库",
};

const stats = [
  { label: "组织仓库", value: "04", note: "2 个活跃分支", icon: "repos" as const },
  { label: "本周提交", value: "128", note: "跨 3 个仓库", icon: "gitCommit" as const },
  { label: "待评审 PR", value: "06", note: "平均等待 2.4h", icon: "pullRequest" as const },
  { label: "合入冲突", value: "00", note: "队列运行正常", icon: "checkCircle" as const },
];

export default function ReposPage() {
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

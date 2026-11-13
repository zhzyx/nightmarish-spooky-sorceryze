"use client";

import Link from "next/link";
import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { Icon, type IconName } from "@/components/Icon";
import type { RepoRecord } from "@/lib/data";

type RepoTab = "files" | "commits" | "pulls";

const repoTabs: { id: RepoTab; label: string; icon: IconName }[] = [
  { id: "files", label: "文件", icon: "folder" },
  { id: "commits", label: "提交", icon: "gitCommit" },
  { id: "pulls", label: "合并请求", icon: "pullRequest" },
];

export interface RepoBrowserProps {
  initialRepos: RepoRecord[];
}

export function RepoBrowser({ initialRepos }: RepoBrowserProps) {
  const [activeId, setActiveId] = useState(initialRepos[0]?.id ?? "");
  const [tab, setTab] = useState<RepoTab>("files");
  const [query, setQuery] = useState("");

  const visibleRepos = initialRepos.filter((repo) =>
    `${repo.name} ${repo.language} ${repo.description}`.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const activeRepo = visibleRepos.find((repo) => repo.id === activeId) ?? visibleRepos[0] ?? null;

  function chooseRepo(repoId: string) {
    setActiveId(repoId);
    setTab("files");
  }

  return (
    <div className="repo-browser">
      <aside className="repo-index panel" aria-label="仓库列表">
        <header className="repo-index-head">
          <div>
            <p className="section-kicker">DUOBAO · SOURCE</p>
            <h2>仓库</h2>
          </div>
          <span className="repo-count">{initialRepos.length}</span>
        </header>

        <label className="repo-search">
          <Icon name="search" size={15} />
          <input
            aria-label="搜索仓库"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索仓库或语言"
            type="search"
            value={query}
          />
        </label>

        <div className="repo-list">
          {visibleRepos.map((repo) => (
            <button
              aria-current={activeRepo?.id === repo.id ? "true" : undefined}
              className={`repo-list-item${activeRepo?.id === repo.id ? " is-active" : ""}`}
              key={repo.id}
              onClick={() => chooseRepo(repo.id)}
              type="button"
            >
              <span className={`repo-list-icon tone-${repo.tone}`}>
                <Icon name="repos" size={16} />
              </span>
              <span className="repo-list-copy">
                <span className="repo-list-title">
                  <strong>{repo.name}</strong>
                  {repo.visibility === "只读镜像" ? <Icon name="lock" size={11} /> : null}
                </span>
                <span className="repo-list-meta">
                  <span className={`language-dot tone-${repo.tone}`} aria-hidden="true" />
                  {repo.language}
                  <span>·</span>
                  {repo.updated}
                </span>
              </span>
              <span className="repo-list-pr">{repo.openPRs}</span>
            </button>
          ))}
          {visibleRepos.length === 0 ? (
            <EmptyState
              compact
              description="试试仓库名、命名空间或编程语言。"
              eyebrow="DUOBAO · NO REPO"
              title="没有找到仓库"
            />
          ) : null}
        </div>

        <footer className="repo-index-foot">
          <span>
            <span className="live-dot" aria-hidden="true" />
            多宝 · 只读演示
          </span>
          <span>4 个仓库</span>
        </footer>
      </aside>

      {activeRepo ? (
        <section className="repo-detail panel" aria-label={`${activeRepo.name} 仓库详情`}>
          <header className="repo-detail-head">
            <div className="repo-detail-title">
              <p className="section-kicker">{activeRepo.namespace.toUpperCase()} / REPOSITORY</p>
              <div className="repo-name-row">
                <h2>{activeRepo.name}</h2>
                <span className="repo-visibility">
                  <Icon name={activeRepo.visibility === "私有" ? "lock" : "users"} size={12} />
                  {activeRepo.visibility}
                </span>
                <span className={`repo-state repo-state-${activeRepo.status}`}>{activeRepo.status}</span>
              </div>
              <p>{activeRepo.description}</p>
            </div>
            <div className="repo-detail-actions">
              <Link className="btn btn-ghost btn-sm" href="/issues">
                <Icon name="issues" size={14} />
                关联工单
              </Link>
              <button className="btn btn-primary btn-sm" onClick={() => setTab("pulls")} type="button">
                <Icon name="pullRequest" size={14} />
                查看合并请求
              </button>
            </div>
          </header>

          <div className="repo-meta-row">
            <span className="repo-meta-language">
              <span className={`language-dot tone-${activeRepo.tone}`} aria-hidden="true" />
              {activeRepo.language}
            </span>
            <span>
              <Icon name="branch" size={14} />
              {activeRepo.branch}
            </span>
            <span>
              <Icon name="gitCommit" size={14} />
              {activeRepo.commits} 次提交
            </span>
            <span>
              <Icon name="clock" size={14} />
              更新于 {activeRepo.updated}
            </span>
            <span className="repo-meta-lock">
              <Icon name="lock" size={13} />
              分支保护已开启
            </span>
          </div>

          <div className="repo-toolbar">
            <div aria-label="仓库视图" className="repo-tabs" role="tablist">
              {repoTabs.map((repoTab) => {
                const count =
                  repoTab.id === "files"
                    ? activeRepo.files.length
                    : repoTab.id === "commits"
                      ? activeRepo.commitLog.length
                      : activeRepo.pullRequests.length;
                return (
                  <button
                    aria-controls={`repo-panel-${repoTab.id}`}
                    aria-selected={tab === repoTab.id}
                    className={tab === repoTab.id ? "is-active" : ""}
                    id={`repo-tab-${repoTab.id}`}
                    key={repoTab.id}
                    onClick={() => setTab(repoTab.id)}
                    role="tab"
                    type="button"
                  >
                    <Icon name={repoTab.icon} size={14} />
                    {repoTab.label}
                    <span>{count}</span>
                  </button>
                );
              })}
            </div>
            <span className="repo-toolbar-note">
              <Icon name="cloud" size={14} />
              本次不连接远端
            </span>
          </div>

          <div
            aria-labelledby={`repo-tab-${tab}`}
            className="repo-tab-panel"
            id={`repo-panel-${tab}`}
            role="tabpanel"
          >
            {tab === "files" ? (
              <div className="file-table">
                <div className="file-table-head">
                  <span>名称</span>
                  <span>最近提交</span>
                  <span>更新</span>
                </div>
                {activeRepo.files.map((file) => (
                  <div className="file-row" key={`${activeRepo.id}-${file.name}`}>
                    <span className="file-name">
                      <span className={`file-icon${file.kind === "dir" ? " is-dir" : ""}`}>
                        <Icon name={file.kind === "dir" ? "folder" : "file"} size={16} />
                      </span>
                      {file.name}
                    </span>
                    <span className="file-commit">{file.message}</span>
                    <span className="file-time">{file.when}</span>
                  </div>
                ))}
              </div>
            ) : null}

            {tab === "commits" ? (
              <div className="commit-list">
                {activeRepo.commitLog.map((commit) => (
                  <div className="commit-row" key={commit.sha}>
                    <span className="commit-mark">
                      <Icon name="gitCommit" size={16} />
                    </span>
                    <span className="commit-main">
                      <strong>{commit.message}</strong>
                      <span>
                        <span className="commit-sha">{commit.sha}</span>
                        <span>{commit.author}</span>
                        <span>{commit.when}</span>
                      </span>
                    </span>
                    <span className="commit-badge">{activeRepo.branch}</span>
                  </div>
                ))}
              </div>
            ) : null}

            {tab === "pulls" ? (
              activeRepo.pullRequests.length > 0 ? (
                <div className="pull-list">
                  {activeRepo.pullRequests.map((pull) => (
                    <div className="pull-row" key={pull.id}>
                      <span className="pull-icon">
                        <Icon name="pullRequest" size={16} />
                      </span>
                      <span className="pull-main">
                        <strong>
                          <span className="mono-key">{pull.id}</span>
                          {pull.title}
                        </strong>
                        <span>
                          {pull.author} · {pull.comments} 条评论 · {pull.age}前
                        </span>
                      </span>
                      <span className={`pull-status pull-status-${pull.status}`}>{pull.status}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  compact
                  description="这个仓库暂时没有待处理的合并请求。"
                  eyebrow="DUOBAO · CLEAN"
                  title="没有打开的合并请求"
                />
              )
            ) : null}
          </div>

          <footer className="repo-detail-foot">
            <span>
              <Icon name="lock" size={13} />
              合入需通过 1 位评审与分支保护检查
            </span>
            <span className="mono-small">base · {activeRepo.branch}</span>
          </footer>
        </section>
      ) : (
        <section className="repo-detail panel">
          <EmptyState
            description="尝试清除筛选，或前往需求工作台生成一个新的工程仓库。"
            eyebrow="DUOBAO · EMPTY"
            title="选择一个仓库"
          />
        </section>
      )}
    </div>
  );
}

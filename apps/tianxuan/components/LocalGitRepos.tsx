"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import {
  fetchLocalBranches,
  fetchLocalLog,
  fetchLocalRepos,
  type ApiCommit,
  type ApiLocalRepo,
} from "@/lib/local-git-api";

type LoadState = "loading" | "ready" | "error";
type DetailState = "idle" | "loading" | "ready" | "error";

const headingStyle = {
  padding: "24px 26px 0",
  marginBottom: 0,
} as const;

const panelBodyStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "14px",
  padding: "16px 26px 22px",
} as const;

const repoListStyle = { padding: 0 } as const;

const repoButtonStyle = {
  width: "100%",
  border: 0,
  background: "transparent",
  color: "inherit",
  cursor: "pointer",
  font: "inherit",
  textAlign: "left",
} as const;

const repoButtonActiveStyle = {
  ...repoButtonStyle,
  background: "rgba(245, 242, 234, 0.05)",
} as const;

const branchRowStyle = {
  display: "flex",
  gap: "6px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const commitListStyle = { padding: 0, marginTop: "8px" } as const;

const commitItemStyle = {
  gridTemplateColumns: "64px minmax(0, 1fr) 14px",
} as const;

const errorRowStyle = {
  display: "flex",
  gap: "12px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const errorTextStyle = { color: "#D48B80" } as const;

function shortSha(sha: string): string {
  const trimmed = sha.trim();
  return trimmed ? trimmed.slice(0, 7) : "—";
}

function formatTime(value: string): string {
  const normalized = value.replace("T", " ").replace(/\.\d+/, "");
  const match = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})/.exec(normalized);
  return match ? `${match[1]} ${match[2]}` : value || "未知时间";
}

export function LocalGitRepos() {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR ?? "";
  const [repos, setRepos] = useState<ApiLocalRepo[]>([]);
  const [reposState, setReposState] = useState<LoadState>("loading");
  const [reposError, setReposError] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [branches, setBranches] = useState<string[]>([]);
  const [commits, setCommits] = useState<ApiCommit[]>([]);
  const [detailState, setDetailState] = useState<DetailState>("idle");
  const [detailError, setDetailError] = useState("");
  const requestRef = useRef(0);

  const selectRepo = useCallback(
    async (name: string) => {
      if (!actor) {
        return;
      }
      const request = requestRef.current + 1;
      requestRef.current = request;
      setSelectedRepo(name);
      setBranches([]);
      setCommits([]);
      setDetailState("loading");
      setDetailError("");
      try {
        const nextBranches = await fetchLocalBranches(actor, name);
        if (requestRef.current !== request) {
          return;
        }
        setBranches(nextBranches);
        const firstBranch = nextBranches[0];
        const nextCommits = firstBranch
          ? await fetchLocalLog(actor, name, firstBranch)
          : [];
        if (requestRef.current !== request) {
          return;
        }
        setCommits(nextCommits);
        setDetailState("ready");
      } catch {
        if (requestRef.current !== request) {
          return;
        }
        setDetailState("error");
        setDetailError("无法读取该仓库的分支或提交，请确认后端服务已启动且仓库仍然存在。");
      }
    },
    [actor],
  );

  const loadRepos = useCallback(async () => {
    if (!actor) {
      return;
    }
    const request = requestRef.current + 1;
    requestRef.current = request;
    setReposState("loading");
    setReposError("");
    setRepos([]);
    setSelectedRepo(null);
    setBranches([]);
    setCommits([]);
    setDetailState("idle");
    setDetailError("");
    try {
      const nextRepos = await fetchLocalRepos(actor);
      if (requestRef.current !== request) {
        return;
      }
      setRepos(nextRepos);
      setReposState("ready");
      if (nextRepos.length > 0) {
        void selectRepo(nextRepos[0]);
      }
    } catch {
      if (requestRef.current !== request) {
        return;
      }
      setReposState("error");
      setReposError("无法读取本地仓库列表，请确认后端服务已启动，且 TIANXUAN_REPO_ROOT 已配置。");
    }
  }, [actor, selectRepo]);

  useEffect(() => {
    void loadRepos();
  }, [loadRepos]);

  function retrySelectedRepo() {
    if (selectedRepo) {
      void selectRepo(selectedRepo);
    }
  }

  if (!actor) {
    return (
      <section aria-label="本地 Git 仓库" className="panel">
        <div className="section-heading" style={headingStyle}>
          <div>
            <p className="section-kicker">DUOBAO · LOCAL GIT</p>
            <h2>本地仓库</h2>
          </div>
          <span className="mono-key">未启用</span>
        </div>
        <div style={panelBodyStyle}>
          <p className="section-note">
            <Icon name="lock" size={13} />
            未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，本地 Git 浏览面板已禁用，不会发起任何请求。
          </p>
        </div>
      </section>
    );
  }

  const summary =
    reposState === "loading"
      ? "读取中…"
      : reposState === "error"
        ? "读取失败"
        : `${repos.length} 个仓库`;

  return (
    <section
      aria-busy={reposState === "loading" || detailState === "loading"}
      aria-label="本地 Git 仓库"
      className="panel"
    >
      <div className="section-heading" style={headingStyle}>
        <div>
          <p className="section-kicker">DUOBAO · LOCAL GIT</p>
          <h2>本地仓库</h2>
        </div>
        <span className="mono-key">{summary}</span>
      </div>

      <div style={panelBodyStyle}>
        {reposState === "loading" ? (
          <p className="section-note">正在读取本地仓库…</p>
        ) : null}

        {reposState === "error" ? (
          <div style={errorRowStyle}>
            <p className="section-note" role="alert" style={errorTextStyle}>
              <Icon name="alert" size={13} /> {reposError}
            </p>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => void loadRepos()}
              type="button"
            >
              <Icon name="history" size={12} />
              重新加载
            </button>
          </div>
        ) : null}

        {reposState === "ready" && repos.length === 0 ? (
          <p className="section-note">
            <Icon name="repos" size={13} />
            TIANXUAN_REPO_ROOT 下还没有 .git 仓库，先创建裸仓库后再回到这里。
          </p>
        ) : null}

        {reposState === "ready" && repos.length > 0 ? (
          <div className="repo-browser">
            <div>
              <p className="mono-key" style={{ marginBottom: "4px" }}>
                选择仓库
              </p>
              <div aria-label="本地仓库列表" className="reading-list live-list" style={repoListStyle}>
                {repos.map((repo) => {
                  const active = repo === selectedRepo;
                  return (
                    <button
                      aria-pressed={active}
                      className="reading-item"
                      key={repo}
                      onClick={() => void selectRepo(repo)}
                      style={active ? repoButtonActiveStyle : repoButtonStyle}
                      type="button"
                    >
                      <span className="reading-index">GIT</span>
                      <span className="reading-copy">
                        <strong>{repo}</strong>
                        <span>{active ? "当前仓库" : "本地裸仓库"}</span>
                      </span>
                      <Icon name="chevronRight" size={14} />
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              {detailState === "idle" ? (
                <p className="section-note">选择一个仓库以查看分支与最近提交。</p>
              ) : null}

              {detailState === "loading" ? (
                <p className="section-note">正在读取 {selectedRepo} 的分支与提交…</p>
              ) : null}

              {detailState === "error" ? (
                <div style={errorRowStyle}>
                  <p className="section-note" role="alert" style={errorTextStyle}>
                    <Icon name="alert" size={13} /> {detailError}
                  </p>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={retrySelectedRepo}
                    type="button"
                  >
                    <Icon name="history" size={12} />
                    重试
                  </button>
                </div>
              ) : null}

              {detailState === "ready" ? (
                branches.length === 0 ? (
                  <p className="section-note">
                    <Icon name="branch" size={13} />
                    该仓库还没有本地分支。
                  </p>
                ) : (
                  <>
                    <div style={branchRowStyle}>
                      <span className="mono-key">分支</span>
                      {branches.map((branch) => (
                        <span className="kind-tag" key={branch}>
                          {branch}
                        </span>
                      ))}
                    </div>

                    <p className="mono-key" style={{ marginTop: "12px" }}>
                      最近提交 · {branches[0]}
                    </p>

                    {commits.length > 0 ? (
                      <div
                        aria-label={`${selectedRepo} 的最近提交`}
                        className="reading-list live-list"
                        style={commitListStyle}
                      >
                        {commits.map((commit) => (
                          <div className="reading-item" key={commit.sha} style={commitItemStyle}>
                            <span className="reading-index" title={commit.sha}>
                              {shortSha(commit.sha)}
                            </span>
                            <span className="reading-copy">
                              <strong title={commit.message}>
                                {commit.message || "（无提交说明）"}
                              </strong>
                              <span>
                                {commit.author || "未知作者"} · {formatTime(commit.date)}
                              </span>
                            </span>
                            <Icon name="gitCommit" size={14} />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="section-note" style={{ marginTop: "8px" }}>
                        该分支还没有提交记录。
                      </p>
                    )}
                  </>
                )
              ) : null}
            </div>
          </div>
        ) : null}

        <p className="section-note">
          <Icon name="gitCommit" size={12} />
          只读浏览本地裸仓库，最多显示所选分支最近 10 条提交。
        </p>
      </div>
    </section>
  );
}

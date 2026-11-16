"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";
import {
  fetchLocalBranches,
  fetchLocalLog,
  fetchLocalRepos,
  type ApiCommit,
  type ApiLocalRepo,
} from "@/lib/local-git-api";
import { useActor } from "@/lib/use-actor";

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

function formatTime(value: string, fallback: string): string {
  const normalized = value.replace("T", " ").replace(/\.\d+/, "");
  const match = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})/.exec(normalized);
  return match ? `${match[1]} ${match[2]}` : value || fallback;
}

export function LocalGitRepos() {
  const actor = useActor();
  const { t } = useI18n();
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
        setDetailError(t("local.detailError"));
      }
    },
    [actor, t],
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
      setReposError(t("local.reposError"));
    }
  }, [actor, selectRepo, t]);

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
      <section aria-label={t("local.aria")} className="panel">
        <div className="section-heading" style={headingStyle}>
          <div>
            <p className="section-kicker">DUOBAO · LOCAL GIT</p>
            <h2>{t("local.title")}</h2>
          </div>
          <span className="mono-key">{t("local.disabled")}</span>
        </div>
        <div style={panelBodyStyle}>
          <p className="section-note">
            <Icon name="lock" size={13} />
            {t("local.disabledNote")}
          </p>
        </div>
      </section>
    );
  }

  const summary =
    reposState === "loading"
      ? t("local.summaryLoading")
      : reposState === "error"
        ? t("local.summaryError")
        : formatMessage(t("local.summaryCount"), { count: repos.length });

  return (
    <section
      aria-busy={reposState === "loading" || detailState === "loading"}
      aria-label={t("local.aria")}
      className="panel"
    >
      <div className="section-heading" style={headingStyle}>
        <div>
          <p className="section-kicker">DUOBAO · LOCAL GIT</p>
          <h2>{t("local.title")}</h2>
        </div>
        <span className="mono-key">{summary}</span>
      </div>

      <div style={panelBodyStyle}>
        {reposState === "loading" ? (
          <p className="section-note">{t("local.loading")}</p>
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
              {t("local.reload")}
            </button>
          </div>
        ) : null}

        {reposState === "ready" && repos.length === 0 ? (
          <p className="section-note">
            <Icon name="repos" size={13} />
            {t("local.emptyRoot")}
          </p>
        ) : null}

        {reposState === "ready" && repos.length > 0 ? (
          <div className="repo-browser">
            <div>
              <p className="mono-key" style={{ marginBottom: "4px" }}>
                {t("local.selectRepo")}
              </p>
              <div aria-label={t("local.repoListAria")} className="reading-list live-list" style={repoListStyle}>
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
                        <span>{active ? t("local.currentRepo") : t("local.bareRepo")}</span>
                      </span>
                      <Icon name="chevronRight" size={14} />
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              {detailState === "idle" ? (
                <p className="section-note">{t("local.selectHint")}</p>
              ) : null}

              {detailState === "loading" ? (
                <p className="section-note">
                  {formatMessage(t("local.loadingRepo"), { repo: selectedRepo ?? "" })}
                </p>
              ) : null}

              {detailState === "error" ? (
                <div style={errorRowStyle}>
                  <p className="section-note" role="alert" style={errorTextStyle}>
                    <Icon name="alert" size={13} /> {detailError}
                  </p>
                  <button className="btn btn-ghost btn-sm" onClick={retrySelectedRepo} type="button">
                    <Icon name="history" size={12} />
                    {t("local.retry")}
                  </button>
                </div>
              ) : null}

              {detailState === "ready" ? (
                branches.length === 0 ? (
                  <p className="section-note">
                    <Icon name="branch" size={13} />
                    {t("local.noBranches")}
                  </p>
                ) : (
                  <>
                    <div style={branchRowStyle}>
                      <span className="mono-key">{t("local.branch")}</span>
                      {branches.map((branch) => (
                        <span className="kind-tag" key={branch}>
                          {branch}
                        </span>
                      ))}
                    </div>

                    <p className="mono-key" style={{ marginTop: "12px" }}>
                      {formatMessage(t("local.recentCommits"), { branch: branches[0] })}
                    </p>

                    {commits.length > 0 ? (
                      <div
                        aria-label={formatMessage(t("local.commitsAria"), { repo: selectedRepo ?? "" })}
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
                                {commit.message || t("local.noMessage")}
                              </strong>
                              <span>
                                {commit.author || t("local.unknownAuthor")} ·{" "}
                                {formatTime(commit.date, t("local.unknownTime"))}
                              </span>
                            </span>
                            <Icon name="gitCommit" size={14} />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="section-note" style={{ marginTop: "8px" }}>
                        {t("local.noCommits")}
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
          {t("local.note")}
        </p>
      </div>
    </section>
  );
}

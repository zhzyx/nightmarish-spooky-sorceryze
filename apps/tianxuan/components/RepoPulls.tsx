"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import {
  createPull,
  fetchBranches,
  fetchPulls,
  mergePull,
  type ApiBranch,
  type ApiPull,
  type MergeMethod,
} from "@/lib/gitea-pulls-api";

type LoadState = "idle" | "loading" | "ready" | "error";

const OWNER_STORAGE_KEY = "tianxuan.pulls.owner";
const REPO_STORAGE_KEY = "tianxuan.pulls.repo";

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

const loadFormStyle = {
  display: "flex",
  gap: "10px",
  alignItems: "flex-end",
  flexWrap: "wrap",
} as const;

const fieldStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "5px",
  flex: "1 1 150px",
  minWidth: 0,
} as const;

const inputStyle = {
  width: "100%",
  minWidth: 0,
  height: "33px",
  padding: "0 10px",
  border: "1px solid var(--line)",
  borderRadius: "8px",
  background: "rgba(245, 242, 234, 0.025)",
  color: "rgba(245, 242, 234, 0.8)",
  fontSize: "10px",
} as const;

const selectStyle = {
  ...inputStyle,
  cursor: "pointer",
} as const;

const textareaStyle = {
  ...inputStyle,
  height: "auto",
  minHeight: "72px",
  padding: "9px 10px",
  lineHeight: 1.6,
  resize: "vertical",
} as const;

const createFormStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: "10px",
  padding: "14px",
  border: "1px solid var(--line)",
  borderRadius: "13px",
  background: "rgba(245, 242, 234, 0.02)",
} as const;

const formActionsStyle = {
  display: "flex",
  gap: "10px",
  alignItems: "center",
  flexWrap: "wrap",
  gridColumn: "1 / -1",
} as const;

const errorRowStyle = {
  display: "flex",
  gap: "12px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const errorTextStyle = { color: "#D48B80" } as const;

const noticeTextStyle = { color: "#9CCBBF" } as const;

const pullItemStyle = {
  gridTemplateColumns: "44px minmax(0, 1fr) auto",
  alignItems: "start",
  rowGap: "2px",
} as const;

const pullActionsStyle = {
  display: "flex",
  gap: "8px",
  alignItems: "center",
  flexWrap: "wrap",
  gridColumn: "2 / -1",
  marginTop: "4px",
} as const;

const mergeSelectStyle = {
  ...selectStyle,
  width: "auto",
  height: "32px",
  fontSize: "9px",
} as const;

const loadButtonStyle = { flex: "0 0 auto", height: "32px" } as const;

function normalizeMergeMethod(value: string): MergeMethod {
  return value === "squash" || value === "rebase" ? value : "merge";
}

function storedValue(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function rememberValue(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // localStorage 不可用时忽略，面板仍可正常使用。
  }
}

export function RepoPulls() {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR ?? "";
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [activeOwner, setActiveOwner] = useState("");
  const [activeRepo, setActiveRepo] = useState("");
  const [branches, setBranches] = useState<ApiBranch[]>([]);
  const [pulls, setPulls] = useState<ApiPull[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [title, setTitle] = useState("");
  const [head, setHead] = useState("");
  const [base, setBase] = useState("main");
  const [body, setBody] = useState("");
  const [mergeMethods, setMergeMethods] = useState<Record<number, MergeMethod>>({});
  const requestRef = useRef(0);

  useEffect(() => {
    if (!actor) {
      return;
    }
    setOwner(storedValue(OWNER_STORAGE_KEY));
    setRepo(storedValue(REPO_STORAGE_KEY));
  }, [actor]);

  const load = useCallback(
    async (ownerValue: string, repoValue: string) => {
      const nextOwner = ownerValue.trim();
      const nextRepo = repoValue.trim();
      if (!actor || !nextOwner || !nextRepo) {
        return;
      }
      const request = requestRef.current + 1;
      requestRef.current = request;
      setLoadState("loading");
      setLoadError("");
      setActionError("");
      setNotice("");
      setBranches([]);
      setPulls([]);
      setActiveOwner(nextOwner);
      setActiveRepo(nextRepo);
      rememberValue(OWNER_STORAGE_KEY, nextOwner);
      rememberValue(REPO_STORAGE_KEY, nextRepo);
      try {
        const [nextBranches, nextPulls] = await Promise.all([
          fetchBranches(actor, nextOwner, nextRepo),
          fetchPulls(actor, nextOwner, nextRepo, "open"),
        ]);
        if (requestRef.current !== request) {
          return;
        }
        const nextBase = nextBranches.some((branch) => branch.name === "main")
          ? "main"
          : nextBranches[0]?.name ?? "main";
        setBranches(nextBranches);
        setPulls(nextPulls);
        setBase(nextBase);
        setHead((previous) => {
          if (
            previous &&
            previous !== nextBase &&
            nextBranches.some((branch) => branch.name === previous)
          ) {
            return previous;
          }
          return (
            nextBranches.find((branch) => branch.name !== nextBase)?.name ??
            nextBranches[0]?.name ??
            ""
          );
        });
        setLoadState("ready");
      } catch (error) {
        if (requestRef.current !== request) {
          return;
        }
        setLoadState("error");
        setLoadError(
          `无法读取分支或 Pull Request，请确认 Gitea 已配置且 ${nextOwner}/${nextRepo} 存在。${
            error instanceof Error ? `（${error.message}）` : ""
          }`,
        );
      }
    },
    [actor],
  );

  function startLoad() {
    if (!actor) {
      return;
    }
    if (!owner.trim() || !repo.trim()) {
      setActionError("请先填写 owner 与 repo，再点击“加载”。");
      return;
    }
    void load(owner, repo);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!actor || busy || loadState !== "ready") {
      return;
    }
    const nextTitle = title.trim();
    if (!nextTitle) {
      setActionError("请填写 Pull Request 标题。");
      return;
    }
    if (!head || !base) {
      setActionError("请选择 head 与 base 分支。");
      return;
    }
    if (head === base) {
      setActionError("head 与 base 不能是同一个分支。");
      return;
    }
    setBusy("create");
    setActionError("");
    setNotice("");
    try {
      const created = await createPull(actor, activeOwner, activeRepo, {
        title: nextTitle,
        head,
        base,
        body: body.trim(),
      });
      setTitle("");
      setBody("");
      await load(activeOwner, activeRepo);
      setNotice(`已创建 PR #${created.number}「${created.title || nextTitle}」。`);
    } catch {
      setActionError("创建 Pull Request 失败，请确认分支存在、Gitea 已配置且当前账号有权限。");
    } finally {
      setBusy("");
    }
  }

  async function submitMerge(pull: ApiPull) {
    if (!actor || busy || loadState !== "ready") {
      return;
    }
    const method = mergeMethods[pull.number] ?? "merge";
    if (!window.confirm(`确认以 ${method} 方式合并 PR #${pull.number}「${pull.title}」？`)) {
      return;
    }
    setBusy(`merge:${pull.number}`);
    setActionError("");
    setNotice("");
    try {
      const result = await mergePull(actor, activeOwner, activeRepo, pull.number, method);
      await load(activeOwner, activeRepo);
      setNotice(
        result.merged
          ? `PR #${pull.number} 已以 ${method} 方式合并${
              result.sha ? `（${result.sha.slice(0, 7)}）` : ""
            }。`
          : `PR #${pull.number} 未报告合并成功，请到 Gitea 查看。`,
      );
    } catch {
      setActionError(`合并 PR #${pull.number} 失败，请确认 PR 仍处于 open 状态且没有冲突。`);
    } finally {
      setBusy("");
    }
  }

  if (!actor) {
    return (
      <section aria-label="Gitea Pull Request 管理" className="panel">
        <div className="section-heading" style={headingStyle}>
          <div>
            <p className="section-kicker">DUOBAO · GITEA PULLS</p>
            <h2>Pull Request 管理</h2>
          </div>
          <span className="mono-key">未启用</span>
        </div>
        <div style={panelBodyStyle}>
          <p className="section-note">
            <Icon name="lock" size={13} />
            未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，Pull Request 面板已禁用，不会发起任何请求。
          </p>
        </div>
      </section>
    );
  }

  const summary =
    loadState === "idle"
      ? "等待加载"
      : loadState === "loading"
        ? "读取中…"
        : loadState === "error"
          ? "读取失败"
          : `${pulls.length} 个 open PR`;

  const createDisabled =
    busy !== "" ||
    loadState !== "ready" ||
    branches.length === 0 ||
    !title.trim() ||
    !head ||
    !base ||
    head === base;

  return (
    <section
      aria-busy={loadState === "loading" || busy !== ""}
      aria-label="Gitea Pull Request 管理"
      className="panel"
    >
      <div className="section-heading" style={headingStyle}>
        <div>
          <p className="section-kicker">DUOBAO · GITEA PULLS</p>
          <h2>Pull Request 管理</h2>
        </div>
        <span className="mono-key">{summary}</span>
      </div>

      <div style={panelBodyStyle}>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            startLoad();
          }}
          style={loadFormStyle}
        >
          <label style={fieldStyle}>
            <span className="mono-key">owner</span>
            <input
              aria-label="仓库 owner"
              autoComplete="off"
              onChange={(event) => setOwner(event.target.value)}
              placeholder="owner"
              spellCheck={false}
              style={inputStyle}
              value={owner}
            />
          </label>
          <label style={fieldStyle}>
            <span className="mono-key">repo</span>
            <input
              aria-label="仓库 repo"
              autoComplete="off"
              onChange={(event) => setRepo(event.target.value)}
              placeholder="repo"
              spellCheck={false}
              style={inputStyle}
              value={repo}
            />
          </label>
          <button
            className="btn btn-ghost btn-sm"
            disabled={loadState === "loading" || busy !== ""}
            style={loadButtonStyle}
            type="submit"
          >
            <Icon name="search" size={12} />
            加载
          </button>
        </form>

        {actionError ? (
          <p className="section-note" role="alert" style={errorTextStyle}>
            <Icon name="alert" size={13} /> {actionError}
          </p>
        ) : null}

        {notice ? (
          <p className="section-note" role="status" style={noticeTextStyle}>
            <Icon name="checkCircle" size={13} /> {notice}
          </p>
        ) : null}

        {loadState === "idle" ? (
          <p className="section-note">
            <Icon name="pullRequest" size={13} />
            填写 owner 与 repo 后点击“加载”，查看分支与 open 状态的 Pull Request。
          </p>
        ) : null}

        {loadState === "loading" ? (
          <p className="section-note">
            正在读取 {activeOwner}/{activeRepo} 的分支与 Pull Request…
          </p>
        ) : null}

        {loadState === "error" ? (
          <div style={errorRowStyle}>
            <p className="section-note" role="alert" style={errorTextStyle}>
              <Icon name="alert" size={13} /> {loadError}
            </p>
            <button className="btn btn-ghost btn-sm" onClick={startLoad} type="button">
              <Icon name="history" size={12} />
              重试
            </button>
          </div>
        ) : null}

        {loadState === "ready" ? (
          <>
            <div>
              <p className="mono-key" style={{ marginBottom: "6px" }}>
                OPEN PULL REQUESTS · {activeOwner}/{activeRepo}
              </p>
              {pulls.length === 0 ? (
                <p className="section-note">
                  <Icon name="pullRequest" size={13} />
                  当前没有处于 open 状态的 Pull Request。
                </p>
              ) : (
                <div
                  aria-label="开放中的 Pull Request 列表"
                  className="reading-list live-list"
                  style={{ padding: 0 }}
                >
                  {pulls.map((pull) => (
                    <div className="reading-item" key={pull.number} style={pullItemStyle}>
                      <span className="reading-index">#{pull.number}</span>
                      <span className="reading-copy">
                        <strong title={pull.title}>{pull.title || "（无标题）"}</strong>
                        <span>
                          {pull.head || "?"} → {pull.base || "?"}
                        </span>
                      </span>
                      <span className="kind-tag">{pull.state || "open"}</span>
                      <span style={pullActionsStyle}>
                        {pull.html_url ? (
                          <a
                            className="btn btn-ghost btn-sm"
                            href={pull.html_url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            <Icon name="link" size={12} />
                            在 Gitea 打开
                          </a>
                        ) : null}
                        {pull.state === "open" ? (
                          <>
                            <select
                              aria-label={`PR #${pull.number} 的合并方式`}
                              disabled={busy !== ""}
                              onChange={(event) =>
                                setMergeMethods((previous) => ({
                                  ...previous,
                                  [pull.number]: normalizeMergeMethod(event.target.value),
                                }))
                              }
                              style={mergeSelectStyle}
                              value={mergeMethods[pull.number] ?? "merge"}
                            >
                              <option value="merge">merge</option>
                              <option value="squash">squash</option>
                              <option value="rebase">rebase</option>
                            </select>
                            <button
                              className="btn btn-danger btn-sm"
                              disabled={busy !== ""}
                              onClick={() => void submitMerge(pull)}
                              type="button"
                            >
                              <Icon name="pullRequest" size={12} />
                              {busy === `merge:${pull.number}` ? "合并中…" : "合并"}
                            </button>
                          </>
                        ) : null}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {branches.length < 2 ? (
              <p className="section-note">
                <Icon name="branch" size={13} />
                该仓库至少需要两个分支（head 与 base 不同）才能创建 Pull Request。
              </p>
            ) : (
              <form onSubmit={(event) => void submitCreate(event)} style={createFormStyle}>
                <p className="mono-key" style={{ gridColumn: "1 / -1" }}>
                  新建 PULL REQUEST
                </p>
                <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                  <span className="mono-key">标题</span>
                  <input
                    aria-label="Pull Request 标题"
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="PR 标题"
                    style={inputStyle}
                    value={title}
                  />
                </label>
                <label style={fieldStyle}>
                  <span className="mono-key">head</span>
                  <select
                    aria-label="head 分支"
                    disabled={busy !== ""}
                    onChange={(event) => setHead(event.target.value)}
                    style={selectStyle}
                    value={head}
                  >
                    {branches.map((branch) => (
                      <option key={branch.name} value={branch.name}>
                        {branch.name}
                        {branch.protected ? " · protected" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span className="mono-key">base</span>
                  <select
                    aria-label="base 分支"
                    disabled={busy !== ""}
                    onChange={(event) => setBase(event.target.value)}
                    style={selectStyle}
                    value={base}
                  >
                    {branches.map((branch) => (
                      <option key={branch.name} value={branch.name}>
                        {branch.name}
                        {branch.protected ? " · protected" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                  <span className="mono-key">说明</span>
                  <textarea
                    aria-label="Pull Request 说明"
                    onChange={(event) => setBody(event.target.value)}
                    placeholder="可选：说明这次变更的目的、范围与验证方式"
                    style={textareaStyle}
                    value={body}
                  />
                </label>
                <div style={formActionsStyle}>
                  <button className="btn btn-primary btn-sm" disabled={createDisabled} type="submit">
                    <Icon name="plus" size={14} />
                    {busy === "create" ? "创建中…" : "创建 PR"}
                  </button>
                  <span className="section-note">
                    把 {head || "head"} 合入 {base || "base"}，创建后自动刷新 open 列表。
                  </span>
                </div>
              </form>
            )}
          </>
        ) : null}

        <p className="section-note">
          <Icon name="gitCommit" size={12} />
          只读取 open 状态的 Pull Request；合并操作会先弹出浏览器确认。
        </p>
      </div>
    </section>
  );
}

"use client";

import { useActor } from "@/lib/use-actor";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  createLocalBranch,
  deleteLocalBranch,
  fetchLocalBranches,
  fetchLocalRepos,
  fetchLocalTags,
  fetchLocalTree,
  importLocalRepo,
  type ApiLocalRepo,
  type ApiTag,
  type ApiTreeEntry,
} from "@/lib/local-git-api";

type LoadState = "idle" | "loading" | "error";

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

const rowStyle = {
  display: "flex",
  gap: "8px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const treeStyle = {
  listStyle: "none",
  padding: 0,
  margin: 0,
  display: "flex",
  flexDirection: "column",
  gap: "2px",
} as const;

const entryStyle = {
  display: "flex",
  gap: "10px",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "4px 0",
  borderBottom: "1px solid rgba(245, 242, 234, 0.06)",
} as const;

const mutedStyle = { color: "rgba(245, 242, 234, 0.55)", fontSize: "12px" } as const;
const errorStyle = { color: "#D48B80" } as const;
const inputStyle = {
  padding: "6px 10px",
  borderRadius: "6px",
  border: "1px solid rgba(245, 242, 234, 0.18)",
  background: "transparent",
  color: "inherit",
  minWidth: "160px",
} as const;

function parentPath(value: string): string {
  const index = value.lastIndexOf("/");
  return index <= 0 ? "" : value.slice(0, index);
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function RepoTree() {
  const actor = useActor();
  const [repos, setRepos] = useState<ApiLocalRepo[]>([]);
  const [repo, setRepo] = useState("");
  const [branches, setBranches] = useState<string[]>([]);
  const [branch, setBranch] = useState("");
  const [path, setPath] = useState("");
  const [entries, setEntries] = useState<ApiTreeEntry[]>([]);
  const [tags, setTags] = useState<ApiTag[]>([]);
  const [newBranch, setNewBranch] = useState("");
  const [importName, setImportName] = useState("");
  const [importSource, setImportSource] = useState("");
  const [importNotice, setImportNotice] = useState("");
  const [status, setStatus] = useState<LoadState>("idle");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requestRef = useRef(0);

  const loadTree = useCallback(
    async (repoName: string, ref: string, nextPath: string) => {
      const request = requestRef.current + 1;
      requestRef.current = request;
      setStatus("loading");
      setError("");
      try {
        const next = await fetchLocalTree(actor, repoName, ref, nextPath);
        if (requestRef.current !== request) {
          return;
        }
        setEntries(next);
        setPath(nextPath);
        setStatus("idle");
      } catch (loadError) {
        if (requestRef.current !== request) {
          return;
        }
        setStatus("error");
        setError(errorMessage(loadError, "读取文件树失败"));
      }
    },
    [actor],
  );

  const selectRepo = useCallback(
    async (repoName: string) => {
      if (!actor) {
        return;
      }
      const request = requestRef.current + 1;
      requestRef.current = request;
      setRepo(repoName);
      setBranches([]);
      setBranch("");
      setEntries([]);
      setTags([]);
      setPath("");
      setError("");
      setStatus("loading");
      try {
        const [nextBranches, nextTags] = await Promise.all([
          fetchLocalBranches(actor, repoName),
          fetchLocalTags(actor, repoName),
        ]);
        if (requestRef.current !== request) {
          return;
        }
        setBranches(nextBranches);
        setTags(nextTags);
        const nextBranch = nextBranches.includes("main") ? "main" : nextBranches[0] ?? "";
        setBranch(nextBranch);
        if (nextBranch) {
          const tree = await fetchLocalTree(actor, repoName, nextBranch, "");
          if (requestRef.current !== request) {
            return;
          }
          setEntries(tree);
        }
        setStatus("idle");
      } catch (loadError) {
        if (requestRef.current !== request) {
          return;
        }
        setStatus("error");
        setError(errorMessage(loadError, "读取仓库失败"));
      }
    },
    [actor],
  );

  useEffect(() => {
    if (!actor) {
      return;
    }
    let cancelled = false;
    fetchLocalRepos(actor)
      .then((next) => {
        if (!cancelled) {
          setRepos(next);
        }
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setStatus("error");
          setError(errorMessage(loadError, "读取本地仓库失败"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [actor]);

  async function handleCreateBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newBranch.trim();
    if (!repo || !name || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createLocalBranch(actor, repo, name, branch || "HEAD");
      const nextBranches = await fetchLocalBranches(actor, repo);
      setBranches(nextBranches);
      setNewBranch("");
      setBranch(name);
      await loadTree(repo, name, "");
    } catch (createError) {
      setError(errorMessage(createError, "创建分支失败"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteBranch() {
    if (!repo || !branch || busy) {
      return;
    }
    if (!window.confirm(`删除分支 ${branch}？`)) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await deleteLocalBranch(actor, repo, branch);
      const nextBranches = await fetchLocalBranches(actor, repo);
      setBranches(nextBranches);
      const nextBranch = nextBranches.includes("main") ? "main" : nextBranches[0] ?? "";
      setBranch(nextBranch);
      setEntries([]);
      setPath("");
      if (nextBranch) {
        await loadTree(repo, nextBranch, "");
      }
    } catch (deleteError) {
      setError(errorMessage(deleteError, "删除分支失败"));
    } finally {
      setBusy(false);
    }
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = importName.trim();
    const source = importSource.trim();
    if (!name || !source || busy) {
      return;
    }
    if (!window.confirm(`从 ${source} 导入为 ${name}？`)) {
      return;
    }
    setBusy(true);
    setError("");
    setImportNotice("");
    try {
      const imported = await importLocalRepo(actor, name, source);
      setImportName("");
      setImportSource("");
      setImportNotice(
        `已导入 ${imported.name}（${imported.branches.length} 分支，${imported.tags.length} 标签）。`,
      );
      const nextRepos = await fetchLocalRepos(actor);
      setRepos(nextRepos);
      await selectRepo(imported.name);
    } catch (importError) {
      setError(errorMessage(importError, "导入仓库失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="repo-tree-title">
      <header style={headingStyle}>
        <p className="section-kicker">DUOBAO · TREE</p>
        <h2 id="repo-tree-title">文件与分支</h2>
      </header>
      <div style={panelBodyStyle}>
        {!actor ? (
          <p style={mutedStyle}>设置 NEXT_PUBLIC_TIANXUAN_ACTOR 后可浏览仓库。</p>
        ) : (
          <>
            <div style={rowStyle} aria-label="本地仓库列表">
              {repos.map((name) => (
                <button
                  key={name}
                  className={`btn btn-ghost btn-sm${repo === name ? " is-active" : ""}`}
                  onClick={() => void selectRepo(name)}
                  type="button"
                >
                  {name}
                </button>
              ))}
              {repos.length === 0 ? <span style={mutedStyle}>没有本地仓库</span> : null}
            </div>

            <form onSubmit={handleImport} style={rowStyle} aria-label="导入仓库">
              <input
                aria-label="导入仓库名"
                value={importName}
                onChange={(event) => setImportName(event.target.value)}
                placeholder="仓库名，例如 app.git"
                style={inputStyle}
              />
              <input
                aria-label="导入来源"
                value={importSource}
                onChange={(event) => setImportSource(event.target.value)}
                placeholder="https://… 或本机绝对路径"
                style={inputStyle}
              />
              <button
                className="btn btn-ghost btn-sm"
                disabled={busy || !importName.trim() || !importSource.trim()}
                type="submit"
              >
                导入
              </button>
            </form>
            {importNotice ? <p style={mutedStyle}>{importNotice}</p> : null}

            {repo ? (
              <div style={rowStyle}>
                <label style={rowStyle}>
                  分支
                  <select
                    aria-label="选择分支"
                    value={branch}
                    onChange={(event) => {
                      const next = event.target.value;
                      setBranch(next);
                      void loadTree(repo, next, "");
                    }}
                    style={inputStyle}
                  >
                    {branches.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <form onSubmit={handleCreateBranch} style={rowStyle}>
                  <input
                    aria-label="新分支名"
                    value={newBranch}
                    onChange={(event) => setNewBranch(event.target.value)}
                    placeholder="新分支名"
                    style={inputStyle}
                  />
                  <button className="btn btn-ghost btn-sm" disabled={busy || !newBranch.trim()} type="submit">
                    新建
                  </button>
                </form>
                <button className="btn btn-ghost btn-sm" disabled={busy || !branch} onClick={() => void handleDeleteBranch()} type="button">
                  删除当前分支
                </button>
              </div>
            ) : null}

            {path ? (
              <div style={rowStyle}>
                <button className="btn btn-ghost btn-sm" onClick={() => void loadTree(repo, branch, parentPath(path))} type="button">
                  上一级
                </button>
                <span style={mutedStyle}>{path}</span>
              </div>
            ) : null}

            {status === "loading" ? <p style={mutedStyle}>加载中…</p> : null}
            {status === "error" ? <p style={errorStyle}>{error}</p> : null}
            {status !== "error" ? (
              <ul style={treeStyle} aria-label="文件树">
                {entries.map((entry) => (
                  <li key={entry.path} style={entryStyle}>
                    {entry.type === "tree" ? (
                      <button className="btn btn-ghost btn-sm" onClick={() => void loadTree(repo, branch, entry.path)} type="button">
                        📁 {entry.name}
                      </button>
                    ) : (
                      <span>{entry.name}</span>
                    )}
                    <span style={mutedStyle}>
                      {entry.type === "tree" ? "目录" : entry.size === null ? "文件" : `${entry.size} B`}
                    </span>
                  </li>
                ))}
                {entries.length === 0 && status !== "loading" ? (
                  <li style={mutedStyle}>空目录，或仓库还没有提交</li>
                ) : null}
              </ul>
            ) : null}

            {tags.length > 0 ? (
              <div style={rowStyle}>
                <strong style={mutedStyle}>标签</strong>
                {tags.map((tag) => (
                  <span key={tag.name} style={mutedStyle}>
                    {tag.name} · {tag.sha.slice(0, 7)}
                  </span>
                ))}
              </div>
            ) : null}

            {error && status !== "error" ? <p style={errorStyle}>{error}</p> : null}
          </>
        )}
      </div>
    </section>
  );
}

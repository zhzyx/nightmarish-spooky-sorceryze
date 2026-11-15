"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";
import {
  createLocalBranch,
  createLocalTag,
  deleteLocalBranch,
  deleteLocalTag,
  fetchLocalBranches,
  fetchLocalRepos,
  fetchBlame,
  fetchLocalTags,
  fetchLocalTree,
  importLocalRepo,
  searchLocalRepo,
  type ApiBlameLine,
  type ApiCodeHit,
  type ApiLocalRepo,
  type ApiTag,
  type ApiTreeEntry,
} from "@/lib/local-git-api";
import { useActor } from "@/lib/use-actor";

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
  const { t } = useI18n();
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
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ApiCodeHit[] | null>(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [blamePath, setBlamePath] = useState("");
  const [blameLines, setBlameLines] = useState<ApiBlameLine[] | null>(null);
  const [blameBusy, setBlameBusy] = useState(false);
  const [blameError, setBlameError] = useState("");
  const [tagName, setTagName] = useState("");
  const [tagNotice, setTagNotice] = useState("");
  const [tagBusy, setTagBusy] = useState(false);
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
        setError(errorMessage(loadError, t("repos.loadTreeError")));
      }
    },
    [actor, t],
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
      setSearchResults(null);
      setSearchError("");
      setBlamePath("");
      setBlameLines(null);
      setBlameError("");
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
        setError(errorMessage(loadError, t("repos.loadRepoError")));
      }
    },
    [actor, t],
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
          setError(errorMessage(loadError, t("repos.loadReposError")));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [actor, t]);

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
      setError(errorMessage(createError, t("repos.createBranchError")));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteBranch() {
    if (!repo || !branch || busy) {
      return;
    }
    if (!window.confirm(`${t("repos.deleteConfirm")}: ${branch}`)) {
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
      setError(errorMessage(deleteError, t("repos.deleteBranchError")));
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
    if (!window.confirm(`${t("repos.importAria")}: ${source} -> ${name}`)) {
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
        `${t("repos.imported")} ${imported.name} · ${imported.branches.length} ${t("repos.branches")} · ${imported.tags.length} ${t("repos.tagsLabel")}`,
      );
      const nextRepos = await fetchLocalRepos(actor);
      setRepos(nextRepos);
      await selectRepo(imported.name);
    } catch (importError) {
      setError(errorMessage(importError, t("repos.importError")));
    } finally {
      setBusy(false);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = searchQuery.trim();
    if (!actor || !repo || !query || searchBusy) {
      return;
    }
    setSearchBusy(true);
    setSearchError("");
    try {
      setSearchResults(await searchLocalRepo(actor, repo, query, branch || "HEAD"));
    } catch (searchErr) {
      setSearchResults(null);
      setSearchError(errorMessage(searchErr, t("repos.searchError")));
    } finally {
      setSearchBusy(false);
    }
  }

  async function handleCreateTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = tagName.trim();
    if (!actor || !repo || !value || tagBusy) {
      return;
    }
    setTagBusy(true);
    setTagNotice("");
    setError("");
    try {
      const created = await createLocalTag(actor, repo, value, branch || "HEAD");
      setTagName("");
      setTags(await fetchLocalTags(actor, repo));
      setTagNotice(formatMessage(t("repos.tagCreated"), { name: created }));
    } catch (tagError) {
      setError(errorMessage(tagError, t("repos.tagError")));
    } finally {
      setTagBusy(false);
    }
  }

  async function handleDeleteTag(name: string) {
    if (!actor || !repo || tagBusy) {
      return;
    }
    if (!window.confirm(`${t("repos.deleteTag")}: ${name}`)) {
      return;
    }
    setTagBusy(true);
    setTagNotice("");
    setError("");
    try {
      await deleteLocalTag(actor, repo, name);
      setTags(await fetchLocalTags(actor, repo));
      setTagNotice(formatMessage(t("repos.tagDeleted"), { name }));
    } catch (tagError) {
      setError(errorMessage(tagError, t("repos.tagError")));
    } finally {
      setTagBusy(false);
    }
  }

  async function loadBlame(path: string) {
    if (!actor || !repo || blameBusy) {
      return;
    }
    setBlameBusy(true);
    setBlamePath(path);
    setBlameError("");
    try {
      setBlameLines(await fetchBlame(actor, repo, branch || "HEAD", path));
    } catch (blameErr) {
      setBlameLines(null);
      setBlameError(errorMessage(blameErr, t("repos.blameError")));
    } finally {
      setBlameBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="repo-tree-title">
      <header style={headingStyle}>
        <p className="section-kicker">DUOBAO · TREE</p>
        <h2 id="repo-tree-title">{t("repos.treeTitle")}</h2>
      </header>
      <div style={panelBodyStyle}>
        {!actor ? (
          <p style={mutedStyle}>{t("repos.treeHint")}</p>
        ) : (
          <>
            <div style={rowStyle} aria-label={t("repos.repoListAria")}>
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
              {repos.length === 0 ? <span style={mutedStyle}>{t("repos.noRepos")}</span> : null}
            </div>

            <form onSubmit={handleImport} style={rowStyle} aria-label={t("repos.importAria")}>
              <input
                aria-label={t("repos.importNameAria")}
                value={importName}
                onChange={(event) => setImportName(event.target.value)}
                placeholder={t("repos.importName")}
                style={inputStyle}
              />
              <input
                aria-label={t("repos.importSource")}
                value={importSource}
                onChange={(event) => setImportSource(event.target.value)}
                placeholder={t("repos.importSource")}
                style={inputStyle}
              />
              <button
                className="btn btn-ghost btn-sm"
                disabled={busy || !importName.trim() || !importSource.trim()}
                type="submit"
              >
                {t("repos.import")}
              </button>
            </form>
            {importNotice ? <p style={mutedStyle}>{importNotice}</p> : null}

            {repo ? (
              <form onSubmit={handleSearch} style={rowStyle} aria-label={t("repos.searchAria")}>
                <input
                  aria-label={t("repos.searchAria")}
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder={t("repos.searchPlaceholder")}
                  style={inputStyle}
                />
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={searchBusy || !searchQuery.trim()}
                  type="submit"
                >
                  {t("repos.search")}
                </button>
                {searchResults !== null ? (
                  <span style={mutedStyle}>
                    {formatMessage(t("repos.searchResults"), { count: searchResults.length })}
                  </span>
                ) : null}
              </form>
            ) : null}
            {searchError ? <p style={errorStyle}>{searchError}</p> : null}
            {blamePath ? (
              <div aria-label={formatMessage(t("repos.blameAria"), { path: blamePath })}>
                <p className="mono-key">
                  {t("repos.blameTitle")} · {blamePath}
                  {blameBusy ? ` · ${t("repos.loading")}` : ""}
                </p>
                {blameError ? <p style={errorStyle}>{blameError}</p> : null}
                {blameLines ? (
                  <ul style={treeStyle}>
                    {blameLines.map((line) => (
                      <li key={`${line.sha}:${line.line}`} style={entryStyle}>
                        <span className="mono-key">{line.line}</span>
                        <span style={mutedStyle}>
                          {line.sha.slice(0, 7)} · {line.author} · {line.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
            {searchResults !== null ? (
              <ul style={treeStyle} aria-label={t("repos.searchAria")}>
                {searchResults.length === 0 ? (
                  <li style={mutedStyle}>{t("repos.searchEmpty")}</li>
                ) : (
                  searchResults.map((hit) => (
                    <li key={`${hit.path}:${hit.line}`} style={entryStyle}>
                      <span className="mono-key">
                        {hit.path}:{hit.line}
                      </span>
                      <span style={mutedStyle}>{hit.text}</span>
                    </li>
                  ))
                )}
              </ul>
            ) : null}

            {repo ? (
              <div style={rowStyle}>
                <label style={rowStyle}>
                  {t("repos.branch")}
                  <select
                    aria-label={t("repos.selectBranch")}
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
                    aria-label={t("repos.newBranch")}
                    value={newBranch}
                    onChange={(event) => setNewBranch(event.target.value)}
                    placeholder={t("repos.newBranch")}
                    style={inputStyle}
                  />
                  <button className="btn btn-ghost btn-sm" disabled={busy || !newBranch.trim()} type="submit">
                    {t("repos.create")}
                  </button>
                </form>
                <button className="btn btn-ghost btn-sm" disabled={busy || !branch} onClick={() => void handleDeleteBranch()} type="button">
                  {t("repos.deleteBranch")}
                </button>
              </div>
            ) : null}

            {path ? (
              <div style={rowStyle}>
                <button className="btn btn-ghost btn-sm" onClick={() => void loadTree(repo, branch, parentPath(path))} type="button">
                  {t("repos.up")}
                </button>
                <span style={mutedStyle}>{path}</span>
              </div>
            ) : null}

            {status === "loading" ? <p style={mutedStyle}>{t("repos.loading")}</p> : null}
            {status === "error" ? <p style={errorStyle}>{error}</p> : null}
            {status !== "error" ? (
              <ul style={treeStyle} aria-label={t("repos.treeAria")}>
                {entries.map((entry) => (
                  <li key={entry.path} style={entryStyle}>
                    {entry.type === "tree" ? (
                      <button className="btn btn-ghost btn-sm" onClick={() => void loadTree(repo, branch, entry.path)} type="button">
                        📁 {entry.name}
                      </button>
                    ) : (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => void loadBlame(entry.path)}
                        type="button"
                      >
                        {entry.name}
                      </button>
                    )}
                    <span style={mutedStyle}>
                      {entry.type === "tree"
                        ? t("repos.directory")
                        : entry.size === null
                          ? t("repos.file")
                          : `${entry.size} B`}
                    </span>
                  </li>
                ))}
                {entries.length === 0 && status !== "loading" ? (
                  <li style={mutedStyle}>{t("repos.emptyTree")}</li>
                ) : null}
              </ul>
            ) : null}

            {repo ? (
              <div style={rowStyle}>
                <strong style={mutedStyle}>{t("repos.tagsLabel")}</strong>
                <form onSubmit={handleCreateTag} style={rowStyle}>
                  <input
                    aria-label={t("repos.newTag")}
                    value={tagName}
                    onChange={(event) => setTagName(event.target.value)}
                    placeholder={t("repos.newTag")}
                    style={inputStyle}
                  />
                  <button className="btn btn-ghost btn-sm" disabled={tagBusy || !tagName.trim()} type="submit">
                    {t("repos.createTag")}
                  </button>
                </form>
                {tags.map((tag) => (
                  <span key={tag.name} style={rowStyle}>
                    <span style={mutedStyle}>
                      {tag.name} · {tag.sha.slice(0, 7)}
                    </span>
                    <button
                      aria-label={t("repos.deleteTag")}
                      className="btn btn-ghost btn-sm"
                      disabled={tagBusy}
                      onClick={() => void handleDeleteTag(tag.name)}
                      type="button"
                    >
                      ×
                    </button>
                  </span>
                ))}
                {tagNotice ? <span style={mutedStyle}>{tagNotice}</span> : null}
              </div>
            ) : null}

            {error && status !== "error" ? <p style={errorStyle}>{error}</p> : null}
          </>
        )}
      </div>
    </section>
  );
}

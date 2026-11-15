"use client";

import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";
import { useActor } from "@/lib/use-actor";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import {
  createPull,
  createRelease,
  createReview,
  fetchBranches,
  fetchPulls,
  fetchReleases,
  fetchReviews,
  mergePull,
  updateRelease,
  type ApiBranch,
  type ApiPull,
  type ApiRelease,
  type ApiReview,
  type MergeMethod,
  type PullState,
  type ReviewEvent,
} from "@/lib/gitea-pulls-api";

type LoadState = "idle" | "loading" | "ready" | "error";

const OWNER_STORAGE_KEY = "tianxuan.pulls.owner";
const REPO_STORAGE_KEY = "tianxuan.pulls.repo";
const PAGE_SIZE = 20;

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

const pagerStyle = {
  display: "flex",
  gap: "8px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

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

function approvedCount(reviews: ApiReview[] | undefined): number {
  return (reviews ?? []).filter((review) => review.state.toUpperCase() === "APPROVED").length;
}

export function RepoPulls() {
  const actor = useActor();
  const { t } = useI18n();
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
  const [reviewsByPull, setReviewsByPull] = useState<Record<number, ApiReview[]>>({});
  const [releases, setReleases] = useState<ApiRelease[]>([]);
  const [releaseTag, setReleaseTag] = useState("");
  const [releaseName, setReleaseName] = useState("");
  const [releaseBody, setReleaseBody] = useState("");
  const [releaseDraft, setReleaseDraft] = useState(false);
  const [releasePre, setReleasePre] = useState(false);
  const [releaseBusy, setReleaseBusy] = useState(false);
  const [releaseError, setReleaseError] = useState("");
  const [pullState, setPullState] = useState<PullState>("open");
  const [page, setPage] = useState(1);
  const requestRef = useRef(0);

  useEffect(() => {
    if (!actor) {
      return;
    }
    setOwner(storedValue(OWNER_STORAGE_KEY));
    setRepo(storedValue(REPO_STORAGE_KEY));
  }, [actor]);

  const load = useCallback(
    async (ownerValue: string, repoValue: string, stateValue: PullState = "open", pageValue = 1) => {
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
      setReleases([]);
      setReviewsByPull({});
      setPullState(stateValue);
      setPage(pageValue);
      setActiveOwner(nextOwner);
      setActiveRepo(nextRepo);
      rememberValue(OWNER_STORAGE_KEY, nextOwner);
      rememberValue(REPO_STORAGE_KEY, nextRepo);
      try {
        const [nextBranches, nextPulls, nextReleases] = await Promise.all([
          fetchBranches(actor, nextOwner, nextRepo),
          fetchPulls(actor, nextOwner, nextRepo, stateValue, pageValue, PAGE_SIZE),
          fetchReleases(actor, nextOwner, nextRepo).catch(() => [] as ApiRelease[]),
        ]);
        if (requestRef.current !== request) {
          return;
        }
        const nextBase = nextBranches.some((branch) => branch.name === "main")
          ? "main"
          : nextBranches[0]?.name ?? "main";
        setBranches(nextBranches);
        setPulls(nextPulls);
        setReleases(nextReleases);
        const reviewEntries = await Promise.all(
          nextPulls.map(async (pull) => {
            try {
              return [pull.number, await fetchReviews(actor, nextOwner, nextRepo, pull.number)] as const;
            } catch {
              return [pull.number, []] as const;
            }
          }),
        );
        if (requestRef.current !== request) {
          return;
        }
        setReviewsByPull(Object.fromEntries(reviewEntries) as Record<number, ApiReview[]>);
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
          `${formatMessage(t("pulls.loadError"), { owner: nextOwner, repo: nextRepo })}${
            error instanceof Error ? ` (${error.message})` : ""
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
      setActionError(t("pulls.needOwnerRepo"));
      return;
    }
    void load(owner, repo, pullState, 1);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!actor || busy || loadState !== "ready") {
      return;
    }
    const nextTitle = title.trim();
    if (!nextTitle) {
      setActionError(t("pulls.needTitle"));
      return;
    }
    if (!head || !base) {
      setActionError(t("pulls.needBranches"));
      return;
    }
    if (head === base) {
      setActionError(t("pulls.sameBranch"));
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
      await load(activeOwner, activeRepo, pullState, page);
      setNotice(formatMessage(t("pulls.created"), { number: created.number, title: created.title || nextTitle }));
    } catch {
      setActionError(t("pulls.createError"));
    } finally {
      setBusy("");
    }
  }

  async function submitMerge(pull: ApiPull) {
    if (!actor || busy || loadState !== "ready") {
      return;
    }
    const method = mergeMethods[pull.number] ?? "merge";
    if (!window.confirm(formatMessage(t("pulls.mergeConfirm"), { method, number: pull.number, title: pull.title }))) {
      return;
    }
    setBusy(`merge:${pull.number}`);
    setActionError("");
    setNotice("");
    try {
      const result = await mergePull(actor, activeOwner, activeRepo, pull.number, method);
      await load(activeOwner, activeRepo, pullState, page);
      setNotice(
        result.merged
          ? `${formatMessage(t("pulls.mergeSuccess"), { number: pull.number, method })}${
              result.sha ? formatMessage(t("pulls.mergeSha"), { sha: result.sha.slice(0, 7) }) : ""
            }`
          : formatMessage(t("pulls.mergeNoResult"), { number: pull.number }),
      );
    } catch {
      setActionError(formatMessage(t("pulls.mergeError"), { number: pull.number }));
    } finally {
      setBusy("");
    }
  }

  async function submitRelease(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const tagName = releaseTag.trim();
    if (!actor || !activeOwner || !activeRepo || !tagName || releaseBusy) {
      return;
    }
    setReleaseBusy(true);
    setReleaseError("");
    setActionError("");
    setNotice("");
    try {
      const created = await createRelease(actor, activeOwner, activeRepo, {
        tag_name: tagName,
        name: releaseName.trim(),
        body: releaseBody.trim(),
        draft: releaseDraft,
        prerelease: releasePre,
      });
      setReleaseTag("");
      setReleaseName("");
      setReleaseBody("");
      setReleaseDraft(false);
      setReleasePre(false);
      setReleases(await fetchReleases(actor, activeOwner, activeRepo));
      setNotice(formatMessage(t("pulls.releaseCreated"), { tag: created.tag_name }));
    } catch {
      setReleaseError(t("pulls.releaseError"));
    } finally {
      setReleaseBusy(false);
    }
  }

  async function editRelease(release: ApiRelease) {
    if (!actor || !activeOwner || !activeRepo || releaseBusy) {
      return;
    }
    const name = window.prompt(t("pulls.releaseNamePrompt"), release.name);
    if (name === null) {
      return;
    }
    const body = window.prompt(t("pulls.releaseBodyPrompt"), release.body);
    if (body === null) {
      return;
    }
    setReleaseBusy(true);
    setReleaseError("");
    setNotice("");
    try {
      await updateRelease(actor, activeOwner, activeRepo, release.id, { name, body });
      setReleases(await fetchReleases(actor, activeOwner, activeRepo));
      setNotice(formatMessage(t("pulls.releaseUpdated"), { tag: release.tag_name }));
    } catch {
      setReleaseError(t("pulls.releaseUpdateError"));
    } finally {
      setReleaseBusy(false);
    }
  }

  async function submitReview(pull: ApiPull, event: ReviewEvent) {
    if (!actor || busy || loadState !== "ready") {
      return;
    }
    let reviewBody = "";
    if (event !== "APPROVED") {
      const input = window.prompt(
        formatMessage(t(event === "REQUEST_CHANGES" ? "pulls.reviewChangesPrompt" : "pulls.reviewCommentPrompt"), {
          number: pull.number,
        }),
      );
      if (input === null) {
        return;
      }
      reviewBody = input.trim();
    }
    setBusy(`review:${pull.number}`);
    setActionError("");
    setNotice("");
    try {
      await createReview(actor, activeOwner, activeRepo, pull.number, event, reviewBody);
      const nextReviews = await fetchReviews(actor, activeOwner, activeRepo, pull.number);
      setReviewsByPull((previous) => ({ ...previous, [pull.number]: nextReviews }));
      setNotice(formatMessage(t("pulls.reviewNotice"), { number: pull.number, event }));
    } catch {
      setActionError(formatMessage(t("pulls.reviewError"), { number: pull.number }));
    } finally {
      setBusy("");
    }
  }

  if (!actor) {
    return (
      <section aria-label={t("pulls.title")} className="panel">
        <div className="section-heading" style={headingStyle}>
          <div>
            <p className="section-kicker">DUOBAO · GITEA PULLS</p>
            <h2>{t("pulls.title")}</h2>
          </div>
          <span className="mono-key">{t("pulls.disabled")}</span>
        </div>
        <div style={panelBodyStyle}>
          <p className="section-note">
            <Icon name="lock" size={13} />
            {t("pulls.disabledNote")}
          </p>
        </div>
      </section>
    );
  }

  const summary =
    loadState === "idle"
      ? t("pulls.summaryIdle")
      : loadState === "loading"
        ? t("pulls.summaryLoading")
        : loadState === "error"
          ? t("pulls.summaryError")
          : formatMessage(t("pulls.summary"), { count: pulls.length, state: pullState, page });

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
      aria-label={t("pulls.title")}
      className="panel"
    >
      <div className="section-heading" style={headingStyle}>
        <div>
          <p className="section-kicker">DUOBAO · GITEA PULLS</p>
          <h2>{t("pulls.title")}</h2>
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
              aria-label={t("pulls.ownerAria")}
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
              aria-label={t("pulls.repoAria")}
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
            {t("pulls.load")}
          </button>
        </form>

        <div style={pagerStyle} aria-label={t("pulls.filterAria")}>
          <label style={{ ...fieldStyle, flex: "0 0 auto", minWidth: "120px" }}>
            <span className="mono-key">{t("pulls.stateLabel")}</span>
            <select
              aria-label={t("pulls.stateAria")}
              disabled={loadState === "loading" || busy !== ""}
              onChange={(event) => {
                const next = event.target.value as PullState;
                if (activeOwner && activeRepo && loadState !== "idle") {
                  void load(activeOwner, activeRepo, next, 1);
                } else {
                  setPullState(next);
                  setPage(1);
                }
              }}
              style={selectStyle}
              value={pullState}
            >
              <option value="open">open</option>
              <option value="closed">closed</option>
              <option value="all">all</option>
            </select>
          </label>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page <= 1 || loadState === "loading" || busy !== ""}
            onClick={() => void load(activeOwner, activeRepo, pullState, page - 1)}
            type="button"
          >
            {t("pulls.prev")}
          </button>
          <span className="mono-key">{formatMessage(t("pulls.page"), { page })}</span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={pulls.length < PAGE_SIZE || loadState === "loading" || busy !== ""}
            onClick={() => void load(activeOwner, activeRepo, pullState, page + 1)}
            type="button"
          >
            {t("pulls.next")}
          </button>
        </div>

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
            {t("pulls.idleHint")}
          </p>
        ) : null}

        {loadState === "loading" ? (
          <p className="section-note">
            {formatMessage(t("pulls.loadingHint"), { owner: activeOwner, repo: activeRepo })}
          </p>
        ) : null}

        {loadState === "error" ? (
          <div style={errorRowStyle}>
            <p className="section-note" role="alert" style={errorTextStyle}>
              <Icon name="alert" size={13} /> {loadError}
            </p>
            <button className="btn btn-ghost btn-sm" onClick={startLoad} type="button">
              <Icon name="history" size={12} />
              {t("pulls.retry")}
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
                  {formatMessage(t("pulls.empty"), { state: pullState })}
                </p>
              ) : (
                <div
                  aria-label={t("pulls.listAria")}
                  className="reading-list live-list"
                  style={{ padding: 0 }}
                >
                  {pulls.map((pull) => (
                    <div className="reading-item" key={pull.number} style={pullItemStyle}>
                      <span className="reading-index">#{pull.number}</span>
                      <span className="reading-copy">
                        <strong title={pull.title}>{pull.title || t("pulls.untitled")}</strong>
                        <span>
                          {pull.head || "?"} → {pull.base || "?"}
                        </span>
                      </span>
                      <span className="kind-tag">{pull.state || "open"}</span>
                      <span style={pullActionsStyle}>
                        <span className="kind-tag">
                          {formatMessage(t("pulls.approvals"), { approved: approvedCount(reviewsByPull[pull.number]), total: (reviewsByPull[pull.number] ?? []).length })}
                        </span>
                        {pull.state === "open" ? (
                          <>
                            <button
                              className="btn btn-ghost btn-sm"
                              disabled={busy !== ""}
                              onClick={() => void submitReview(pull, "APPROVED")}
                              type="button"
                            >
                              {busy === `review:${pull.number}` ? t("pulls.submitting") : t("pulls.approve")}
                            </button>
                            <button
                              className="btn btn-ghost btn-sm"
                              disabled={busy !== ""}
                              onClick={() => void submitReview(pull, "REQUEST_CHANGES")}
                              type="button"
                            >
                              {t("pulls.requestChanges")}
                            </button>
                            <button
                              className="btn btn-ghost btn-sm"
                              disabled={busy !== ""}
                              onClick={() => void submitReview(pull, "COMMENT")}
                              type="button"
                            >
                              {t("pulls.comment")}
                            </button>
                          </>
                        ) : null}
                        {pull.html_url ? (
                          <a
                            className="btn btn-ghost btn-sm"
                            href={pull.html_url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            <Icon name="link" size={12} />
                            {t("pulls.openInGitea")}
                          </a>
                        ) : null}
                        {pull.state === "open" ? (
                          <>
                            <select
                              aria-label={formatMessage(t("pulls.mergeMethodAria"), { number: pull.number })}
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
                              {busy === `merge:${pull.number}` ? t("pulls.merging") : t("pulls.merge")}
                            </button>
                          </>
                        ) : null}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <p className="mono-key" style={{ marginBottom: "6px" }}>
                {t("pulls.releasesTitle")} · {activeOwner}/{activeRepo}
              </p>
              <form onSubmit={submitRelease} style={loadFormStyle} aria-label={t("pulls.newRelease")}>
                <input
                  aria-label={t("pulls.releaseTagAria")}
                  placeholder={t("pulls.releaseTag")}
                  value={releaseTag}
                  onChange={(event) => setReleaseTag(event.target.value)}
                  style={inputStyle}
                />
                <input
                  aria-label={t("pulls.releaseName")}
                  placeholder={t("pulls.releaseName")}
                  value={releaseName}
                  onChange={(event) => setReleaseName(event.target.value)}
                  style={inputStyle}
                />
                <input
                  aria-label={t("pulls.releaseBody")}
                  placeholder={t("pulls.releaseBody")}
                  value={releaseBody}
                  onChange={(event) => setReleaseBody(event.target.value)}
                  style={inputStyle}
                />
                <label style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={releaseDraft}
                    onChange={(event) => setReleaseDraft(event.target.checked)}
                  />
                  {t("pulls.releaseDraftLabel")}
                </label>
                <label style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={releasePre}
                    onChange={(event) => setReleasePre(event.target.checked)}
                  />
                  {t("pulls.releasePreLabel")}
                </label>
                <button className="btn btn-ghost btn-sm" disabled={releaseBusy || !releaseTag.trim()} type="submit">
                  {t("pulls.createRelease")}
                </button>
              </form>
              {releaseError ? <p className="section-note" role="alert" style={errorTextStyle}>{releaseError}</p> : null}
              {releases.length === 0 ? (
                <p className="section-note">{t("pulls.releasesEmpty")}</p>
              ) : (
                <div className="reading-list live-list" style={{ padding: 0 }}>
                  {releases.map((release) => (
                    <div className="reading-item" key={release.id ?? release.tag_name}>
                      <span className="reading-index">{release.tag_name}</span>
                      <span className="reading-copy">
                        <strong>{release.name || release.tag_name}</strong>
                        <span>
                          {release.draft ? t("pulls.releaseDraft") : ""}
                          {release.draft && release.prerelease ? " · " : ""}
                          {release.prerelease ? t("pulls.releasePre") : ""}
                          {release.created_at ? ` · ${release.created_at.slice(0, 10)}` : ""}
                        </span>
                      </span>
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={releaseBusy}
                        onClick={() => void editRelease(release)}
                        type="button"
                      >
                        {t("pulls.editRelease")}
                      </button>
                      {release.html_url ? (
                        <a className="btn btn-ghost btn-sm" href={release.html_url} rel="noreferrer" target="_blank">
                          <Icon name="link" size={12} />
                          {t("pulls.openInGitea")}
                        </a>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {branches.length < 2 ? (
              <p className="section-note">
                <Icon name="branch" size={13} />
                {t("pulls.branchHint")}
              </p>
            ) : (
              <form onSubmit={(event) => void submitCreate(event)} style={createFormStyle}>
                <p className="mono-key" style={{ gridColumn: "1 / -1" }}>
                  {t("pulls.newTitle")}
                </p>
                <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                  <span className="mono-key">{t("pulls.titleLabel")}</span>
                  <input
                    aria-label={t("pulls.titleAria")}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder={t("pulls.titlePlaceholder")}
                    style={inputStyle}
                    value={title}
                  />
                </label>
                <label style={fieldStyle}>
                  <span className="mono-key">head</span>
                  <select
                    aria-label={t("pulls.headAria")}
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
                    aria-label={t("pulls.baseAria")}
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
                  <span className="mono-key">{t("pulls.bodyLabel")}</span>
                  <textarea
                    aria-label={t("pulls.bodyAria")}
                    onChange={(event) => setBody(event.target.value)}
                    placeholder={t("pulls.bodyPlaceholder")}
                    style={textareaStyle}
                    value={body}
                  />
                </label>
                <div style={formActionsStyle}>
                  <button className="btn btn-primary btn-sm" disabled={createDisabled} type="submit">
                    <Icon name="plus" size={14} />
                    {busy === "create" ? t("pulls.creating") : t("pulls.createPr")}
                  </button>
                  <span className="section-note">
                    {formatMessage(t("pulls.createNote"), { head: head || "head", base: base || "base" })}
                  </span>
                </div>
              </form>
            )}
          </>
        ) : null}

        <p className="section-note">
          <Icon name="gitCommit" size={12} />
          {t("pulls.readNote")}
        </p>
      </div>
    </section>
  );
}

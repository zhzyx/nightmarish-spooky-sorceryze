"use client";

import { useActor } from "@/lib/use-actor";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import {
  addComment,
  fetchComments,
  resolveComment,
  type ApiComment,
} from "@/lib/api";
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";

type LoadState = "loading" | "ready" | "error";

export interface DocCommentsProps {
  docId: string;
}

const panelBodyStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "14px",
  padding: "0 26px 22px",
} as const;

const commentListStyle = { padding: 0 } as const;

const commentItemStyle = {
  gridTemplateColumns: "minmax(0, 1fr) auto",
  alignItems: "flex-start",
} as const;

const commentMainStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "7px",
  minWidth: 0,
} as const;

const commentMetaStyle = {
  display: "flex",
  gap: "9px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const commentAuthorStyle = {
  color: "rgba(245, 242, 234, 0.78)",
  fontSize: "10.5px",
  fontWeight: 500,
} as const;

const commentTimeStyle = { fontSize: "8px" } as const;

const commentBodyStyle = {
  margin: 0,
  color: "rgba(245, 242, 234, 0.66)",
  fontSize: "11px",
  lineHeight: 1.75,
  overflowWrap: "anywhere",
  whiteSpace: "pre-wrap",
} as const;

const commentFormStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "9px",
  padding: "13px 14px",
  border: "1px solid var(--line)",
  borderRadius: "13px",
  background: "rgba(245, 242, 234, 0.025)",
} as const;

const commentInputStyle = {
  width: "100%",
  minHeight: "76px",
  padding: "9px 11px",
  resize: "vertical",
  border: "1px solid rgba(245, 242, 234, 0.075)",
  borderRadius: "9px",
  background: "rgba(8, 11, 14, 0.45)",
  color: "rgba(245, 242, 234, 0.8)",
  fontSize: "11px",
  lineHeight: 1.7,
} as const;

const commentFormFootStyle = {
  display: "flex",
  gap: "12px",
  alignItems: "center",
  justifyContent: "space-between",
} as const;

function shortAuthor(author: string, fallback: string): string {
  const trimmed = author.trim();
  if (!trimmed) {
    return fallback;
  }
  return trimmed.length > 12 ? `${trimmed.slice(0, 11)}…` : trimmed;
}

function formatTimestamp(value: string, fallback: string): string {
  const normalized = value.replace("T", " ").replace(/\.\d+/, "");
  const match = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})/.exec(normalized);
  return match ? `${match[1]} ${match[2]}` : value || fallback;
}

export function DocComments({ docId }: DocCommentsProps) {
  const actor = useActor();
  const { t } = useI18n();
  const [comments, setComments] = useState<ApiComment[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);
  const [resolvingId, setResolvingId] = useState("");

  const loadComments = useCallback(async () => {
    if (!actor) {
      return;
    }
    setLoadState("loading");
    setLoadError("");
    try {
      const next = await fetchComments(docId, actor);
      setComments(next);
      setLoadState("ready");
    } catch {
      setLoadState("error");
      setLoadError(t("comments.errorLoad"));
    }
  }, [actor, docId]);

  useEffect(() => {
    void loadComments();
  }, [loadComments]);

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = draft.trim();
    if (!actor || !body || posting) {
      return;
    }
    setPosting(true);
    setActionError("");
    try {
      const created = await addComment(docId, actor, body);
      setComments((current) => [...current, created]);
      setDraft("");
    } catch {
      setActionError(t("comments.errorSubmit"));
    } finally {
      setPosting(false);
    }
  }

  async function toggleResolved(comment: ApiComment) {
    if (!actor || resolvingId) {
      return;
    }
    const nextResolved = !comment.resolved;
    setResolvingId(comment.id);
    setActionError("");
    try {
      const updated = await resolveComment(comment.id, actor, nextResolved);
      setComments((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch {
      setActionError(
        nextResolved ? t("comments.errorResolve") : t("comments.errorReopen"),
      );
    } finally {
      setResolvingId("");
    }
  }

  if (!actor) {
    return (
      <section aria-label={t("comments.title")} className="panel">
        <header className="panel-head">
          <div>
            <p className="section-kicker">WENQU · COMMENTS</p>
            <h2>{t("comments.title")}</h2>
          </div>
          <span className="mono-key">{t("comments.disabled")}</span>
        </header>
        <div style={panelBodyStyle}>
          <p className="section-note" style={{ fontSize: "10.5px", lineHeight: 1.6 }}>
            <Icon name="lock" size={14} />
            {t("comments.disabledNote")}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section aria-busy={loadState === "loading"} aria-label={t("comments.title")} className="panel">
      <header className="panel-head">
        <div>
          <p className="section-kicker">WENQU · COMMENTS</p>
          <h2>{t("comments.title")}</h2>
        </div>
        <span className="mono-key">
          {loadState === "loading"
            ? t("comments.summaryLoading")
            : loadState === "error"
              ? t("comments.summaryError")
              : formatMessage(t("comments.summary"), { count: comments.length })}
        </span>
      </header>

      <div style={panelBodyStyle}>
        {loadState === "loading" ? <p className="section-note">{t("comments.loading")}</p> : null}

        {loadState === "error" ? (
          <div
            style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}
          >
            <p className="section-note" role="alert" style={{ color: "#D48B80" }}>
              <Icon name="alert" size={13} /> {loadError}
            </p>
            <button className="text-link" onClick={() => void loadComments()} type="button">
              <Icon name="history" size={13} />
              {t("comments.reload")}
            </button>
          </div>
        ) : null}

        {loadState === "ready" && comments.length === 0 ? (
          <p className="section-note">{t("comments.empty")}</p>
        ) : null}

        {comments.length > 0 ? (
          <ul className="reading-list" style={commentListStyle}>
            {comments.map((comment) => (
              <li className="reading-item" key={comment.id} style={commentItemStyle}>
                <div style={commentMainStyle}>
                  <div style={commentMetaStyle}>
                    <strong style={commentAuthorStyle} title={comment.author}>
                      {shortAuthor(comment.author, t("comments.anonymous"))}
                    </strong>
                    <time
                      className="section-note"
                      dateTime={comment.created_at}
                      style={commentTimeStyle}
                    >
                      {formatTimestamp(comment.created_at, t("comments.unknownTime"))}
                    </time>
                    {comment.resolved ? <span className="kind-tag">{t("comments.resolved")}</span> : null}
                  </div>
                  <p style={commentBodyStyle}>{comment.body}</p>
                </div>
                <button
                  aria-label={
                    comment.resolved
                      ? formatMessage(t("comments.reopenAria"), {
                          author: shortAuthor(comment.author, t("comments.anonymous")),
                        })
                      : formatMessage(t("comments.resolveAria"), {
                          author: shortAuthor(comment.author, t("comments.anonymous")),
                        })
                  }
                  className="btn btn-ghost btn-sm"
                  disabled={resolvingId !== ""}
                  onClick={() => void toggleResolved(comment)}
                  type="button"
                >
                  <Icon name={comment.resolved ? "history" : "check"} size={12} />
                  {resolvingId === comment.id
                    ? t("comments.updating")
                    : comment.resolved
                      ? t("comments.reopen")
                      : t("comments.resolve")}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {actionError ? (
          <p className="section-note" role="alert" style={{ color: "#D48B80" }}>
            <Icon name="alert" size={13} /> {actionError}
          </p>
        ) : null}

        <form onSubmit={(event) => void submitComment(event)} style={commentFormStyle}>
          <label className="sr-only" htmlFor="doc-comment-input">
            {t("comments.inputLabel")}
          </label>
          <textarea
            id="doc-comment-input"
            onChange={(event) => setDraft(event.target.value)}
            placeholder={t("comments.placeholder")}
            rows={3}
            style={commentInputStyle}
            value={draft}
          />
          <div style={commentFormFootStyle}>
            <span className="section-note">
              {draft.trim() ? formatMessage(t("comments.charCount"), { count: draft.trim().length }) : t("comments.plainText")}
            </span>
            <button
              className="btn btn-primary btn-sm"
              disabled={posting || !draft.trim()}
              type="submit"
            >
              <Icon name="comment" size={14} />
              {posting ? t("comments.submitting") : t("comments.add")}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

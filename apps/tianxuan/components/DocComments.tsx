"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import {
  addComment,
  fetchComments,
  resolveComment,
  type ApiComment,
} from "@/lib/api";

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

function shortAuthor(author: string): string {
  const trimmed = author.trim();
  if (!trimmed) {
    return "匿名";
  }
  return trimmed.length > 12 ? `${trimmed.slice(0, 11)}…` : trimmed;
}

function formatTimestamp(value: string): string {
  const normalized = value.replace("T", " ").replace(/\.\d+/, "");
  const match = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})/.exec(normalized);
  return match ? `${match[1]} ${match[2]}` : value || "未知时间";
}

export function DocComments({ docId }: DocCommentsProps) {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR ?? "";
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
      setLoadError("无法读取评论，请确认后端服务已启动且当前账号有权限。");
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
      setActionError("评论提交失败，请稍后重试。");
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
        nextResolved ? "标记评论为已解决失败，请稍后重试。" : "重新打开评论失败，请稍后重试。",
      );
    } finally {
      setResolvingId("");
    }
  }

  if (!actor) {
    return (
      <section aria-label="文档评论" className="panel">
        <header className="panel-head">
          <div>
            <p className="section-kicker">文曲 · COMMENTS</p>
            <h2>文档评论</h2>
          </div>
          <span className="mono-key">未启用</span>
        </header>
        <div style={panelBodyStyle}>
          <p className="section-note" style={{ fontSize: "10.5px", lineHeight: 1.6 }}>
            <Icon name="lock" size={14} />
            未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，评论面板已禁用，不会请求评论接口。
          </p>
        </div>
      </section>
    );
  }

  return (
    <section aria-busy={loadState === "loading"} aria-label="文档评论" className="panel">
      <header className="panel-head">
        <div>
          <p className="section-kicker">文曲 · COMMENTS</p>
          <h2>文档评论</h2>
        </div>
        <span className="mono-key">
          {loadState === "loading"
            ? "读取中…"
            : loadState === "error"
              ? "读取失败"
              : `${comments.length} 条评论`}
        </span>
      </header>

      <div style={panelBodyStyle}>
        {loadState === "loading" ? <p className="section-note">正在读取评论…</p> : null}

        {loadState === "error" ? (
          <div
            style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}
          >
            <p className="section-note" role="alert" style={{ color: "#D48B80" }}>
              <Icon name="alert" size={13} /> {loadError}
            </p>
            <button className="text-link" onClick={() => void loadComments()} type="button">
              <Icon name="history" size={13} />
              重新加载
            </button>
          </div>
        ) : null}

        {loadState === "ready" && comments.length === 0 ? (
          <p className="section-note">还没有评论，写下第一条建议或问题。</p>
        ) : null}

        {comments.length > 0 ? (
          <ul className="reading-list" style={commentListStyle}>
            {comments.map((comment) => (
              <li className="reading-item" key={comment.id} style={commentItemStyle}>
                <div style={commentMainStyle}>
                  <div style={commentMetaStyle}>
                    <strong style={commentAuthorStyle} title={comment.author}>
                      {shortAuthor(comment.author)}
                    </strong>
                    <time
                      className="section-note"
                      dateTime={comment.created_at}
                      style={commentTimeStyle}
                    >
                      {formatTimestamp(comment.created_at)}
                    </time>
                    {comment.resolved ? <span className="kind-tag">已解决</span> : null}
                  </div>
                  <p style={commentBodyStyle}>{comment.body}</p>
                </div>
                <button
                  aria-label={
                    comment.resolved
                      ? `重新打开 ${shortAuthor(comment.author)} 的评论`
                      : `标记 ${shortAuthor(comment.author)} 的评论为已解决`
                  }
                  className="btn btn-ghost btn-sm"
                  disabled={resolvingId !== ""}
                  onClick={() => void toggleResolved(comment)}
                  type="button"
                >
                  <Icon name={comment.resolved ? "history" : "check"} size={12} />
                  {resolvingId === comment.id
                    ? "更新中…"
                    : comment.resolved
                      ? "重新打开"
                      : "标记已解决"}
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
            评论内容
          </label>
          <textarea
            id="doc-comment-input"
            onChange={(event) => setDraft(event.target.value)}
            placeholder="写下评论，例如：请补充验收标准…"
            rows={3}
            style={commentInputStyle}
            value={draft}
          />
          <div style={commentFormFootStyle}>
            <span className="section-note">
              {draft.trim() ? `${draft.trim().length} 字` : "纯文本评论"}
            </span>
            <button
              className="btn btn-primary btn-sm"
              disabled={posting || !draft.trim()}
              type="submit"
            >
              <Icon name="comment" size={14} />
              {posting ? "提交中…" : "添加评论"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

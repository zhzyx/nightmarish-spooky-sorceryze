"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import {
  fetchShares,
  setDocVisibility,
  shareDoc,
  unshareDoc,
  type ApiShare,
  type DocVisibility,
  type SharePermission,
} from "@/lib/api";

type LoadState = "loading" | "ready" | "error";

export interface DocSharingProps {
  docId: string;
  initialVisibility?: string;
}

function normalizeVisibility(value: string | undefined): DocVisibility {
  return value === "private" ? "private" : "tenant";
}

function shareDate(value: string): string {
  const date = value.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : value;
}

const panelBodyStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "14px",
  padding: "0 26px 22px",
} as const;

const visibilityRowStyle = {
  display: "flex",
  gap: "18px",
  alignItems: "center",
  justifyContent: "space-between",
  flexWrap: "wrap",
  padding: "12px 14px",
  border: "1px solid var(--line)",
  borderRadius: "13px",
  background: "rgba(245, 242, 234, 0.025)",
} as const;

const visibilityCopyStyle = {
  display: "flex",
  gap: "8px",
  alignItems: "center",
  marginTop: "4px",
  color: "rgba(245, 242, 234, 0.66)",
  fontSize: "10.5px",
  lineHeight: 1.6,
} as const;

const shareFormStyle = {
  display: "flex",
  gap: "8px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const shareInputStyle = { flex: "1 1 180px", width: "auto" } as const;

const shareListStyle = { padding: 0 } as const;

export function DocSharing({ docId, initialVisibility }: DocSharingProps) {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR ?? "";
  const [visibility, setVisibility] = useState<DocVisibility>(() =>
    normalizeVisibility(initialVisibility),
  );
  const [shares, setShares] = useState<ApiShare[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [newUserId, setNewUserId] = useState("");
  const [newPermission, setNewPermission] = useState<SharePermission>("read");

  const loadShares = useCallback(async () => {
    if (!actor) {
      return;
    }
    setLoadState("loading");
    setError("");
    try {
      const next = await fetchShares(docId, actor);
      setShares(next);
      setLoadState("ready");
    } catch {
      setLoadState("error");
      setError("无法读取共享列表，请确认后端服务已启动且当前账号有权限。");
    }
  }, [actor, docId]);

  useEffect(() => {
    void loadShares();
  }, [loadShares]);

  async function toggleVisibility() {
    const next: DocVisibility = visibility === "private" ? "tenant" : "private";
    setBusy("visibility");
    setError("");
    try {
      const updated = await setDocVisibility(docId, actor, next);
      setVisibility(normalizeVisibility(updated.visibility));
    } catch {
      setError("可见性更新失败，请稍后重试。");
    } finally {
      setBusy("");
    }
  }

  async function addShare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const userId = newUserId.trim();
    if (!userId) {
      return;
    }
    setBusy("share");
    setError("");
    try {
      await shareDoc(docId, actor, userId, newPermission);
      setNewUserId("");
      await loadShares();
    } catch {
      setError("添加共享失败，请检查用户 ID 是否属于当前租户。");
    } finally {
      setBusy("");
    }
  }

  async function removeShare(userId: string) {
    setBusy(`remove:${userId}`);
    setError("");
    try {
      await unshareDoc(docId, actor, userId);
      await loadShares();
    } catch {
      setError(`移除 ${userId} 的共享失败，请稍后重试。`);
    } finally {
      setBusy("");
    }
  }

  if (!actor) {
    return (
      <section aria-label="文档共享" className="panel">
        <header className="panel-head">
          <div>
            <p className="section-kicker">文曲 · SHARING</p>
            <h2>文档共享</h2>
          </div>
          <span className="mono-key">未启用</span>
        </header>
        <div style={panelBodyStyle}>
          <p style={visibilityCopyStyle}>
            <Icon name="lock" size={14} />
            未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，共享面板已禁用，不会请求共享接口。
          </p>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="文档共享" className="panel">
      <header className="panel-head">
        <div>
          <p className="section-kicker">文曲 · SHARING</p>
          <h2>文档共享</h2>
        </div>
        <span className="mono-key">
          {loadState === "loading" ? "读取中…" : `${shares.length} 位协作者`}
        </span>
      </header>

      <div style={panelBodyStyle}>
        <div style={visibilityRowStyle}>
          <div>
            <p className="mono-key">当前可见性</p>
            <p style={visibilityCopyStyle}>
              <Icon name={visibility === "private" ? "lock" : "users"} size={14} />
              {visibility === "private"
                ? "私有 · 仅创建者与获共享成员可见"
                : "租户内可见 · 同租户成员均可阅读"}
            </p>
          </div>
          <button
            className="btn btn-ghost btn-sm"
            disabled={busy === "visibility"}
            onClick={() => void toggleVisibility()}
            type="button"
          >
            <Icon name={visibility === "private" ? "users" : "lock"} size={14} />
            {busy === "visibility"
              ? "更新中…"
              : visibility === "private"
                ? "设为租户可见"
                : "设为私有"}
          </button>
        </div>

        {error ? (
          <p className="section-note" role="alert" style={{ color: "#D48B80" }}>
            <Icon name="alert" size={13} /> {error}
          </p>
        ) : null}

        <div>
          <p className="mono-key" style={{ marginBottom: "6px" }}>
            已共享成员
          </p>
          {loadState === "loading" ? <p className="section-note">正在读取共享列表…</p> : null}
          {loadState === "error" ? (
            <button className="text-link" onClick={() => void loadShares()} type="button">
              <Icon name="history" size={13} />
              重新加载
            </button>
          ) : null}
          {loadState === "ready" && shares.length === 0 ? (
            <p className="section-note">还没有共享成员，可在下方按用户 ID 添加。</p>
          ) : null}
          {shares.length > 0 ? (
            <ul className="reading-list" style={shareListStyle}>
              {shares.map((share) => (
                <li
                  className="reading-item"
                  key={share.user_id}
                  style={{ gridTemplateColumns: "minmax(0, 1fr) auto" }}
                >
                  <span className="reading-copy">
                    <strong>{share.user_id}</strong>
                    <span>
                      {share.permission === "write" ? "可编辑" : "只读"} ·{" "}
                      {shareDate(share.created_at)}
                    </span>
                  </span>
                  <button
                    aria-label={`移除 ${share.user_id} 的共享`}
                    className="btn btn-danger btn-sm"
                    disabled={busy === `remove:${share.user_id}`}
                    onClick={() => void removeShare(share.user_id)}
                    type="button"
                  >
                    <Icon name="close" size={12} />
                    {busy === `remove:${share.user_id}` ? "移除中…" : "移除"}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <form onSubmit={(event) => void addShare(event)} style={shareFormStyle}>
          <label className="field-search" style={shareInputStyle}>
            <Icon name="users" size={15} />
            <input
              aria-label="共享用户 ID"
              onChange={(event) => setNewUserId(event.target.value)}
              placeholder="用户 ID，例如 usr_1001"
              value={newUserId}
            />
          </label>
          <label className="select-field">
            <span className="sr-only">共享权限</span>
            <select
              aria-label="共享权限"
              onChange={(event) =>
                setNewPermission(event.target.value === "write" ? "write" : "read")
              }
              value={newPermission}
            >
              <option value="read">只读</option>
              <option value="write">可编辑</option>
            </select>
            <Icon name="chevronDown" size={13} />
          </label>
          <button
            className="btn btn-primary btn-sm"
            disabled={busy === "share" || !newUserId.trim()}
            type="submit"
          >
            <Icon name="plus" size={14} />
            {busy === "share" ? "添加中…" : "添加共享"}
          </button>
        </form>

        <p className="section-note">
          <Icon name="shield" size={12} /> 仅文档创建者或管理员可以修改可见性与共享名单。
        </p>
      </div>
    </section>
  );
}

"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import {
  createIdentityLink,
  deleteIdentityLink,
  fetchIdentityLinks,
  fetchUsers,
  rebindIdentityLink,
  type ApiIdentityLink,
  type ApiMember,
} from "@/lib/api";

const PROVIDERS = ["tianshu", "github", "oidc", "static"];

const fieldStyle: CSSProperties = {
  background: "rgba(245, 242, 234, 0.06)",
  border: "1px solid rgba(245, 242, 234, 0.14)",
  borderRadius: 8,
  color: "inherit",
  font: "inherit",
  fontSize: 12,
  minWidth: 0,
  padding: "9px 10px",
};

export function IdentityBindings() {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR;
  const [links, setLinks] = useState<ApiIdentityLink[]>([]);
  const [users, setUsers] = useState<ApiMember[]>([]);
  const [provider, setProvider] = useState("tianshu");
  const [subject, setSubject] = useState("");
  const [userId, setUserId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [removing, setRemoving] = useState("");
  const [targets, setTargets] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    if (!actor) {
      return;
    }
    const [nextLinks, nextUsers] = await Promise.all([
      fetchIdentityLinks(actor),
      fetchUsers(actor),
    ]);
    setLinks(nextLinks);
    setUsers(nextUsers);
    setTargets((current) => {
      const next = { ...current };
      for (const link of nextLinks) {
        next[link.id] = next[link.id] ?? link.user_id;
      }
      return next;
    });
    setUserId((current) => current || nextUsers[0]?.id || "");
  }, [actor]);

  useEffect(() => {
    if (!actor) {
      return;
    }
    load()
      .then(() => setError(""))
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "加载失败"));
  }, [actor, load]);

  async function bind() {
    if (!actor || !subject.trim() || !userId) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await createIdentityLink(actor, provider, subject.trim(), userId);
      setSubject("");
      await load();
      setNotice("已绑定外部身份");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "绑定失败");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!actor) {
      return;
    }
    setRemoving(id);
    setError("");
    try {
      await deleteIdentityLink(actor, id);
      await load();
      setNotice("已解绑外部身份");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "解绑失败");
    } finally {
      setRemoving("");
    }
  }

  async function rebind(id: string) {
    if (!actor) {
      return;
    }
    const target = targets[id];
    if (!target) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await rebindIdentityLink(actor, id, target);
      await load();
      setNotice("已改绑外部身份");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "改绑失败");
    } finally {
      setBusy(false);
    }
  }

  function userLabel(id: string): string {
    const user = users.find((item) => item.id === id);
    return user ? `${user.name} · ${user.email}` : id;
  }

  return (
    <section className="panel" aria-labelledby="identity-bindings-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker">IDENTITY · ADAPTERS</p>
          <h2 id="identity-bindings-title">外部身份绑定</h2>
        </div>
        <span className="section-note">{links.length} 个绑定</span>
      </div>
      {!actor ? (
        <p className="section-note" style={{ padding: "0 26px 22px" }}>
          未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，无法读取身份绑定。
        </p>
      ) : (
        <>
          <div className="reading-list live-list">
            {links.length === 0 ? (
              <p className="section-note" style={{ padding: "12px 16px" }}>
                还没有外部身份绑定。先添加绑定，再让天枢/GitHub/OIDC 用对应身份换取会话。
              </p>
            ) : (
              links.map((link) => (
                <div className="reading-item" key={link.id}>
                  <span className="reading-index">{link.provider.slice(0, 1)}</span>
                  <span className="reading-copy">
                    <strong>{link.subject}</strong>
                    <span>
                      {link.provider} · {userLabel(link.user_id)}
                    </span>
                  </span>
                  <select
                    aria-label={`改绑 ${link.subject}`}
                    style={{ ...fieldStyle, maxWidth: 220, padding: "6px 8px" }}
                    value={targets[link.id] ?? link.user_id}
                    onChange={(event) =>
                      setTargets((current) => ({ ...current, [link.id]: event.target.value }))
                    }
                  >
                    {users.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.name} · {user.email}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={busy || (targets[link.id] ?? link.user_id) === link.user_id}
                    onClick={() => rebind(link.id)}
                  >
                    改绑
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={removing === link.id}
                    onClick={() => remove(link.id)}
                  >
                    {removing === link.id ? "解绑中…" : "解绑"}
                  </button>
                </div>
              ))
            )}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "140px minmax(0, 1fr) minmax(0, 1fr) auto",
              gap: "10px",
              alignItems: "center",
              padding: "0 26px 22px",
            }}
          >
            <select
              aria-label="身份提供方"
              style={fieldStyle}
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              {PROVIDERS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <input
              aria-label="外部 subject"
              style={fieldStyle}
              placeholder="外部 subject，如 GitHub 用户 ID"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
            />
            <select
              aria-label="绑定到成员"
              style={fieldStyle}
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
            >
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name} · {user.email}
                </option>
              ))}
            </select>
            <button className="btn btn-primary" type="button" disabled={busy || !subject.trim()} onClick={bind}>
              {busy ? "绑定中…" : "绑定身份"}
            </button>
          </div>
        </>
      )}
      {notice ? <p className="section-note" style={{ padding: "0 26px 18px" }}>{notice}</p> : null}
      {error ? <p className="section-note" style={{ padding: "0 26px 18px" }}>{error}</p> : null}
    </section>
  );
}

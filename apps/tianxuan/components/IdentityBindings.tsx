"use client";

import { useActor } from "@/lib/use-actor";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import {
  createIdentityLink,
  deleteIdentityLink,
  fetchIdentityEvents,
  fetchIdentityLinks,
  fetchUsers,
  rebindIdentityLink,
  type ApiIdentityEvent,
  type ApiIdentityLink,
  type ApiMember,
} from "@/lib/api";
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";

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
  const actor = useActor();
  const { t, locale } = useI18n();
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
  const [events, setEvents] = useState<ApiIdentityEvent[]>([]);
  const [eventFilter, setEventFilter] = useState("all");

  const load = useCallback(async () => {
    if (!actor) {
      return;
    }
    const [nextLinks, nextUsers, nextEvents] = await Promise.all([
      fetchIdentityLinks(actor),
      fetchUsers(actor),
      fetchIdentityEvents(actor),
    ]);
    setLinks(nextLinks);
    setUsers(nextUsers);
    setEvents(nextEvents);
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
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : t("identity.errorLoad")));
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
      setNotice(t("identity.noticeLinked"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("identity.errorBind"));
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
      setNotice(t("identity.noticeUnlinked"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("identity.errorUnbind"));
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
      setNotice(t("identity.noticeRebound"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("identity.errorRebind"));
    } finally {
      setBusy(false);
    }
  }

  function userLabel(id: string): string {
    const user = users.find((item) => item.id === id);
    return user ? `${user.name} · ${user.email}` : id;
  }

  const filteredEvents =
    eventFilter === "all" ? events : events.filter((event) => event.type === eventFilter);

  return (
    <section className="panel" aria-labelledby="identity-bindings-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker">IDENTITY · ADAPTERS</p>
          <h2 id="identity-bindings-title">{t("identity.title")}</h2>
        </div>
        <span className="section-note">{formatMessage(t("identity.note"), { count: links.length })}</span>
      </div>
      {!actor ? (
        <p className="section-note" style={{ padding: "0 26px 22px" }}>
          {t("identity.disabled")}
        </p>
      ) : (
        <>
          <div className="reading-list live-list">
            {links.length === 0 ? (
              <p className="section-note" style={{ padding: "12px 16px" }}>
                {t("identity.empty")}
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
                    aria-label={formatMessage(t("identity.rebindAria"), { subject: link.subject })}
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
                    {t("identity.rebind")}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={removing === link.id}
                    onClick={() => remove(link.id)}
                  >
                    {removing === link.id ? t("identity.removing") : t("identity.unbind")}
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
              aria-label={t("identity.providerAria")}
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
              aria-label={t("identity.subjectAria")}
              style={fieldStyle}
              placeholder={t("identity.subjectPlaceholder")}
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
            />
            <select
              aria-label={t("identity.userAria")}
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
              {busy ? t("identity.binding") : t("identity.bind")}
            </button>
          </div>
          <div className="reading-list live-list" style={{ marginTop: 8 }}>
            <div
              style={{
                alignItems: "center",
                display: "flex",
                gap: 10,
                padding: "0 16px",
              }}
            >
              <p className="section-kicker" style={{ flex: 1 }}>
                RECENT · IDENTITY EVENTS
              </p>
              <select
                aria-label={t("identity.filterAria")}
                value={eventFilter}
                onChange={(event) => setEventFilter(event.target.value)}
                style={{ ...fieldStyle, padding: "4px 8px", width: 150 }}
              >
                <option value="all">{t("identity.allEvents")}</option>
                <option value="identity.linked">{t("identity.linked")}</option>
                <option value="identity.rebound">{t("identity.rebound")}</option>
                <option value="identity.unlinked">{t("identity.unlinked")}</option>
              </select>
            </div>
            {filteredEvents.length === 0 ? (
              <p className="section-note" style={{ padding: "8px 16px" }}>
                {t("identity.noEvents")}
              </p>
            ) : (
              filteredEvents.slice(0, 8).map((event) => (
                <div className="reading-item" key={`${event.created_at}-${event.type}-${event.target}`}>
                  <span className="reading-index">·</span>
                  <span className="reading-copy">
                    <strong>{event.type.replace("identity.", "")}</strong>
                    <span>
                      {String(event.payload.subject ?? "")} · {new Date(event.created_at).toLocaleString(locale === "en" ? "en-US" : "zh-CN")}
                    </span>
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      )}
      {notice ? <p className="section-note" style={{ padding: "0 26px 18px" }}>{notice}</p> : null}
      {error ? <p className="section-note" style={{ padding: "0 26px 18px" }}>{error}</p> : null}
    </section>
  );
}

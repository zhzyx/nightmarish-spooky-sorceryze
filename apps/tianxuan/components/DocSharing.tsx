"use client";

import { useActor } from "@/lib/use-actor";

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
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";

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
  const actor = useActor();
  const { t } = useI18n();
  const [visibility, setVisibility] = useState<DocVisibility>(() =>
    normalizeVisibility(initialVisibility),
  );
  const [shares, setShares] = useState<ApiShare[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [newUserId, setNewUserId] = useState("");
  const [newPermission, setNewPermission] = useState<SharePermission>("read");
  const [expiryDays, setExpiryDays] = useState("");

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
      setError(t("sharing.errorLoad"));
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
      setError(t("sharing.errorVisibility"));
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
    const days = expiryDays.trim() === "" ? null : Number(expiryDays);
    if (days !== null && (!Number.isInteger(days) || days <= 0)) {
      setError(t("sharing.expiryInvalid"));
      return;
    }
    const expiresAt =
      days === null ? undefined : new Date(Date.now() + days * 86_400_000).toISOString();
    setBusy("share");
    setError("");
    try {
      await shareDoc(docId, actor, userId, newPermission, expiresAt);
      setNewUserId("");
      setExpiryDays("");
      await loadShares();
    } catch {
      setError(t("sharing.errorAdd"));
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
      setError(formatMessage(t("sharing.errorRemove"), { id: userId }));
    } finally {
      setBusy("");
    }
  }

  if (!actor) {
    return (
      <section aria-label={t("sharing.title")} className="panel">
        <header className="panel-head">
          <div>
            <p className="section-kicker">WENQU · SHARING</p>
            <h2>{t("sharing.title")}</h2>
          </div>
          <span className="mono-key">{t("sharing.disabled")}</span>
        </header>
        <div style={panelBodyStyle}>
          <p style={visibilityCopyStyle}>
            <Icon name="lock" size={14} />
            {t("sharing.disabledNote")}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section aria-label={t("sharing.title")} className="panel">
      <header className="panel-head">
        <div>
          <p className="section-kicker">WENQU · SHARING</p>
          <h2>{t("sharing.title")}</h2>
        </div>
        <span className="mono-key">
          {loadState === "loading" ? t("sharing.summaryLoading") : formatMessage(t("sharing.summary"), { count: shares.length })}
        </span>
      </header>

      <div style={panelBodyStyle}>
        <div style={visibilityRowStyle}>
          <div>
            <p className="mono-key">{t("sharing.visibility")}</p>
            <p style={visibilityCopyStyle}>
              <Icon name={visibility === "private" ? "lock" : "users"} size={14} />
              {visibility === "private" ? t("sharing.private") : t("sharing.tenant")}
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
              ? t("sharing.updating")
              : visibility === "private"
                ? t("sharing.setTenant")
                : t("sharing.setPrivate")}
          </button>
        </div>

        {error ? (
          <p className="section-note" role="alert" style={{ color: "#D48B80" }}>
            <Icon name="alert" size={13} /> {error}
          </p>
        ) : null}

        <div>
          <p className="mono-key" style={{ marginBottom: "6px" }}>
            {t("sharing.members")}
          </p>
          {loadState === "loading" ? <p className="section-note">{t("sharing.loadingList")}</p> : null}
          {loadState === "error" ? (
            <button className="text-link" onClick={() => void loadShares()} type="button">
              <Icon name="history" size={13} />
              {t("sharing.reload")}
            </button>
          ) : null}
          {loadState === "ready" && shares.length === 0 ? (
            <p className="section-note">{t("sharing.empty")}</p>
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
                      {share.permission === "write" ? t("sharing.write") : t("sharing.read")} ·{" "}
                      {shareDate(share.created_at)}
                      {share.expires_at
                        ? ` · ${formatMessage(t("sharing.expiresAt"), { date: share.expires_at.slice(0, 10) })}`
                        : ""}
                    </span>
                  </span>
                  <button
                    aria-label={formatMessage(t("sharing.removeAria"), { id: share.user_id })}
                    className="btn btn-danger btn-sm"
                    disabled={busy === `remove:${share.user_id}`}
                    onClick={() => void removeShare(share.user_id)}
                    type="button"
                  >
                    <Icon name="close" size={12} />
                    {busy === `remove:${share.user_id}` ? t("sharing.removing") : t("sharing.remove")}
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
              aria-label={t("sharing.userAria")}
              onChange={(event) => setNewUserId(event.target.value)}
              placeholder={t("sharing.userPlaceholder")}
              value={newUserId}
            />
          </label>
          <label className="field-search" style={{ flex: "0 1 130px" }}>
            <Icon name="clock" size={15} />
            <input
              aria-label={t("sharing.expiryLabel")}
              min={1}
              onChange={(event) => setExpiryDays(event.target.value)}
              placeholder={t("sharing.expiryPlaceholder")}
              style={{ width: "100%" }}
              type="number"
              value={expiryDays}
            />
          </label>
          <label className="select-field">
            <span className="sr-only">{t("sharing.permission")}</span>
            <select
              aria-label={t("sharing.permission")}
              onChange={(event) =>
                setNewPermission(event.target.value === "write" ? "write" : "read")
              }
              value={newPermission}
            >
              <option value="read">{t("sharing.read")}</option>
              <option value="write">{t("sharing.write")}</option>
            </select>
            <Icon name="chevronDown" size={13} />
          </label>
          <button
            className="btn btn-primary btn-sm"
            disabled={busy === "share" || !newUserId.trim()}
            type="submit"
          >
            <Icon name="plus" size={14} />
            {busy === "share" ? t("sharing.adding") : t("sharing.add")}
          </button>
        </form>

        <p className="section-note">
          <Icon name="shield" size={12} /> {t("sharing.note")}
        </p>
      </div>
    </section>
  );
}

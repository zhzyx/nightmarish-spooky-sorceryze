"use client";

import { useActor } from "@/lib/use-actor";

import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchDocDiff, fetchVersions, MergeConflict, restoreDocVersion, type ApiVersion } from "@/lib/api";
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";

type LoadState = "loading" | "ready" | "error";
type DiffState = "idle" | "loading" | "ready" | "error";

export interface DocVersionsProps {
  docId: string;
}

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

const versionListStyle = { padding: 0 } as const;

const versionItemStyle = {
  gridTemplateColumns: "48px minmax(0, 1fr) auto",
} as const;

const controlsStyle = {
  display: "flex",
  gap: "9px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const arrowStyle = { fontSize: "10px" } as const;

const errorRowStyle = {
  display: "flex",
  gap: "12px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const errorTextStyle = { color: "#D48B80" } as const;

const diffStyle = {
  maxHeight: "360px",
  margin: 0,
  padding: "12px 14px",
  overflow: "auto",
  border: "1px solid var(--line)",
  borderRadius: "11px",
  background: "rgba(8, 11, 14, 0.45)",
  color: "rgba(245, 242, 234, 0.74)",
  fontFamily:
    "var(--font-mono), ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
  fontSize: "10px",
  lineHeight: 1.65,
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
  tabSize: 2,
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

export function DocVersions({ docId }: DocVersionsProps) {
  const actor = useActor();
  const { t } = useI18n();
  const [versions, setVersions] = useState<ApiVersion[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [fromVersion, setFromVersion] = useState<number | null>(null);
  const [toVersion, setToVersion] = useState<number | null>(null);
  const [diff, setDiff] = useState("");
  const [diffState, setDiffState] = useState<DiffState>("idle");
  const [diffError, setDiffError] = useState("");

  const [restoring, setRestoring] = useState(false);
  const [restoreNote, setRestoreNote] = useState("");

  const resetDiff = useCallback(() => {
    setDiff("");
    setDiffState("idle");
    setDiffError("");
  }, []);

  const loadVersions = useCallback(async () => {
    if (!actor) {
      return;
    }
    setLoadState("loading");
    setLoadError("");
    resetDiff();
    try {
      const fetched = await fetchVersions(docId, actor);
      const next = [...fetched].sort((a, b) => a.version - b.version);
      setVersions(next);
      if (next.length === 0) {
        setFromVersion(null);
        setToVersion(null);
      } else {
        const latest = next[next.length - 1];
        const previous = next.length > 1 ? next[next.length - 2] : latest;
        setFromVersion(previous.version);
        setToVersion(latest.version);
      }
      setLoadState("ready");
    } catch {
      setLoadState("error");
      setLoadError(t("versions.errorLoad"));
    }
  }, [actor, docId, resetDiff]);

  useEffect(() => {
    void loadVersions();
  }, [loadVersions]);

  async function restore(sourceVersion: number, expectedVersion: number) {
    if (!actor || restoring) return;
    const prompt = formatMessage(t("versions.confirmRestore"), { sourceVersion, expectedVersion });
    if (!window.confirm(prompt)) return;
    setRestoring(true);
    setRestoreNote("");
    try {
      const updated = await restoreDocVersion(docId, actor, sourceVersion, expectedVersion);
      window.dispatchEvent(new CustomEvent("tianxuan:doc-updated", { detail: updated }));
      setRestoreNote(formatMessage(t("versions.restored"), { version: updated.version }));
      await loadVersions();
    } catch (error) {
      if (error instanceof MergeConflict) {
        setRestoreNote(t("versions.restoreConflict"));
        await loadVersions();
      } else {
        setRestoreNote(t("versions.restoreError"));
      }
    } finally {
      setRestoring(false);
    }
  }

  async function loadDiff() {
    if (!actor || fromVersion === null || toVersion === null) {
      return;
    }
    setDiffState("loading");
    setDiffError("");
    try {
      const text = await fetchDocDiff(docId, actor, fromVersion, toVersion);
      setDiff(text);
      setDiffState("ready");
    } catch {
      setDiff("");
      setDiffState("error");
      setDiffError(t("versions.errorDiff"));
    }
  }

  if (!actor) {
    return (
      <section aria-label={t("versions.title")} className="panel">
        <div className="section-heading" style={headingStyle}>
          <div>
            <p className="section-kicker">WENQU · VERSIONS</p>
            <h2>{t("versions.title")}</h2>
          </div>
          <span className="mono-key">{t("versions.disabled")}</span>
        </div>
        <div style={panelBodyStyle}>
          <p className="section-note" style={{ fontSize: "10.5px", lineHeight: 1.6 }}>
            <Icon name="lock" size={14} />
            {t("versions.disabledNote")}
          </p>
        </div>
      </section>
    );
  }

  const latestVersion = versions.length > 0 ? versions[versions.length - 1].version : null;

  return (
    <section
      aria-busy={loadState === "loading"}
      aria-label={t("versions.title")}
      className="panel"
    >
      <div className="section-heading" style={headingStyle}>
        <div>
          <p className="section-kicker">WENQU · VERSIONS</p>
          <h2>{t("versions.title")}</h2>
        </div>
        <span className="mono-key">
          {loadState === "loading"
            ? t("versions.summaryLoading")
            : loadState === "error"
              ? t("versions.summaryError")
              : formatMessage(t("versions.summary"), { count: versions.length })}
        </span>
      </div>

      <div style={panelBodyStyle}>
        {restoreNote && <p className="section-note" role="status">{restoreNote}</p>}
        {loadState === "ready" && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={restoring} onClick={() => void loadVersions()}>
            {t("versions.reload")}
          </button>
        )}
        {loadState === "loading" ? <p className="section-note">{t("versions.loading")}</p> : null}

        {loadState === "error" ? (
          <div style={errorRowStyle}>
            <p className="section-note" role="alert" style={errorTextStyle}>
              <Icon name="alert" size={13} /> {loadError}
            </p>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => void loadVersions()}
              type="button"
            >
              <Icon name="history" size={12} />
              {t("versions.reload")}
            </button>
          </div>
        ) : null}

        {loadState === "ready" && versions.length === 0 ? (
          <p className="section-note">{t("versions.empty")}</p>
        ) : null}

        {loadState === "ready" && versions.length > 0 ? (
          <>
            <ul className="reading-list" style={versionListStyle}>
              {versions.map((item) => (
                <li className="reading-item" key={item.version} style={versionItemStyle}>
                  <span className="reading-index">v{item.version}</span>
                  <span className="reading-copy">
                    <strong title={item.author}>{shortAuthor(item.author, t("versions.anonymous"))}</strong>
                    <span>{formatTimestamp(item.created_at, t("versions.unknownTime"))}</span>
                  </span>
                  {item.version === latestVersion ? (
                    <span className="kind-tag">{t("versions.latest")}</span>
                  ) : latestVersion !== null && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={restoring}
                      onClick={() => void restore(item.version, latestVersion)}
                    >
                      {formatMessage(t("versions.restore"), { version: item.version })}
                    </button>
                  )}
                </li>
              ))}
            </ul>

            <div style={controlsStyle}>
              <label className="select-field">
                <span className="mono-key">{t("versions.from")}</span>
                <select
                  aria-label={t("versions.fromAria")}
                  disabled={diffState === "loading"}
                  onChange={(event) => {
                    setFromVersion(Number(event.target.value));
                    resetDiff();
                  }}
                  value={fromVersion ?? ""}
                >
                  {versions.map((item) => (
                    <option key={item.version} value={item.version}>
                      v{item.version}
                    </option>
                  ))}
                </select>
                <Icon name="chevronDown" size={13} />
              </label>
              <span aria-hidden="true" className="mono-key" style={arrowStyle}>
                →
              </span>
              <label className="select-field">
                <span className="mono-key">{t("versions.to")}</span>
                <select
                  aria-label={t("versions.toAria")}
                  disabled={diffState === "loading"}
                  onChange={(event) => {
                    setToVersion(Number(event.target.value));
                    resetDiff();
                  }}
                  value={toVersion ?? ""}
                >
                  {versions.map((item) => (
                    <option key={item.version} value={item.version}>
                      v{item.version}
                    </option>
                  ))}
                </select>
                <Icon name="chevronDown" size={13} />
              </label>
              <button
                className="btn btn-primary btn-sm"
                disabled={diffState === "loading"}
                onClick={() => void loadDiff()}
                type="button"
              >
                <Icon name="code" size={14} />
                {diffState === "loading" ? t("versions.generating") : t("versions.viewDiff")}
              </button>
            </div>

            {diffState === "error" ? (
              <div style={errorRowStyle}>
                <p className="section-note" role="alert" style={errorTextStyle}>
                  <Icon name="alert" size={13} /> {diffError}
                </p>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => void loadDiff()}
                  type="button"
                >
                  <Icon name="history" size={12} />
                  {t("versions.retry")}
                </button>
              </div>
            ) : null}

            {diffState === "ready" ? (
              diff.trim() ? (
                <pre
                  aria-label={formatMessage(t("versions.diffAria"), { from: fromVersion ?? "", to: toVersion ?? "" })}
                  style={diffStyle}
                  tabIndex={0}
                >{diff}</pre>
              ) : (
                <p className="section-note">
                  <Icon name="check" size={12} />{" "}
                  {formatMessage(t("versions.same"), { from: fromVersion ?? "", to: toVersion ?? "" })}
                </p>
              )
            ) : null}

            <p className="section-note">
              <Icon name="gitCommit" size={12} />
              {t("versions.note")}
            </p>
          </>
        ) : null}
      </div>
    </section>
  );
}

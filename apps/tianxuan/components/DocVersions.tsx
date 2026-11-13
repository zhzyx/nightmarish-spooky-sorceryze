"use client";

import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchDocDiff, fetchVersions, type ApiVersion } from "@/lib/api";

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

export function DocVersions({ docId }: DocVersionsProps) {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR ?? "";
  const [versions, setVersions] = useState<ApiVersion[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [fromVersion, setFromVersion] = useState<number | null>(null);
  const [toVersion, setToVersion] = useState<number | null>(null);
  const [diff, setDiff] = useState("");
  const [diffState, setDiffState] = useState<DiffState>("idle");
  const [diffError, setDiffError] = useState("");

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
      setLoadError("无法读取版本历史，请确认后端服务已启动且当前账号有权限。");
    }
  }, [actor, docId, resetDiff]);

  useEffect(() => {
    void loadVersions();
  }, [loadVersions]);

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
      setDiffError("无法生成版本差异，请确认所选版本仍然存在后重试。");
    }
  }

  if (!actor) {
    return (
      <section aria-label="文档版本历史" className="panel">
        <div className="section-heading" style={headingStyle}>
          <div>
            <p className="section-kicker">文曲 · VERSIONS</p>
            <h2>版本历史</h2>
          </div>
          <span className="mono-key">未启用</span>
        </div>
        <div style={panelBodyStyle}>
          <p className="section-note" style={{ fontSize: "10.5px", lineHeight: 1.6 }}>
            <Icon name="lock" size={14} />
            未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，版本历史面板已禁用，不会请求版本接口。
          </p>
        </div>
      </section>
    );
  }

  const latestVersion = versions.length > 0 ? versions[versions.length - 1].version : null;

  return (
    <section
      aria-busy={loadState === "loading"}
      aria-label="文档版本历史"
      className="panel"
    >
      <div className="section-heading" style={headingStyle}>
        <div>
          <p className="section-kicker">文曲 · VERSIONS</p>
          <h2>版本历史</h2>
        </div>
        <span className="mono-key">
          {loadState === "loading"
            ? "读取中…"
            : loadState === "error"
              ? "读取失败"
              : `${versions.length} 个版本`}
        </span>
      </div>

      <div style={panelBodyStyle}>
        {loadState === "loading" ? <p className="section-note">正在读取版本历史…</p> : null}

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
              重新加载
            </button>
          </div>
        ) : null}

        {loadState === "ready" && versions.length === 0 ? (
          <p className="section-note">还没有版本记录，保存文档后会自动生成历史版本。</p>
        ) : null}

        {loadState === "ready" && versions.length > 0 ? (
          <>
            <ul className="reading-list" style={versionListStyle}>
              {versions.map((item) => (
                <li className="reading-item" key={item.version} style={versionItemStyle}>
                  <span className="reading-index">v{item.version}</span>
                  <span className="reading-copy">
                    <strong title={item.author}>{shortAuthor(item.author)}</strong>
                    <span>{formatTimestamp(item.created_at)}</span>
                  </span>
                  {item.version === latestVersion ? (
                    <span className="kind-tag">最新</span>
                  ) : null}
                </li>
              ))}
            </ul>

            <div style={controlsStyle}>
              <label className="select-field">
                <span className="mono-key">自</span>
                <select
                  aria-label="起始版本"
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
                <span className="mono-key">至</span>
                <select
                  aria-label="目标版本"
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
                {diffState === "loading" ? "生成中…" : "查看差异"}
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
                  重试
                </button>
              </div>
            ) : null}

            {diffState === "ready" ? (
              diff.trim() ? (
                <pre
                  aria-label={`v${fromVersion} 与 v${toVersion} 的版本差异`}
                  style={diffStyle}
                  tabIndex={0}
                >{diff}</pre>
              ) : (
                <p className="section-note">
                  <Icon name="check" size={12} /> v{fromVersion} 与 v{toVersion} 内容一致，没有差异。
                </p>
              )
            ) : null}

            <p className="section-note">
              <Icon name="gitCommit" size={12} />
              默认对比最新两个版本；差异以只读统一差异（unified diff）文本展示。
            </p>
          </>
        ) : null}
      </div>
    </section>
  );
}

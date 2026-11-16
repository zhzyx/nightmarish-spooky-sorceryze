"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getToken } from "@/lib/auth";
import { formatMessage, type MessageKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";
import {
  cancelMerge,
  enqueueMerge,
  fetchMergeQueue,
  fetchMergeQueueStatus,
  fetchMergeWorkers,
  type ApiMergeWorker,
  processMergeQueue,
  retryMerge,
  type ApiMergeQueueItem,
  type ApiMergeQueueStatus,
} from "@/lib/merge-queue-api";
import { useActor } from "@/lib/use-actor";

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

const STATUS_KEYS: Record<string, MessageKey> = {
  queued: "queue.statusQueued",
  validating: "queue.statusValidating",
  merged: "queue.statusMerged",
  conflict: "queue.statusConflict",
  rejected: "queue.statusRejected",
  cancelled: "queue.statusCancelled",
};

function evidenceText(item: ApiMergeQueueItem): string {
  const evidence = item.evidence ?? {};
  const error = evidence["error"];
  if (typeof error === "string" && error) {
    return error;
  }
  const sha = evidence["merge_sha"];
  if (typeof sha === "string" && sha) {
    return `merge ${sha.slice(0, 10)}`;
  }
  return "";
}

export function MergeQueuePanel() {
  const actor = useActor();
  const { t } = useI18n();
  const [items, setItems] = useState<ApiMergeQueueItem[]>([]);
  const [status, setStatus] = useState<ApiMergeQueueStatus | null>(null);
  const [workers, setWorkers] = useState<ApiMergeWorker[]>([]);
  const [repo, setRepo] = useState("docs.git");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("main");
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("0");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [live, setLive] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const statusLabel = useCallback(
    (value: string): string => {
      const key = STATUS_KEYS[value];
      return key ? t(key) : value;
    },
    [t],
  );

  const load = useCallback(async () => {
    if (!actor) {
      return;
    }
    const [nextItems, nextStatus, nextWorkers] = await Promise.all([
      fetchMergeQueue(actor),
      fetchMergeQueueStatus(actor),
      fetchMergeWorkers(actor).catch(() => [] as ApiMergeWorker[]),
    ]);
    setItems(nextItems);
    setStatus(nextStatus);
    setWorkers(nextWorkers);
  }, [actor]);

  useEffect(() => {
    if (!actor) {
      return;
    }
    let active = true;
    let poll: number | null = null;
    load().catch(() => undefined);
    const startPolling = () => {
      if (poll !== null) {
        return;
      }
      poll = window.setInterval(() => {
        load()
          .then(() => active && setError(""))
          .catch((cause: unknown) =>
            active && setError(cause instanceof Error ? cause.message : t("queue.loadError")),
          );
      }, 5000);
    };
    const base =
      process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
    const token = getToken();
    const query = token ? `token=${encodeURIComponent(token)}` : `actor=${encodeURIComponent(actor)}`;
    const socket = new WebSocket(
      `${base.replace(/^http/, "ws")}/api/v1/ws/merge-queue?${query}`,
    );
    socket.onopen = () => {
      if (active) {
        setLive(true);
      }
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as { type?: string; items?: ApiMergeQueueItem[] };
        if (message.type === "snapshot") {
          setItems(message.items ?? []);
        }
      } catch {
        // Ignore non-JSON messages.
      }
    };
    socket.onerror = () => socket.close();
    socket.onclose = () => {
      if (!active) {
        return;
      }
      setLive(false);
      startPolling();
    };
    return () => {
      active = false;
      socket.close();
      if (poll !== null) {
        window.clearInterval(poll);
      }
    };
  }, [actor, load, t]);

  async function enqueue() {
    if (!actor || !repo.trim() || !source.trim() || !target.trim()) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await enqueueMerge(actor, {
        repo: repo.trim(),
        source: source.trim(),
        target: target.trim(),
        title: title.trim(),
        priority: Number(priority) || 0,
      });
      setSource("");
      setTitle("");
      await load();
      setNotice(t("queue.enqueuedNotice"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("queue.enqueueError"));
    } finally {
      setBusy(false);
    }
  }

  async function processNow() {
    if (!actor) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const processed = await processMergeQueue(actor, 5);
      await load();
      setNotice(formatMessage(t("queue.processedNotice"), { count: processed.length }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("queue.processError"));
    } finally {
      setBusy(false);
    }
  }

  async function retry(item: ApiMergeQueueItem) {
    if (!actor) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await retryMerge(actor, item.id);
      await load();
      setNotice(t("queue.retryNotice"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("queue.retryError"));
    } finally {
      setBusy(false);
    }
  }

  async function cancel(item: ApiMergeQueueItem) {
    if (!actor) {
      return;
    }
    setBusy(true);
    try {
      await cancelMerge(actor, item.id);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("queue.cancelError"));
    } finally {
      setBusy(false);
    }
  }

  const visible = statusFilter === "all" ? items : items.filter((item) => item.status === statusFilter);

  return (
    <section className="panel" aria-labelledby="merge-queue-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker">DUOBAO · MERGE TRAIN</p>
          <h2 id="merge-queue-title">{t("queue.title")}</h2>
        </div>
        <span className="section-note">
          <select
            aria-label={t("queue.filterAria")}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            style={{ ...fieldStyle, padding: "4px 8px", marginRight: 10 }}
          >
            <option value="all">{t("queue.all")}</option>
            {Object.entries(STATUS_KEYS).map(([value, key]) => (
              <option key={value} value={value}>
                {t(key)}
              </option>
            ))}
          </select>
          {status?.worker ? t("queue.workerMode") : t("queue.manualMode")} · {status?.queued ?? 0}{" "}
          {t("queue.queued")} · {visible.length} {t("queue.candidates")} · {live ? t("queue.live") : t("queue.polling")} ·{" "}
          {formatMessage(t("queue.workers"), { count: workers.length })}
          <button className="btn btn-ghost" type="button" disabled={busy} onClick={processNow} style={{ marginLeft: 10 }}>
            {t("queue.processNow")}
          </button>
        </span>
      </div>
      {!actor ? (
        <p className="section-note" style={{ padding: "0 26px 22px" }}>
          {t("queue.disabled")}
        </p>
      ) : (
        <>
          <div className="reading-list live-list">
            {visible.length === 0 ? (
              <p className="section-note" style={{ padding: "12px 16px" }}>
                {t("queue.empty")}
              </p>
            ) : (
              visible.map((item) => (
                <div className="reading-item" key={item.id}>
                  <span className="reading-index">{item.status.slice(0, 1).toUpperCase()}</span>
                  <span className="reading-copy">
                    <strong>{item.title || `${item.source} → ${item.target}`}</strong>
                    <span>
                      {formatMessage(t("queue.itemMeta"), {
                        repo: item.repo,
                        source: item.source,
                        target: item.target,
                        attempts: item.attempts,
                      })}{" "}
                      · {statusLabel(item.status)}
                      {evidenceText(item) ? ` · ${evidenceText(item)}` : ""}
                    </span>
                  </span>
                  {item.status === "queued" ? (
                    <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => cancel(item)}>
                      {t("queue.cancel")}
                    </button>
                  ) : ["rejected", "conflict", "cancelled"].includes(item.status) ? (
                    <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => retry(item)}>
                      {t("queue.retry")}
                    </button>
                  ) : null}
                </div>
              ))
            )}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) 80px auto",
              gap: "10px",
              alignItems: "center",
              padding: "0 26px 22px",
            }}
          >
            <input
              aria-label={t("queue.repoAria")}
              style={fieldStyle}
              placeholder="docs.git"
              value={repo}
              onChange={(event) => setRepo(event.target.value)}
            />
            <input
              aria-label={t("queue.sourceAria")}
              style={fieldStyle}
              placeholder="feature"
              value={source}
              onChange={(event) => setSource(event.target.value)}
            />
            <input
              aria-label={t("queue.targetAria")}
              style={fieldStyle}
              placeholder="main"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            />
            <input
              aria-label={t("queue.titleAria")}
              style={fieldStyle}
              placeholder={t("queue.titlePlaceholder")}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
            <input
              aria-label={t("queue.priorityAria")}
              style={fieldStyle}
              placeholder="0"
              value={priority}
              onChange={(event) => setPriority(event.target.value)}
            />
            <button className="btn btn-primary" type="button" disabled={busy || !source.trim()} onClick={enqueue}>
              {busy ? t("queue.busy") : t("queue.enqueue")}
            </button>
          </div>
        </>
      )}
      {notice ? (
        <p className="section-note" style={{ padding: "0 26px 16px" }}>
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="section-note" style={{ padding: "0 26px 16px" }}>
          {error}
        </p>
      ) : null}
    </section>
  );
}

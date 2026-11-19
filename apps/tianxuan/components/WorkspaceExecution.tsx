"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { workspaceEntryStatus, workspaceRunStatus } from "@/components/WorkspaceRuns";
import { useI18n } from "@/lib/i18n-client";
import { workspaceRequest, type Conversation } from "@/lib/workspace-conversations";

type EntryStatus = {
  entry: string;
  state: string;
  progress: { total: number; done: number; percent: number };
  tasks: { task: string; state: string; issue_id?: string; title?: string }[];
  failures: unknown[];
};

type ModelProfile = { id: string };
type RequirementReview = { title: string; body_md: string; version: number; approved_version: number };

const finalTaskStates = new Set(["accepted", "failed", "stopped", "superseded", "closed-unresolved"]);

function isSettled(status: EntryStatus) {
  return status.state === "delivered" && status.tasks.length > 0 &&
    status.tasks.every(({ state }) => finalTaskStates.has(state));
}

type Props = {
  conversation: Conversation;
  editable: boolean;
  busy: boolean;
  change: (action: (conversation: Conversation) => Promise<Conversation>) => Promise<void>;
};

export function WorkspaceExecution({ conversation, editable, busy, change }: Props) {
  const { locale } = useI18n();
  const zh = locale === "zh";
  const execution = conversation.execution;
  const entry = execution?.entry;
  const [scopes, setScopes] = useState<string[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [models, setModels] = useState<ModelProfile[]>([]);
  const [model, setModel] = useState("");
  const [status, setStatus] = useState<EntryStatus | null>(null);
  const [request, setRequest] = useState<"loading" | "ready" | "unavailable" | "error">("loading");
  const [refresh, setRefresh] = useState(0);
  const lastState = useRef("");
  const [review, setReview] = useState<RequirementReview | null>(null);
  const [reviewError, setReviewError] = useState(false);
  const [reviewRefresh, setReviewRefresh] = useState(0);
  const reviewPath = `/${conversation.id}/requirement-review`;
  const needsReview = review && review.version !== review.approved_version;

  useEffect(() => {
    let active = true;
    setReview(null);
    setReviewError(false);
    void workspaceRequest<RequirementReview>(reviewPath).then((result) => {
      if (active) setReview(result);
    }).catch(() => { if (active) setReviewError(true); });
    return () => { active = false; };
  }, [reviewPath, reviewRefresh, conversation.requirement_version]);

  useEffect(() => {
    const update = () => { if (!document.hidden) setReviewRefresh((value) => value + 1); };
    document.addEventListener("visibilitychange", update);
    window.addEventListener("tianxuan:doc-updated", update);
    return () => {
      document.removeEventListener("visibilitychange", update);
      window.removeEventListener("tianxuan:doc-updated", update);
    };
  }, []);

  async function confirmReview(documentVersion: number) {
    await change((current) => workspaceRequest(reviewPath, {
      expected_version: current.version, document_version: documentVersion,
    }));
    setReviewRefresh((value) => value + 1);
  }

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    let reading = false;
    let failures = 0;
    let unchanged = 0;
    let settled = false;
    setRequest("loading");
    const endpoint = entry ? encodeURIComponent(entry) : "capabilities";
    async function read() {
      if (reading || controller.signal.aborted || (entry && document.hidden)) return;
      window.clearTimeout(timer);
      reading = true;
      try {
        const response = await fetch(`/api/v1/native/entry/${endpoint}`, {
          cache: "no-store", signal: controller.signal,
        });
        if (response.status === 404 && !entry) {
          if (!controller.signal.aborted) setRequest("unavailable");
          return;
        }
        if (!response.ok) throw new Error("Execution request failed");
        const data = await response.json();
        if (controller.signal.aborted) return;
        if (entry) {
          if (data.entry !== entry) throw new Error("Execution entry mismatch");
          const current = data as EntryStatus;
          setStatus(current);
          settled = isSettled(current);
          const snapshot = JSON.stringify([entry, current.state, current.tasks, current.progress]);
          if (snapshot !== lastState.current) {
            unchanged = 0;
            lastState.current = snapshot;
            window.dispatchEvent(new Event("tianxuan:execution-updated"));
          } else {
            unchanged += 1;
          }
        } else {
          const installed = Object.keys(data.scopes).sort();
          const available = (data.models ?? []) as ModelProfile[];
          setScopes(installed);
          setChosen((previous) => previous.filter((scope) => installed.includes(scope)));
          setModels(available);
          setModel((previous) => available.some(({ id }) => id === previous) ? previous : "");
        }
        failures = 0;
        setRequest("ready");
      } catch {
        failures += 1;
        if (!controller.signal.aborted) setRequest("error");
      } finally {
        reading = false;
        if (entry && !settled && !controller.signal.aborted && !document.hidden && failures < 5) {
          timer = window.setTimeout(read, 3000 * 2 ** Math.min(4, Math.max(failures, unchanged)));
        }
      }
    }
    function visible() {
      window.clearTimeout(timer);
      if (!document.hidden && !settled) {
        failures = 0;
        unchanged = 0;
        void read();
      }
    }
    void read();
    if (entry) {
      document.addEventListener("visibilitychange", visible);
      window.addEventListener("online", visible);
    }
    return () => {
      controller.abort();
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", visible);
      window.removeEventListener("online", visible);
    };
  }, [entry, refresh]);

  function launch() {
    void change(async (current) => {
      try {
        return await workspaceRequest<Conversation>(`/${current.id}/execution`, {
          expected_version: current.version, requirement_version: current.requirement_version,
          scopes: chosen, ...(model && { model }),
        });
      } catch (failure) {
        const saved = await workspaceRequest<Conversation>(`/${current.id}`).catch(() => null);
        if (saved?.execution && saved.execution.requirement_version === current.requirement_version) return saved;
        setReviewRefresh((value) => value + 1);
        throw failure;
      }
    });
  }

  return (
    <section className="workspace-execution" aria-labelledby="workspace-execution-title">
      <div className="workspace-chat-header">
        <h3 id="workspace-execution-title">{zh ? "需求执行" : "Requirement execution"}</h3>
        {(entry || request === "error" || request === "unavailable") && (
          <button type="button" className="workspace-refresh" disabled={request === "loading"}
            onClick={() => setRefresh((value) => value + 1)}>{zh ? "刷新" : "Refresh"}</button>
        )}
      </div>
      {reviewError && <p role="alert">{zh ? "无法读取需求版本。" : "Could not read the requirement revision."}
        <button type="button" className="workspace-refresh" onClick={() => setReviewRefresh((value) => value + 1)}>
          {zh ? "重试" : "Retry"}
        </button>
      </p>}
      {needsReview && <details className="workspace-requirement-review" key={review.version}>
        <summary>{zh ? `审阅需求版本 ${review.version}` : `Review requirement revision ${review.version}`}</summary>
        <p>{zh ? `当前需求已更新，上次确认版本为 ${review.approved_version}。` :
          `The requirement changed after revision ${review.approved_version} was approved.`}</p>
        <strong>{review.title}</strong>
        <p className="workspace-revision-body">{review.body_md}</p>
        <button type="button" className="btn btn-ghost" disabled={!editable || busy}
          onClick={() => void confirmReview(review.version)}>
          {zh ? `确认需求版本 ${review.version}` : `Approve requirement revision ${review.version}`}
        </button>
      </details>}
      {request === "loading" && <p role="status">{zh ? "正在读取执行服务…" : "Loading execution service…"}</p>}
      {request === "unavailable" && <p>{zh ? "尚未配置执行服务。" : "Execution service is not configured."}</p>}
      {request === "error" && <p role="alert">{entry
        ? (zh ? "无法回读执行状态。" : "Could not load execution status.")
        : (zh ? "无法读取已准入的执行范围。" : "Could not load installed scopes.")}</p>}
      {execution ? <>
        {status && status.entry === entry && <>
          <p role="status">{workspaceEntryStatus(status.state, zh)} · {zh
            ? `需求工单 ${status.progress.done}/${status.progress.total} 已完成`
            : `${status.progress.done}/${status.progress.total} requirement work orders complete`}</p>
          {status.failures.length > 0 && <p role="alert">{zh ? "执行服务报告异常。" : "The execution service reported an error."}</p>}
          {status.tasks.length > 0 && <ul className="workspace-items">
            {status.tasks.map(({ task, state, issue_id, title }, index) => {
              const name = title ?? (zh ? `执行工单 ${index + 1}` : `Execution work order ${index + 1}`);
              return <li className="workspace-item-details" key={task}>
                {issue_id ? <Link className="text-link" href={`/issues/${encodeURIComponent(issue_id)}`}>{name}</Link>
                  : <span>{name}</span>}
                <span>{workspaceRunStatus(state, zh)}</span>
              </li>;
            })}
          </ul>}
        </>}
        <details>
          <summary>{zh ? "执行详情" : "Execution details"}</summary>
          <p><span>{zh ? "执行编号" : "Execution ID"}</span> <code>{entry}</code></p>
          <p>{execution.scopes.join(" · ")}{execution.model && ` · ${execution.model}`}</p>
          {status && status.entry === entry && status.tasks.length > 0 && <ul className="workspace-items">
            {status.tasks.map(({ task, title }, index) => <li key={task}>
              <span>{title ?? (zh ? `工单 ${index + 1}` : `Work order ${index + 1}`)}</span> <code>{task}</code>
            </li>)}
          </ul>}
        </details>
      </> : request === "ready" && review && !needsReview && (scopes.length ? (
        <fieldset disabled={!editable || busy}>
          <legend>{zh ? "选择执行范围" : "Select execution scopes"}</legend>
          <div className="workspace-execution-scopes">
            {scopes.map((scope) => <label key={scope}>
              <input type="checkbox" checked={chosen.includes(scope)} onChange={(event) => {
                const checked = event.currentTarget.checked;
                setChosen((previous) => checked ? [...previous, scope] : previous.filter((item) => item !== scope));
              }} /> {scope}
            </label>)}
          </div>
          {models.length > 0 && <label className="workspace-execution-model">
            {zh ? "执行模型" : "Execution model"}
            <select value={model} onChange={(event) => setModel(event.target.value)}>
              <option value="">{zh ? "按任务自动选择" : "Select by task capability"}</option>
              {models.map(({ id }) => <option key={id} value={id}>{id}</option>)}
            </select>
          </label>}
          <button type="button" className="btn btn-ghost" disabled={!chosen.length} onClick={launch}>
            {zh ? "启动已确认需求" : "Run approved requirement"}
          </button>
        </fieldset>
      ) : <p>{zh ? "当前没有已准入的执行范围。" : "No execution scopes are installed."}</p>)}
      {conversation.past_executions.length > 0 && <details>
        <summary>{zh ? "以往版本的执行编号" : "Execution IDs for earlier revisions"}</summary>
        <ul className="workspace-items">
          {conversation.past_executions.map((item) => <li className="workspace-item-details" key={item.entry}>
            <span>{zh ? `版本 ${item.requirement_version}` : `Revision ${item.requirement_version}`}</span>
            <code>{item.entry}</code>
          </li>)}
        </ul>
      </details>}
    </section>
  );
}

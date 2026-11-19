"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useIdentity } from "@/components/IdentityProvider";
import { authHeaders } from "@/lib/auth";
import { useActor } from "@/lib/use-actor";
import { useI18n } from "@/lib/i18n-client";
import styles from "./page.module.css";

type Entry = "existing" | "tianxuan";
type Snapshot = {
  available: boolean;
  source?: string;
  revision?: string;
  imported_at?: string | null;
  published_at?: string | null;
  counts?: Record<string, number>;
  records_sha256?: string;
};

const countLabels: Record<string, [string, string]> = {
  commit: ["提交", "Commits"], requirement: ["需求文件", "Requirement files"],
  issue: ["工单", "Issues"], pull: ["拉取请求", "Pull requests"],
  pull_issue_projection: ["拉取请求的工单记录", "Pull request issue records"],
  issue_comment: ["会话评论", "Conversation comments"], review: ["审查", "Reviews"],
  review_comment: ["审查评论", "Review comments"], commit_comment: ["提交评论", "Commit comments"],
  attachment: ["附件", "Attachments"],
};

async function readEntry(url: string, actor: string, signal?: AbortSignal, entry?: Entry): Promise<Entry> {
  const response = await fetch(url, {
    cache: "no-store", signal, method: entry ? "PUT" : "GET",
    headers: { ...authHeaders(actor), ...(entry ? { "Content-Type": "application/json" } : {}) },
    body: entry ? JSON.stringify({ entry }) : undefined,
  });
  if (!response.ok) throw Error(String(response.status));
  const result = await response.json();
  if (result.entry !== "existing" && result.entry !== "tianxuan") throw Error();
  return result.entry;
}

function EntryChoice({ url, actor, zh }: { url: string; actor: string; zh: boolean }) {
  const identity = useIdentity();
  const canConfigure = identity?.role === "admin";
  const [current, setCurrent] = useState<Entry>();
  const [choice, setChoice] = useState<Entry>("existing");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setCurrent(undefined);
    setMessage("");
    readEntry(url, actor, controller.signal).then(value => {
      if (!controller.signal.aborted) { setCurrent(value); setChoice(value); }
    }).catch(() => {
      if (!controller.signal.aborted) setMessage(zh ? "无法读取当前入口。" : "Could not read the current entry.");
    });
    return () => controller.abort();
  }, [url, actor, zh, reload]);

  async function save() {
    if (!canConfigure || busy) return;
    setBusy(true);
    try {
      const value = await readEntry(url, actor, undefined, choice);
      setCurrent(value);
      setChoice(value);
      setMessage(zh ? "已保存入口。" : "Entry saved.");
    } catch {
      setCurrent(undefined);
      setMessage(zh ? "未确认保存结果，请重新读取。" : "Save unconfirmed. Reload the current entry.");
    } finally {
      setBusy(false);
    }
  }
  return <div className={styles.choice}>
    {current ? <><label>{zh ? "新任务入口" : "Entry for new tasks"}
      <select value={choice} disabled={busy || !canConfigure}
        onChange={event => setChoice(event.target.value as Entry)}>
        <option value="existing">{zh ? "现有入口" : "Existing entry"}</option>
        <option value="tianxuan">{zh ? "天璇" : "Tianxuan"}</option>
      </select></label>
      <button type="button" disabled={busy || choice === current || !canConfigure} onClick={save}>
        {zh ? "保存入口" : "Save entry"}
      </button></> : message ? <button type="button" onClick={() => setReload(reload + 1)}>
        {zh ? "重新读取" : "Reload entry"}</button> : <span>{zh ? "正在读取…" : "Loading…"}</span>}
    <span role="status">{message}</span>
  </div>;
}

function NewTask({ scope, actor, zh }: { scope: string; actor: string; zh: boolean }) {
  const identity = useIdentity();
  const canStart = identity?.role === "admin" || identity?.role === "editor";
  const [title, setTitle] = useState("");
  const [result, setResult] = useState<{ text: string; href?: string }>();
  const [pending, setPending] = useState(false);
  const call = useRef("");
  const inFlight = useRef(false);
  async function start(event: FormEvent) {
    event.preventDefault();
    if (!canStart || inFlight.current || !title.trim()) return;
    inFlight.current = true;
    setPending(true);
    setResult(undefined);
    try {
      if (!call.current) {
        const bytes = crypto.getRandomValues(new Uint8Array(16));
        call.current = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
      }
      const response = await fetch("/api/v1/migration/tasks", {
        method: "POST", headers: { ...authHeaders(actor), "Content-Type": "application/json" },
        body: JSON.stringify({ ...Object.fromEntries(new URLSearchParams(scope)),
          title: title.trim(), call_id: call.current }),
      });
      if (!response.ok) throw Error(String(response.status));
      const data = await response.json();
      if (data.entry !== "existing" && data.entry !== "tianxuan") throw Error();
      let href: string | undefined;
      if (data.url) {
        const link = new URL(data.url, location.origin);
        if (!["http:", "https:"].includes(link.protocol)) throw Error();
        href = link.href;
      }
      setResult({ href, text: href ? (zh ? "打开任务入口" : "Open task entry") :
        (zh ? "请为此项目配置现有入口。" : "Configure the existing entry for this project.") });
    } catch {
      setResult({ text: zh ? "无法确认任务结果，请核对项目和需求后重试。" :
        "Task result unconfirmed. Check the project and requirement, then retry." });
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }
  return <form onSubmit={start}><label>{zh ? "任务标题" : "Task title"}
    <input required value={title} disabled={pending} onChange={event => {
      setTitle(event.target.value); call.current = ""; setResult(undefined);
    }} /></label>
    <button type="submit" disabled={!canStart || !title.trim() || pending}>
      {zh ? "新建任务" : "New task"}</button>
    <span role="status">{result?.href ? <a href={result.href}>{result.text}</a> : result?.text}</span>
  </form>;
}

export default function MigrationPage() {
  const { locale, t } = useI18n();
  const zh = locale === "zh";
  const actor = useActor();
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  const [project, setProject] = useState("");
  const [requirement, setRequirement] = useState("");
  const [scope, setScope] = useState("");
  const statusProject = new URLSearchParams(scope).get("project") ?? "workspace";
  useEffect(() => {
    const controller = new AbortController();
    setSnapshot(undefined);
    setFailed(false);
    fetch("/api/v1/migration/status?" + new URLSearchParams({ project: statusProject }), { headers: authHeaders(actor), cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw Error();
        const result = await response.json();
        if (typeof result.available !== "boolean") throw Error();
        if (!controller.signal.aborted) setSnapshot(result);
      }).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [actor, reload, statusProject]);
  function loadScope(event: FormEvent) {
    event.preventDefault();
    if (!project.trim()) return;
    const query = new URLSearchParams({ project: project.trim() });
    if (requirement.trim()) query.set("requirement", requirement.trim());
    setScope(query.toString());
  }

  return <div className="page-stack">
    <header className="page-header"><h1>{t("nav.migration")}</h1></header>
    <section className={styles.panel}>
      <h2>{zh ? "已导入的历史" : "Imported history"}</h2>
      {!snapshot ? <p role="status">{failed ? (zh ? "无法读取迁移状态。" : "Could not read migration status.")
        : (zh ? "正在读取…" : "Loading…")}</p> : !snapshot.available
        ? <p>{zh ? "当前租户尚无迁移回执。" : "No migration receipt for this tenant yet."}</p> : <>
          <dl>{[[zh ? "来源" : "Source", snapshot.source], [zh ? "版本" : "Revision", snapshot.revision],
            [zh ? "导入时间" : "Imported", snapshot.imported_at ?? (zh ? "未知" : "Unknown")],
            [zh ? "发布时间" : "Published", snapshot.published_at ?? (zh ? "未知" : "Unknown")],
            ["SHA-256", snapshot.records_sha256]]
            .map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          <dl className={styles.counts}>{Object.entries(snapshot.counts ?? {}).map(([kind, count]) =>
            <div key={kind}><dt>{countLabels[kind]?.[zh ? 0 : 1] ?? kind}</dt><dd>{count.toLocaleString(locale)}</dd></div>)}</dl>
        </>}
      <button onClick={() => setReload(reload + 1)}>{zh ? "刷新状态" : "Refresh status"}</button>
    </section>
    <section className={styles.panel}>
      <h2>{zh ? "新任务入口" : "New task entry"}</h2>
      <p>{zh ? "按项目或需求选择入口。历史未结工单仅作记录。" : "Choose an entry per project or requirement. Historical open issues remain records."}</p>
      <form onSubmit={loadScope}>
        <label>{zh ? "项目 ID" : "Project ID"}<input required value={project}
          onChange={e => { setProject(e.target.value); setScope(""); }} /></label>
        <label>{zh ? "需求 ID（可选）" : "Requirement ID (optional)"}<input value={requirement}
          onChange={e => { setRequirement(e.target.value); setScope(""); }} /></label>
        <button type="submit" disabled={!project.trim()}>{zh ? "查看入口" : "View entry"}</button>
      </form>
      {scope && <div key={scope + actor}>
        <EntryChoice url={"/api/v1/migration/entry?" + scope} actor={actor} zh={zh} />
        <NewTask scope={scope} actor={actor} zh={zh} />
      </div>}
    </section>
  </div>;
}

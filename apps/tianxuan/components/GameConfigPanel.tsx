"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useI18n } from "@/lib/i18n-client";
import { useActor } from "@/lib/use-actor";
import { getToken } from "@/lib/auth";
import { fetchVersions, type ApiVersion } from "@/lib/api";
import {
  ConfigRequestError, createConfigProject, listConfigProjects, readConfigProject,
  readConfigClients, saveConfigProject, restoreConfigProject, projectDraft, parseDraft, mergeConfigDrafts,
  type ConfigProject, type ConfigProjectSummary, type ConfigClient, type ConfigType,
  type ProjectDraft, type FeatureDraft, type EntryDraft,
} from "@/lib/game-config-api";

const types: ConfigType[] = ["number", "integer", "boolean", "string", "enum", "json", "reference"];
const idPattern = "[A-Za-z][A-Za-z0-9_-]{0,63}";
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : String(cause);
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
function initialValue(type: ConfigType) {
  return type === "number" || type === "integer" ? "0" : type === "boolean" ? "false" : type === "json" ? "{}" : "";
}
function typeLabel(type: ConfigType, zh: boolean) {
  const labels = { number: "数值", integer: "整数", boolean: "布尔", string: "文本", enum: "枚举", json: "JSON", reference: "ID 引用" };
  return zh ? labels[type] : type;
}

export function GameConfigPanel() {
  const { locale, t } = useI18n();
  const zh = locale === "zh";
  const actor = useActor();
  const [projects, setProjects] = useState<ConfigProjectSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [unsaved, setUnsaved] = useState(false);
  const load = useCallback(async () => {
    if (!actor) return;
    setLoading(true);
    try {
      const rows = await listConfigProjects(actor);
      setProjects(rows);
      setSelected(current => current || rows[0]?.id || "");
      setError("");
    } catch (cause) { setError(errorText(cause)); }
    finally { setLoading(false); }
  }, [actor]);
  useEffect(() => { void load(); }, [load]);
  const saved = useCallback((project: ConfigProject) => {
    const summary = { id: project.id, title: project.title, version: project.version, feature_count: project.features.length, entry_count: project.features.reduce((sum, f) => sum + f.entries.length, 0) };
    setProjects(current => current.some(item => item.id === project.id) ? current.map(item => item.id === project.id ? summary : item) : [...current, summary]);
  }, []);
  function canLeave() {
    return !unsaved || window.confirm(zh ? "此项目仍有未保存草稿。离开会丢弃草稿，是否继续？" : "This project has unsaved edits. Leave and discard the draft?");
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !canLeave()) return;
    setCreating(true);
    try {
      const project = await createConfigProject(actor, title.trim());
      saved(project); setSelected(project.id); setUnsaved(false); setTitle(""); setError("");
    } catch (cause) { setError(errorText(cause)); }
    finally { setCreating(false); }
  }
  return <div className="page-stack game-config-page">
    <header className="page-header"><div className="page-title-group"><h1>{t("nav.gameConfig")}</h1><p className="page-lede">{zh ? "按 feature 管理参数与内容。完成字段编辑后自动保存，在线游戏实际应用后才显示生效。" : "Manage parameters and content by feature. Fields save when editing finishes; games report when changes are actually applied."}</p></div></header>
    {!actor ? <section className="panel gc-card"><p>{zh ? "登录后管理游戏配置。" : "Sign in to manage game configuration."}</p><Link className="btn btn-primary" href="/login">{zh ? "登录" : "Sign in"}</Link></section> : <>
      <section className="panel gc-card">
        <div className="gc-toolbar"><h2>{zh ? "项目" : "Projects"}</h2><button className="btn btn-ghost" onClick={() => void load()} disabled={loading}>{zh ? "刷新列表" : "Refresh list"}</button></div>
        <label className="gc-field"><span>{zh ? "搜索项目名称或 ID" : "Search project name or ID"}</span><input type="search" value={query} onChange={e => setQuery(e.target.value)} /></label>
        {loading ? <p role="status">{zh ? "读取项目中…" : "Loading projects…"}</p> : null}
        {error ? <p role="alert" className="gc-error">{error}</p> : null}
        <div className="gc-projects" aria-label={zh ? "选择项目" : "Select project"}>
          {projects.filter(project => (project.title + " " + project.id).toLowerCase().includes(query.toLowerCase())).map(project => <button className={"gc-project" + (selected === project.id ? " is-selected" : "")} aria-pressed={selected === project.id} key={project.id} onClick={() => { if (project.id !== selected && canLeave()) { setSelected(project.id); setUnsaved(false); } }}>
            <strong>{project.title}</strong><code>{project.id}</code><small>v{project.version} · {project.feature_count} feature · {project.entry_count} {zh ? "条目" : "entries"}</small>
          </button>)}
          {!loading && !projects.length ? <p>{zh ? "还没有游戏配置项目。" : "No game configuration projects yet."}</p> : null}
        </div>
        <form className="gc-create-project" onSubmit={create}><label className="gc-field"><span>{zh ? "新项目名称" : "New project name"}</span><input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></label><button className="btn btn-primary" disabled={creating || !title.trim()}>{creating ? (zh ? "创建中…" : "Creating…") : (zh ? "创建项目" : "Create project")}</button></form>
      </section>
      {selected ? <ProjectEditor key={actor + ":" + selected} id={selected} actor={actor} onSaved={saved} onDirty={setUnsaved} /> : null}
    </>}
  </div>;
}

function ProjectEditor({ id, actor, onSaved, onDirty }: { id: string; actor: string; onSaved: (project: ConfigProject) => void; onDirty: (dirty: boolean) => void }) {
  const { locale } = useI18n();
  const zh = locale === "zh";
  const [draft, setDraft] = useState<ProjectDraft | null>(null);
  const [version, setVersion] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [remote, setRemote] = useState<ConfigProject | null>(null);
  const [connection, setConnection] = useState<"connecting" | "live" | "polling" | "offline">("connecting");
  const [clients, setClients] = useState<ConfigClient[] | null>(null);
  const [versions, setVersions] = useState<ApiVersion[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [restoring, setRestoring] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [retry, setRetry] = useState(0);
  const draftRef = useRef<ProjectDraft | null>(null);
  const baseRef = useRef<ConfigProject | null>(null);
  const dirtyRef = useRef(false);
  const savingRef = useRef(false);
  const restoringRef = useRef(false);
  const conflictRef = useRef<ConfigProject | null>(null);
  const queuedRef = useRef(false);
  const pendingRemoteRef = useRef<ConfigProject | null>(null);
  const activeRef = useRef(true);
  const saveRef = useRef<() => Promise<void>>(async () => {});
  const setDirtyFlag = useCallback((value: boolean) => { dirtyRef.current = value; setDirty(value); onDirty(value); }, [onDirty]);
  const replaceDraft = useCallback((value: ProjectDraft) => { draftRef.current = value; setDraft(value); }, []);
  const conflict = useCallback((value: ConfigProject) => {
    if (!conflictRef.current || value.version >= conflictRef.current.version) { conflictRef.current = value; setRemote(value); }
  }, []);
  const accept = useCallback((value: ConfigProject) => {
    baseRef.current = value; setVersion(value.version); replaceDraft(projectDraft(value)); setDirtyFlag(false);
    conflictRef.current = null; setRemote(null); setError(""); onSaved(value);
  }, [onSaved, replaceDraft, setDirtyFlag]);
  const receive = useCallback((value: ConfigProject) => {
    if (!activeRef.current || value.id !== id || (baseRef.current && value.version <= baseRef.current.version)) return;
    if (savingRef.current || restoringRef.current) {
      if (!pendingRemoteRef.current || value.version > pendingRemoteRef.current.version) pendingRemoteRef.current = value;
      return;
    }
    onSaved(value);
    if (dirtyRef.current || conflictRef.current) conflict(value);
    else accept(value);
  }, [accept, conflict, id, onSaved]);
  const history = useCallback(async () => {
    try { const rows = await fetchVersions(id, actor); if (activeRef.current) { setVersions(rows); setHistoryError(""); } }
    catch (cause) { if (activeRef.current) setHistoryError(errorText(cause)); }
  }, [actor, id]);

  useEffect(() => {
    activeRef.current = true;
    let active = true, socket: WebSocket | null = null, retryTimer = 0, reading = false;
    async function refresh() {
      if (!active || reading) return;
      reading = true;
      const results = await Promise.allSettled([readConfigProject(actor, id), readConfigClients(actor, id)]);
      if (active) {
        if (results[0].status === "fulfilled") { receive(results[0].value); if (socket?.readyState !== WebSocket.OPEN) setConnection("polling"); }
        else { setConnection("offline"); if (!baseRef.current) setError(errorText(results[0].reason)); }
        if (results[1].status === "fulfilled") setClients(results[1].value);
        else setClients(null);
      }
      reading = false;
    }
    function connect() {
      if (!active) return;
      const url = new URL("/api/v1/ws/game-config/" + encodeURIComponent(id) + "?kind=editor", window.location.origin);
      url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(url);
      socket.onopen = () => {
        const token = getToken();
        socket?.send(JSON.stringify({ type: "subscribe", name: "Tianxuan editor", ...(token ? { token } : { actor }) }));
      };
      socket.onmessage = event => {
        if (!active) return;
        try {
          const message = JSON.parse(event.data);
          if (message.type === "snapshot" && message.project) { setConnection("live"); receive(message.project); void history(); }
          if (message.type === "clients" && Array.isArray(message.clients)) setClients(message.clients);
        } catch { /* Invalid frames never replace the confirmed snapshot. */ }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (!active) return;
        setConnection("polling"); setClients(null);
        void refresh(); retryTimer = window.setTimeout(connect, 3000);
      };
    }
    function beforeUnload(event: BeforeUnloadEvent) { if (dirtyRef.current || savingRef.current || restoringRef.current) { event.preventDefault(); event.returnValue = ""; } }
    void refresh(); void history(); connect();
    const poll = window.setInterval(refresh, 5000);
    const heartbeat = window.setInterval(() => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" })); }, 10000);
    window.addEventListener("beforeunload", beforeUnload); window.addEventListener("online", refresh);
    return () => {
      active = false; activeRef.current = false; window.clearInterval(poll); window.clearInterval(heartbeat); window.clearTimeout(retryTimer); socket?.close();
      window.removeEventListener("beforeunload", beforeUnload); window.removeEventListener("online", refresh);
    };
  }, [actor, id, receive, history, retry]);

  async function save() {
    if (!draftRef.current || !baseRef.current || !dirtyRef.current || conflictRef.current || restoringRef.current) return;
    if (savingRef.current) { queuedRef.current = true; return; }
    const submitted = draftRef.current;
    let payload;
    try { payload = parseDraft(submitted); }
    catch { setError(zh ? "草稿未保存：请填写项目名称、合法数字与 JSON，并选择有效引用。" : "Draft not saved: check the project name, numbers, JSON and reference selections."); return; }
    savingRef.current = true; setSaving(true); setError(""); queuedRef.current = false;
    let succeeded = false;
    try {
      const result = await saveConfigProject(actor, id, payload.title, payload.features, baseRef.current.version);
      if (!activeRef.current) return;
      baseRef.current = result; setVersion(result.version); onSaved(result);
      if (equal(draftRef.current, submitted)) { replaceDraft(projectDraft(result)); setDirtyFlag(false); }
      succeeded = true; void history();
    } catch (cause) {
      if (!activeRef.current) return;
      setError((zh ? "草稿未保存，输入已保留" : "Draft not saved; your input is preserved") + " · " + errorText(cause));
      if (cause instanceof ConfigRequestError && cause.status === 409) {
        // Block retries even if the authoritative re-read itself fails.
        conflict(baseRef.current);
        try { const latest = await readConfigProject(actor, id); if (activeRef.current) conflict(latest); }
        catch { /* Explicit conflict refresh remains available. */ }
      }
    } finally {
      savingRef.current = false;
      if (activeRef.current) {
        setSaving(false);
        const pending = pendingRemoteRef.current; pendingRemoteRef.current = null;
        if (pending) receive(pending);
        if (succeeded && queuedRef.current && !conflictRef.current) void saveRef.current();
      }
    }
  }
  saveRef.current = save;
  function update(next: ProjectDraft, immediate = false) {
    replaceDraft(next); setDirtyFlag(true);
    if (immediate) void saveRef.current();
  }
  function updateFeature(featureId: string, change: Partial<FeatureDraft>, immediate = false) {
    const current = draftRef.current; if (!current) return;
    update({ ...current, features: current.features.map(feature => feature.id === featureId ? { ...feature, ...change } : feature) }, immediate);
  }
  function updateEntry(featureId: string, entryId: string, change: Partial<EntryDraft>, immediate = false) {
    const feature = draftRef.current?.features.find(item => item.id === featureId); if (!feature) return;
    updateFeature(featureId, { entries: feature.entries.map(entry => entry.id === entryId ? { ...entry, ...change } : entry) }, immediate);
  }
  async function resolve(useLocal: boolean) {
    if (!draftRef.current || !baseRef.current || !conflictRef.current) return;
    setResolving(true);
    try {
      const latest = await readConfigProject(actor, id);
      if (!activeRef.current) return;
      if (latest.version !== conflictRef.current.version) { conflict(latest); setError(zh ? "远端又有更新，请查看最新比较后再次选择。" : "The remote changed again. Review the updated comparison before choosing."); return; }
      if (!useLocal) { accept(latest); return; }
      const merged = mergeConfigDrafts(projectDraft(baseRef.current), draftRef.current, projectDraft(latest));
      baseRef.current = latest; setVersion(latest.version); conflictRef.current = null; setRemote(null); setError("");
      update(merged.draft); await saveRef.current();
    } catch (cause) { if (activeRef.current) setError(errorText(cause)); }
    finally { if (activeRef.current) setResolving(false); }
  }
  async function restore(sourceVersion: number) {
    if (!baseRef.current || dirtyRef.current || savingRef.current || conflictRef.current || restoringRef.current) return;
    if (!window.confirm(zh ? "将 v" + sourceVersion + " 恢复为新版本？历史记录会保留。" : "Restore v" + sourceVersion + " as a new version? History will be preserved.")) return;
    restoringRef.current = true; setRestoring(true); setError("");
    try {
      const result = await restoreConfigProject(actor, id, sourceVersion, baseRef.current.version);
      if (activeRef.current) { accept(result); void history(); }
    } catch (cause) {
      if (activeRef.current) {
        setError(errorText(cause));
        if (cause instanceof ConfigRequestError && cause.status === 409) {
          try { receive(await readConfigProject(actor, id)); } catch { /* Retry stays explicit. */ }
        }
      }
    } finally {
      restoringRef.current = false;
      if (activeRef.current) {
        setRestoring(false);
        const pending = pendingRemoteRef.current; pendingRemoteRef.current = null;
        if (pending) receive(pending);
      }
    }
  }
  const blurSave = () => { void saveRef.current(); };
  const search = query.trim().toLowerCase();
  const matches = (text: string) => text.toLowerCase().includes(search);
  const merged = remote && draft && baseRef.current ? mergeConfigDrafts(projectDraft(baseRef.current), draft, projectDraft(remote)) : null;
  const newestVersion = Math.max(version, remote?.version ?? 0);
  return <div className="gc-editor">
    {!draft ? <section className="panel gc-card"><p role={error ? "alert" : "status"}>{error || (zh ? "读取配置中…" : "Loading configuration…")}</p>{error ? <button className="btn btn-ghost" onClick={() => setRetry(value => value + 1)}>{zh ? "重新读取" : "Retry"}</button> : null}</section> : <>
      <section className="panel gc-card">
        <div className="gc-toolbar"><h2>{zh ? "项目配置" : "Project configuration"}</h2><Link className="btn btn-ghost" href={"/docs/" + encodeURIComponent(id)} target="_blank" rel="noopener noreferrer">{zh ? "在文曲共同编辑 ↗" : "Collaborate in Wenqu ↗"}</Link></div>
        <div className="gc-status" aria-live="polite"><span>{saving ? (zh ? "保存中…" : "Saving…") : remote ? (zh ? "版本冲突 · 草稿保留" : "Version conflict · draft kept") : dirty ? (zh ? "草稿未保存" : "Unsaved draft") : (zh ? "已保存" : "Saved") + " v" + version}</span><span>{connection === "live" ? (zh ? "实时连接" : "Live connection") : connection === "polling" ? (zh ? "实时连接重连中 · 定期回读" : "Live connection reconnecting · polling") : connection === "offline" ? (zh ? "无法连接服务器" : "Server unavailable") : (zh ? "连接中…" : "Connecting…")}</span><code>{id}</code></div>
        {error ? <p className="gc-error" role="alert">{error}</p> : null}
        {remote && merged ? <div className="gc-conflict" role="alert">
          <h3>{zh ? "远端有新版本，自动保存已暂停" : "Remote version changed; automatic saving is paused"}</h3>
          <p>{zh ? "草稿基于 v" + version + "，远端为 v" + remote.version + "。独立修改会合并；以下冲突字段需要选择。" : "Draft v" + version + "; remote v" + remote.version + ". Independent changes will be merged. Choose how to handle conflicting fields."}</p>
          <ul>{merged.conflicts.map(path => <li key={path}><code>{path}</code></li>)}</ul>
          {!merged.conflicts.length ? <p>{zh ? "没有重叠字段，可保留双方修改。" : "No overlapping fields; both sets of changes can be kept."}</p> : null}
          <details><summary>{zh ? "查看本地与远端内容" : "Compare local and remote content"}</summary><div className="gc-compare"><div><h4>{zh ? "本地草稿" : "Local draft"}</h4><pre>{JSON.stringify(draft, null, 2)}</pre></div><div><h4>{zh ? "远端配置" : "Remote configuration"}</h4><pre>{JSON.stringify(projectDraft(remote), null, 2)}</pre></div></div></details>
          <div className="gc-toolbar"><button className="btn btn-primary" disabled={resolving} onClick={() => void resolve(true)}>{merged.conflicts.length ? (zh ? "合并并保留我的冲突字段" : "Merge and keep my conflicting fields") : (zh ? "合并双方修改并保存" : "Merge both changes and save")}</button><button className="btn btn-ghost" disabled={resolving} onClick={() => { if (window.confirm(zh ? "丢弃本地草稿并采用远端配置？" : "Discard this local draft and use the remote configuration?")) void resolve(false); }}>{zh ? "采用远端，丢弃草稿" : "Use remote; discard draft"}</button></div>
        </div> : null}
        <label className="gc-field"><span>{zh ? "项目名称" : "Project name"}</span><input maxLength={200} value={draft.title} disabled={restoring} onChange={e => update({ ...draftRef.current!, title: e.target.value })} onBlur={blurSave} /></label>
        <div className="gc-toolbar"><small>{zh ? "失焦或选择后保存。ID 创建后保持稳定；非法草稿不会生效。" : "Saves on blur or selection. IDs remain stable after creation; invalid drafts never become active."}</small><button className="btn btn-ghost" disabled={!dirty || saving || !!remote || restoring} onClick={blurSave}>{zh ? "重试保存草稿" : "Retry saving draft"}</button></div>
      </section>
      <section className="panel gc-card" aria-label={zh ? "游戏消费者" : "Game consumers"}>
        <div className="gc-toolbar"><h2>{zh ? "在线游戏" : "Connected games"}</h2><span>{zh ? "最新保存版本" : "Latest saved version"} v{newestVersion}</span></div>
        {clients === null ? <p>{zh ? "消费者状态尚未确认。" : "Consumer status has not been confirmed."}</p> : !clients.length ? <p>{zh ? "没有在线游戏。保存配置不代表游戏已经应用。" : "No games are connected. A saved configuration does not mean a game has applied it."}</p> : <ul className="gc-clients">{clients.map(client => {
          const applied = client.status === "applied" && client.version === newestVersion;
          const status = client.status === "failed" ? (zh ? "应用失败" : "Application failed") : applied ? (zh ? "已应用最新版本" : "Latest version applied") : (zh ? "待应用最新版本" : "Pending latest version");
          return <li key={client.id}><div><strong>{client.name}</strong><code>{client.id}</code></div><span className={client.status === "failed" ? "gc-error" : ""}>{status} · {zh ? "已确认版本" : "Acknowledged version"} {client.version ? "v" + client.version : "—"}</span>{client.error ? <p className="gc-error">{client.error}</p> : null}</li>;
        })}</ul>}
      </section>
      <section className="panel gc-card">
        <div className="gc-filter"><label className="gc-field"><span>{zh ? "搜索 feature、条目名称、说明或 ID" : "Search features, entries, descriptions or IDs"}</span><input type="search" value={query} onChange={e => setQuery(e.target.value)} /></label><label className="gc-field"><span>{zh ? "条目分类" : "Entry kind"}</span><select value={kind} onChange={e => setKind(e.target.value)}><option value="all">{zh ? "全部" : "All"}</option><option value="parameter">{zh ? "参数" : "Parameters"}</option><option value="content">{zh ? "内容" : "Content"}</option></select></label></div>
        <FeatureCreator zh={zh} disabled={restoring} onCreate={feature => {
          const current = draftRef.current!;
          if (current.features.some(item => item.id === feature.id)) { setError(zh ? "Feature ID 已存在。" : "Feature ID already exists."); return false; }
          update({ ...current, features: [...current.features, feature] }, true); return true;
        }} />
      </section>
      <fieldset disabled={restoring} className="gc-features">
        {draft.features.filter(feature => matches(feature.id + " " + feature.name + " " + feature.description) || feature.entries.some(entry => matches(entry.id + " " + entry.name + " " + entry.description))).map(feature => {
          const featureMatches = matches(feature.id + " " + feature.name + " " + feature.description);
          const entries = feature.entries.filter(entry => (featureMatches || matches(entry.id + " " + entry.name + " " + entry.description)) && (kind === "all" || kind === entry.kind));
          return <section className="panel gc-card" key={feature.id}>
            <div className="gc-toolbar"><h2>{feature.name}</h2><code>feature: {feature.id}</code><button className="btn btn-ghost" onClick={() => {
              if (!window.confirm(zh ? "删除 feature「" + feature.name + "」及其全部条目？若仍被其他条目引用，保存会被拒绝；请在草稿中修复引用后重试。" : "Delete feature “" + feature.name + "” and all its entries? Remaining references will prevent saving; fix them in the draft before retrying.")) return;
              const current = draftRef.current!;
              update({ ...current, features: current.features.filter(item => item.id !== feature.id) }, true);
            }}>{zh ? "删除 feature" : "Delete feature"}</button></div>
            <div className="gc-grid"><label className="gc-field"><span>{zh ? "Feature 名称" : "Feature name"}</span><input value={feature.name} onChange={e => updateFeature(feature.id, { name: e.target.value })} onBlur={blurSave} /></label><label className="gc-field"><span>{zh ? "说明" : "Description"}</span><input value={feature.description} onChange={e => updateFeature(feature.id, { description: e.target.value })} onBlur={blurSave} /></label><label className="gc-field"><span>{zh ? "文曲说明文档 ID（可选）" : "Wenqu documentation ID (optional)"}</span><input value={feature.document_id ?? ""} onChange={e => updateFeature(feature.id, { document_id: e.target.value })} onBlur={blurSave} /></label></div>
            {feature.document_id ? <Link href={"/docs/" + encodeURIComponent(feature.document_id)} target="_blank" rel="noopener noreferrer">{zh ? "打开 feature 说明 ↗" : "Open feature documentation ↗"}</Link> : null}
            <div className="gc-entries">{entries.map(entry => <EntryEditor key={entry.id} feature={feature.id} entry={entry} features={draft.features} zh={zh} change={(value, immediate) => updateEntry(feature.id, entry.id, value, immediate)} save={blurSave} remove={() => {
              if (!window.confirm(zh ? "删除条目「" + entry.name + "」？若仍被引用，保存会被拒绝；请在草稿中修复引用后重试。" : "Delete entry “" + entry.name + "”? Remaining references will prevent saving; fix them in the draft before retrying.")) return;
              const currentFeature = draftRef.current!.features.find(item => item.id === feature.id)!;
              updateFeature(feature.id, { entries: currentFeature.entries.filter(item => item.id !== entry.id) }, true);
            }} />)}</div>
            {!entries.length ? <p>{zh ? "暂无匹配条目。" : "No matching entries."}</p> : null}
            <EntryCreator zh={zh} features={draft.features} onCreate={entry => {
              const currentFeature = draftRef.current!.features.find(item => item.id === feature.id)!;
              if (currentFeature.entries.some(item => item.id === entry.id)) { setError(zh ? "此 feature 内条目 ID 已存在。" : "Entry ID already exists in this feature."); return false; }
              updateFeature(feature.id, { entries: [...currentFeature.entries, entry] }, true); return true;
            }} />
          </section>;
        })}
        {!draft.features.length ? <section className="panel gc-card"><p>{zh ? "先创建 feature，再添加参数或内容。" : "Create a feature, then add parameters or content."}</p></section> : null}
      </fieldset>
      <section className="panel gc-card"><div className="gc-toolbar"><h2>{zh ? "版本历史" : "Version history"}</h2><button className="btn btn-ghost" onClick={() => void history()}>{zh ? "刷新历史" : "Refresh history"}</button></div><p>{zh ? "恢复会创建新版本并推送给在线游戏。请先保存或处理当前草稿。" : "Restoring creates a new version and sends it to connected games. Save or resolve your current draft first."}</p>{historyError ? <p role="alert" className="gc-error">{historyError}</p> : null}<ul className="gc-versions">{versions.map(item => <li key={item.version}><span>v{item.version} · {item.author} · <time dateTime={item.created_at}>{item.created_at}</time></span><button className="btn btn-ghost" disabled={dirty || saving || !!remote || restoring || item.version === version} onClick={() => void restore(item.version)}>{zh ? "恢复此版本" : "Restore version"}</button></li>)}</ul></section>
    </>}
  </div>;
}

function FeatureCreator({ zh, disabled, onCreate }: { zh: boolean; disabled: boolean; onCreate: (feature: FeatureDraft) => boolean }) {
  const [id, setId] = useState(""); const [name, setName] = useState(""); const [description, setDescription] = useState("");
  return <details className="gc-create"><summary>{zh ? "创建 feature" : "Create feature"}</summary><form onSubmit={event => { event.preventDefault(); if (onCreate({ id, name, description, document_id: "", entries: [] })) { setId(""); setName(""); setDescription(""); } }}><fieldset disabled={disabled} className="gc-grid"><label className="gc-field"><span>{zh ? "稳定 ID（字母开头，最多 64 位）" : "Stable ID (letter first, up to 64 characters)"}</span><input required pattern={idPattern} maxLength={64} value={id} onChange={e => setId(e.target.value)} placeholder="combat" /></label><label className="gc-field"><span>{zh ? "显示名称" : "Display name"}</span><input required value={name} onChange={e => setName(e.target.value)} /></label><label className="gc-field"><span>{zh ? "说明" : "Description"}</span><input value={description} onChange={e => setDescription(e.target.value)} /></label><button className="btn btn-primary">{zh ? "创建 feature" : "Create feature"}</button></fieldset></form></details>;
}

function ValueInput({ entry, field, features, zh, change, save }: { entry: EntryDraft; field: "value" | "default"; features: FeatureDraft[]; zh: boolean; change: (text: string, immediate?: boolean) => void; save: () => void }) {
  const value = entry[field];
  const label = field === "value" ? (zh ? "当前值" : "Current value") : (zh ? "默认值" : "Default value");
  let control;
  if (entry.type === "boolean") control = <select value={value} onChange={e => change(e.target.value, true)}>{value !== "true" && value !== "false" ? <option value={value}>{zh ? "请选择布尔值" : "Choose a boolean"}</option> : null}<option value="false">false</option><option value="true">true</option></select>;
  else if (entry.type === "enum") control = <select value={value} onChange={e => change(e.target.value, true)}>{!entry.options.split("\n").includes(value) ? <option value={value}>{value || (zh ? "选择值" : "Choose a value")}</option> : null}{entry.options.split("\n").filter(Boolean).map((option, index) => <option key={option + ":" + index} value={option}>{option}</option>)}</select>;
  else if (entry.type === "reference") {
    let selected = "";
    try { const ref = JSON.parse(value); selected = ref.feature_id + "/" + ref.entry_id; } catch { /* Incomplete selections stay in the draft. */ }
    const choices = features.flatMap(feature => feature.entries.map(item => ({ value: feature.id + "/" + item.id, label: feature.name + " / " + item.name + " (" + feature.id + "/" + item.id + ")", ref: { feature_id: feature.id, entry_id: item.id } })));
    control = <select value={selected} onChange={e => { const choice = choices.find(item => item.value === e.target.value); change(choice ? JSON.stringify(choice.ref, null, 2) : "", true); }}><option value="">{zh ? "选择条目" : "Select an entry"}</option>{selected && !choices.some(choice => choice.value === selected) ? <option value={selected}>{selected} ({zh ? "引用无效" : "invalid reference"})</option> : null}{choices.map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select>;
  } else if (entry.type === "json" || (entry.kind === "content" && entry.type === "string")) control = <textarea rows={entry.type === "json" ? 5 : 3} spellCheck={entry.type !== "json"} value={value} onChange={e => change(e.target.value)} onBlur={save} />;
  else control = <input value={value} inputMode={entry.type === "number" || entry.type === "integer" ? "decimal" : undefined} onChange={e => change(e.target.value)} onBlur={save} />;
  return <label className="gc-field"><span>{label}</span>{control}</label>;
}

function EntryEditor({ feature, entry, features, zh, change, save, remove }: { feature: string; entry: EntryDraft; features: FeatureDraft[]; zh: boolean; change: (value: Partial<EntryDraft>, immediate?: boolean) => void; save: () => void; remove: () => void }) {
  const numeric = entry.type === "number" || entry.type === "integer";
  return <article className="gc-entry"><div className="gc-toolbar"><h3>{entry.name}</h3><code>{feature}/{entry.id}</code><span>{entry.kind === "parameter" ? (zh ? "参数" : "Parameter") : (zh ? "内容" : "Content")} · {typeLabel(entry.type, zh)}</span><button className="btn btn-ghost" onClick={remove}>{zh ? "删除条目" : "Delete entry"}</button></div>
    <div className="gc-grid"><label className="gc-field"><span>{zh ? "名称" : "Name"}</span><input value={entry.name} onChange={e => change({ name: e.target.value })} onBlur={save} /></label><label className="gc-field"><span>{zh ? "说明" : "Description"}</span><input value={entry.description} onChange={e => change({ description: e.target.value })} onBlur={save} /></label><label className="gc-field"><span>{zh ? "分类" : "Kind"}</span><select value={entry.kind} onChange={e => change({ kind: e.target.value as EntryDraft["kind"] }, true)}><option value="parameter">{zh ? "参数" : "Parameter"}</option><option value="content">{zh ? "内容" : "Content"}</option></select></label><label className="gc-field"><span>{zh ? "类型" : "Type"}</span><select value={entry.type} onChange={e => { const type = e.target.value as ConfigType; change({ type, ...(type === "number" || type === "integer" ? {} : { min: "", max: "" }) }, true); }}>{types.map(type => <option key={type} value={type}>{typeLabel(type, zh)}</option>)}</select></label></div>
    <div className="gc-values"><ValueInput entry={entry} field="value" features={features} zh={zh} change={(value, immediate) => change({ value }, immediate)} save={save} /><ValueInput entry={entry} field="default" features={features} zh={zh} change={(value, immediate) => change({ default: value }, immediate)} save={save} /></div>
    {numeric ? <div className="gc-grid"><label className="gc-field"><span>{zh ? "最小值（可选）" : "Minimum (optional)"}</span><input inputMode="decimal" value={entry.min} onChange={e => change({ min: e.target.value })} onBlur={save} /></label><label className="gc-field"><span>{zh ? "最大值（可选）" : "Maximum (optional)"}</span><input inputMode="decimal" value={entry.max} onChange={e => change({ max: e.target.value })} onBlur={save} /></label></div> : null}
    {entry.type === "enum" ? <label className="gc-field"><span>{zh ? "枚举选项（每行一个）" : "Enum options (one per line)"}</span><textarea rows={3} value={entry.options} onChange={e => change({ options: e.target.value })} onBlur={save} /></label> : null}
  </article>;
}

function EntryCreator({ zh, features, onCreate }: { zh: boolean; features: FeatureDraft[]; onCreate: (entry: EntryDraft) => boolean }) {
  const empty = (): EntryDraft => ({ id: "", name: "", description: "", kind: "parameter", type: "number", value: "0", default: "0", min: "", max: "", options: "" });
  const [entry, setEntry] = useState<EntryDraft>(empty);
  const [error, setError] = useState("");
  const change = (update: Partial<EntryDraft>) => setEntry(current => ({ ...current, ...update }));
  function submit(event: FormEvent) {
    event.preventDefault();
    try { parseDraft({ title: "validation", features: [{ id: "validation", name: "validation", description: "", entries: [entry] }] }); }
    catch { setError(zh ? "请填写合法的数值、JSON 或引用。" : "Enter valid numbers, JSON or references."); return; }
    if (onCreate(entry)) { setEntry(empty()); setError(""); }
  }
  return <details className="gc-create"><summary>{zh ? "添加参数或内容" : "Add parameter or content"}</summary><form onSubmit={submit}>
    <div className="gc-grid"><label className="gc-field"><span>{zh ? "稳定 ID（字母开头，最多 64 位）" : "Stable ID (letter first, up to 64 characters)"}</span><input required pattern={idPattern} maxLength={64} value={entry.id} onChange={e => change({ id: e.target.value })} placeholder="damage" /></label><label className="gc-field"><span>{zh ? "显示名称" : "Display name"}</span><input required value={entry.name} onChange={e => change({ name: e.target.value })} /></label><label className="gc-field"><span>{zh ? "分类" : "Kind"}</span><select value={entry.kind} onChange={e => change({ kind: e.target.value as EntryDraft["kind"] })}><option value="parameter">{zh ? "参数" : "Parameter"}</option><option value="content">{zh ? "内容" : "Content"}</option></select></label><label className="gc-field"><span>{zh ? "类型" : "Type"}</span><select value={entry.type} onChange={e => { const type = e.target.value as ConfigType; change({ type, value: initialValue(type), default: initialValue(type), min: "", max: "", options: "" }); }}>{types.map(type => <option key={type} value={type}>{typeLabel(type, zh)}</option>)}</select></label><label className="gc-field"><span>{zh ? "说明" : "Description"}</span><input value={entry.description} onChange={e => change({ description: e.target.value })} /></label></div>
    {entry.type === "enum" ? <label className="gc-field"><span>{zh ? "枚举选项（每行一个）" : "Enum options (one per line)"}</span><textarea required rows={3} value={entry.options} onChange={e => change({ options: e.target.value })} /></label> : null}
    <div className="gc-values"><ValueInput entry={entry} field="value" features={features} zh={zh} change={value => change({ value })} save={() => {}} /><ValueInput entry={entry} field="default" features={features} zh={zh} change={value => change({ default: value })} save={() => {}} /></div>
    {entry.type === "number" || entry.type === "integer" ? <div className="gc-grid"><label className="gc-field"><span>{zh ? "最小值（可选）" : "Minimum (optional)"}</span><input inputMode="decimal" value={entry.min} onChange={e => change({ min: e.target.value })} /></label><label className="gc-field"><span>{zh ? "最大值（可选）" : "Maximum (optional)"}</span><input inputMode="decimal" value={entry.max} onChange={e => change({ max: e.target.value })} /></label></div> : null}
    {error ? <p role="alert" className="gc-error">{error}</p> : null}<button className="btn btn-primary">{zh ? "添加条目" : "Add entry"}</button>
  </form></details>;
}

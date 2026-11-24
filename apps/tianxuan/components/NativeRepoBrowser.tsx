"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useI18n } from "@/lib/i18n-client";

type Revision = { id: string; objects: string[] };
type Result = { module: string; revision: Revision | null };
type ModulePage = {
  available: boolean;
  modules: { module: string; revision: string }[];
  next_cursor: string | null;
};

export function NativeRepoBrowser() {
  const { locale } = useI18n();
  const zh = locale === "zh";
  const [module, setModule] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const [catalog, setCatalog] = useState<ModulePage | null>(null);
  const [catalogError, setCatalogError] = useState(false);
  const [catalogPending, setCatalogPending] = useState(true);
  const [catalogRequest, setCatalogRequest] = useState({ after: "", refresh: 0 });
  const lookupRequest = useRef<AbortController | null>(null);

  useEffect(() => () => lookupRequest.current?.abort(), []);

  useEffect(() => {
    const controller = new AbortController();
    const url = "/api/v1/workspace/modules" +
      (catalogRequest.after ? `/after/${encodeURIComponent(catalogRequest.after)}` : "");
    setCatalogPending(true);
    setCatalogError(false);
    fetch(url, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("module catalog unavailable");
        const data: ModulePage = await response.json();
        if (!controller.signal.aborted) {
          setCatalog((previous) => catalogRequest.after && previous
            ? { ...data, modules: [...previous.modules, ...data.modules] } : data);
        }
      })
      .catch(() => { if (!controller.signal.aborted) setCatalogError(true); })
      .finally(() => { if (!controller.signal.aborted) setCatalogPending(false); });
    return () => controller.abort();
  }, [catalogRequest]);

  function loadCatalog(after = "") {
    if (!after) setCatalog(null);
    setCatalogPending(true);
    setCatalogRequest((previous) => ({ after, refresh: previous.refresh + 1 }));
  }

  async function lookup(name: string, listedRevision?: string) {
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(name)) return;
    lookupRequest.current?.abort();
    const controller = new AbortController();
    lookupRequest.current = controller;
    setPending(true);
    setError(false);
    setResult(null);
    const path = `/api/v1/native/modules/${encodeURIComponent(name)}`;
    const options = { cache: "no-store" as const, signal: controller.signal };
    try {
      let revision: string | null = listedRevision ?? null;
      if (!listedRevision) {
        const head = await fetch(`${path}/head`, options);
        if (!head.ok) throw new Error("head is unavailable");
        revision = (await head.json()).revision;
      }
      if (controller.signal.aborted) return;
      if (revision === null) {
        setResult({ module: name, revision: null });
        return;
      }
      if (typeof revision !== "string" || !/^[a-f0-9]{64}$/.test(revision)) throw new Error("invalid revision");
      const detail = await fetch(`${path}/revisions/${revision}`, options);
      if (!detail.ok) throw new Error("revision is unavailable");
      const { objects } = await detail.json();
      if (!objects || typeof objects !== "object" || Array.isArray(objects)) throw new Error("invalid objects");
      if (!controller.signal.aborted) {
        setResult({ module: name, revision: { id: revision, objects: Object.keys(objects).sort() } });
      }
    } catch {
      if (!controller.signal.aborted) setError(true);
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void lookup(module.trim());
  }

  return (
    <section className="workspace-card native-repo-browser" aria-labelledby="native-repo-title">
      <header className="workspace-chat-header">
        <h2 id="native-repo-title">{zh ? "多宝原生版本" : "Duobao native revisions"}</h2>
        <button className="workspace-refresh" type="button" disabled={catalogPending}
          onClick={() => loadCatalog()}>{zh ? "刷新目录" : "Refresh modules"}</button>
      </header>
      {catalogPending && !catalog && <p role="status">{zh ? "读取模块目录…" : "Loading modules…"}</p>}
      {catalogError && <p role="alert">{zh ? "无法读取模块目录。" : "The module catalog could not be loaded."}</p>}
      {catalog?.available === false && <p>{zh ? "尚未配置原生存储。" : "Native storage is not configured."}</p>}
      {catalog?.available && catalog.modules.length === 0 && <p>{zh ? "暂无可见模块。" : "No visible modules."}</p>}
      {catalog?.available && catalog.modules.length > 0 && (
        <ul className="workspace-items" aria-label={zh ? "原生模块目录" : "Native modules"}>
          {catalog.modules.map((item) => <li className="workspace-item" key={item.module}>
            <button type="button" className="workspace-refresh" onClick={() => {
              setModule(item.module);
              void lookup(item.module, item.revision);
            }}>{item.module}</button>
            <code> {item.revision.slice(0, 12)}</code>
          </li>)}
        </ul>
      )}
      {catalog?.next_cursor && <button className="workspace-refresh" type="button" disabled={catalogPending}
        onClick={() => loadCatalog(catalog.next_cursor ?? "")}>{zh ? "加载更多" : "Load more"}</button>}
      <form onSubmit={submit}>
        <label htmlFor="native-module">{zh ? "模块名" : "Module name"}</label>
        <input id="native-module" pattern={"[A-Za-z0-9][A-Za-z0-9_.\\-]{0,127}"} maxLength={128}
          required value={module} readOnly={pending} onChange={(event) => setModule(event.target.value)} />
        <button type="submit" className="btn btn-ghost" disabled={pending}>
          {pending ? (zh ? "读取中…" : "Loading…") : (zh ? "查询版本" : "Find revision")}
        </button>
      </form>
      {error && <p role="alert">{zh ? "无法读取此模块。" : "Could not read this module."}</p>}
      {result && (
        <div className="native-repo-result" role="status">
          <strong>{result.module}</strong>
          {result.revision ? (
            <>
              <code>{result.revision.id}</code>
              <ul>{result.revision.objects.map((name) => <li key={name}>{name}</li>)}</ul>
            </>
          ) : <p>{zh ? "暂无版本。" : "No revision found."}</p>}
        </div>
      )}
    </section>
  );
}

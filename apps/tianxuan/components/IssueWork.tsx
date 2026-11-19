"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { authHeaders } from "@/lib/auth";
import { useActor } from "@/lib/use-actor";
import { AssetPreview, objectPath, type ReviewAsset as Asset } from "./AssetPreview";
import styles from "./IssueWork.module.css";

type Kind = "concept" | "model";

type Plan = { iteration?: string; milestone?: string; roadmap?: string; status?: string; estimated_minutes?: number; custom_fields?: Record<string, unknown> };
type Work = { id: string; version: number; plan: Plan; logged_minutes: number; assets: Partial<Record<Kind, Asset>>; logs: {minutes: number; note: string}[]; history: unknown[] };
type Pending = { action: string; data: Record<string, unknown> };
const labels = { iteration: "迭代", milestone: "里程碑", roadmap: "路线图", status: "自定义状态" } as const;
const kinds = { concept: "概念图", model: "模型" };

function Field({ name, title, value, numeric = false, required = false }: {
  name: string; title: string; value?: string | number; numeric?: boolean; required?: boolean;
}) {
  return <label>{title}<input name={name} defaultValue={value} type={numeric ? "number" : "text"} min={numeric ? 0 : undefined} required={required} /></label>;
}

export function IssueWork({ id }: { id: string }) {
  const actor = useActor();
  const base = "/api/v1/issues/" + encodeURIComponent(id) + "/work";
  const [work, setWork] = useState<Work>();
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<Pending>();
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const lock = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    setWork(undefined);
    setPending(undefined);
    fetch(base, { headers: authHeaders(actor), cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw Error("读取失败（" + response.status + "）");
        const result = await response.json();
        if (!controller.signal.aborted) setWork(result);
      })
      .catch(error => { if (!controller.signal.aborted) setMessage(String(error)); });
    return () => controller.abort();
  }, [actor, base, reload]);

  async function send(request: Pending) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(base + "/" + request.action, {
        method: "POST", headers: { ...authHeaders(actor), "Content-Type": "application/json" },
        body: JSON.stringify(request.data),
      });
      if (!response.ok) {
        if (response.status === 409) {
          setReload(value => value + 1);
          throw Error("工单已变化。请核对最新版本后重新填写。");
        }
        if (response.status >= 500) setPending(request);
        else setPending(undefined);
        const detail = await response.text();
        throw Error("保存失败（" + response.status + "） " + detail.slice(0, 300));
      }
      setWork(await response.json());
      setPending(undefined);
      setMessage("已保存");
    } catch (error) {
      if (error instanceof TypeError || error instanceof SyntaxError) setPending(request);
      setMessage(String(error));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>, action: string, extra?: Asset) {
    event.preventDefault();
    if (!work || pending || busy) return;
    const values = Object.fromEntries(new FormData(event.currentTarget));
    let payload: Record<string, unknown> = values;
    try {
      if (action === "plan") {
        payload = { plan: { ...values, estimated_minutes: Number(values.estimated_minutes), custom_fields: JSON.parse(String(values.custom_fields) || "{}") } };
      } else if (action === "log") payload = { ...values, minutes: Number(values.minutes) };
      else if (extra) payload = { ...values, kind: extra.kind, module: extra.module, revision: extra.revision, path: extra.path };
      void send({ action, data: { ...payload, expected_version: work.version, call_id: crypto.randomUUID() } });
    } catch (error) { setMessage(String(error)); }
  }

  async function download(asset: Asset) {
    try {
      const response = await fetch(objectPath(asset), { headers: authHeaders(actor) });
      if (!response.ok) throw Error("下载失败（" + response.status + "）");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = asset.path.split("/").pop() || "asset";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (error) { setMessage(String(error)); }
  }

  return <section className={styles.work}>
    <header><h1>工单计划与美术确认</h1><small>{id}{work && " · v" + work.version}</small></header>
    <p role="status">{message}</p>
    {pending && <button disabled={busy} onClick={() => void send(pending)}>重试同一次保存</button>}
    {!work && <button onClick={() => setReload(value => value + 1)}>重新读取工单</button>}
    {work && <fieldset disabled={busy || Boolean(pending)} key={work.version}>
      <section><h2>计划</h2>
        <ol className={styles.road}>{([work.plan.roadmap, work.plan.milestone, work.plan.iteration]).filter(Boolean).map((step, i) => <li key={i}>{step}</li>)}</ol>
        <form onSubmit={event => submit(event, "plan")}>
          {(Object.keys(labels) as (keyof typeof labels)[]).map(key => <Field key={key} name={key} title={labels[key]} value={work.plan[key]} />)}
          <Field name="estimated_minutes" title="预计工时（分钟）" numeric value={work.plan.estimated_minutes ?? 0} />
          <label>自定义字段（JSON 对象）<textarea name="custom_fields" defaultValue={JSON.stringify(work.plan.custom_fields ?? {}, null, 2)} /></label>
          <button>保存计划</button>
        </form>
      </section>
      <section><h2>工时 · {work.logged_minutes} 分钟</h2>
        <ul>{work.logs.map((log, i) => <li key={i}>{log.minutes} 分钟　{log.note}</li>)}</ul>
        <form onSubmit={event => submit(event, "log")}><label>本次分钟数<input name="minutes" type="number" min="1" required /></label><Field name="note" title="工作记录" /><button>登记工时</button></form>
      </section>
      <section><h2>美术修订</h2><form onSubmit={event => submit(event, "submit_asset")}>
        <label>资产类型<select name="kind"><option value="concept">概念图</option><option value="model">模型</option></select></label>
        <Field name="module" title="原生模块" required /><Field name="revision" title="修订 ID" required /><Field name="path" title="资产路径" required />
        <button>提交人工确认</button>
      </form>
      {Object.values(work.assets).filter((asset): asset is Asset => Boolean(asset)).map(asset => <article key={asset.kind}>
        <h3>{kinds[asset.kind]} · {asset.decision}</h3><p>{asset.module} / {asset.path}<br /><code>{asset.revision}</code></p>
        <AssetPreview asset={asset} actor={actor} />
        <button type="button" onClick={() => void download(asset)}>下载此修订</button>
        {asset.decision === "pending" && <form onSubmit={event => submit(event, "decide", asset)}>
          <label>人工结论<select name="decision" required defaultValue=""><option disabled value="">选择结论</option><option value="approved">确认通过</option><option value="changes_requested">要求修改</option></select></label>
          <Field name="note" title="确认意见" /><button>记录人工结论</button>
        </form>}</article>)}</section>
      <details><summary>变更历史（{work.history.length}）</summary><ol>{work.history.map((item, i) => <li key={i}><pre>{JSON.stringify(item, null, 2)}</pre></li>)}</ol></details>
    </fieldset>}
  </section>;
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { authHeaders } from "@/lib/auth";
import { fetchIssues, type ApiIssue } from "@/lib/api";
import styles from "./IssueWork.module.css";

type Stage = { id: string; progress: number; human: boolean };
type Edge = { from: string; to: string };
type Flow = {
  id: string; status: string; version: number; stages: Stage[]; edges: Edge[];
  dependencies: (Pick<ApiIssue, "id" | "title" | "status"> & { accepted: boolean })[]; progress: number; configured: boolean;
};
type Operation = "configure" | "dependencies" | "advance" | "judge";
type Write = (op: Operation, changes: Record<string, unknown>) => void;
type Pending = { op: Operation; body: string };

function FlowDefinition({ flow, write }: { flow: Flow; write: Write }) {
  const [stages, setStages] = useState(flow.stages);
  const [edges, setEdges] = useState(flow.edges);
  const [newId, setNewId] = useState("");
  function addStage(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const id = newId.trim();
    if (!id || stages.some(stage => stage.id === id)) return;
    setStages([...stages, { id, progress: 0, human: false }]);
    setNewId("");
  }
  function addEdge(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = new FormData(e.currentTarget);
    const from = String(values.get("from")), to = String(values.get("to"));
    if (from !== to && !edges.some(edge => edge.from === from && edge.to === to)) setEdges([...edges, { from, to }]);
  }
  return <details><summary>配置阶段与流转路径</summary>
    <p>当前阶段和完成阶段（done）须保留。勾选人工判断后，由审核者选择下一阶段。</p>
    {stages.map((stage, i) => <div className={styles.stage} key={stage.id}>
      <strong>{stage.id}</strong>
      <label>进度（%）<input aria-label={stage.id + " 进度"} type="number" min={0} max={100} value={stage.progress}
        onChange={e => setStages(stages.map((s, n) => n === i ? { ...s, progress: Number(e.target.value) } : s))} /></label>
      <label><input aria-label={stage.id + " 人工判断"} type="checkbox" checked={stage.human}
        onChange={e => setStages(stages.map((s, n) => n === i ? { ...s, human: e.target.checked } : s))} />人工判断</label>
      <button type="button" disabled={stage.id === flow.status || stage.id === "done"}
        onClick={() => { setStages(stages.filter(s => s.id !== stage.id)); setEdges(edges.filter(edge => edge.from !== stage.id && edge.to !== stage.id)); }}>移除 {stage.id}</button>
    </div>)}
    <form onSubmit={addStage}><label>新阶段名称<input required value={newId} onChange={e => setNewId(e.target.value)} /></label>
      <button disabled={!newId.trim() || stages.some(stage => stage.id === newId.trim())}>添加阶段</button></form>
    <h3>允许的流转路径</h3><ul>{edges.map(edge => <li key={JSON.stringify(edge)}>{edge.from} → {edge.to}　<button type="button" aria-label={"删除路径 " + edge.from + " → " + edge.to}
      onClick={() => setEdges(edges.filter(item => item !== edge))}>删除</button></li>)}</ul>
    <form onSubmit={addEdge}>{(["from", "to"] as const).map((key, i) => <label key={key}>{i === 0 ? "起始阶段" : "目标阶段"}
      <select name={key}>{stages.map(stage => <option key={stage.id}>{stage.id}</option>)}</select></label>)}
      <button>添加路径</button></form>
    <button type="button" onClick={() => write("configure", { stages, edges })}>保存流程配置</button>
  </details>;
}

export function IssueFlow({ id, actor }: { id: string; actor: string }) {
  const [flow, setFlow] = useState<Flow>();
  const [choices, setChoices] = useState<ApiIssue[]>([]);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<Pending>();
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const locked = useRef(false);
  const base = "/api/v1/issues/" + encodeURIComponent(id) + "/work/flow";
  useEffect(() => {
    const controller = new AbortController();
    setFlow(undefined);
    setChoices([]);
    setPending(undefined);
    async function load() {
      const response = await fetch(base, { headers: authHeaders(actor), cache: "no-store", signal: controller.signal });
      if (!response.ok) throw Error("流程读取失败（" + response.status + "）");
      const state: Flow = await response.json();
      if (!controller.signal.aborted) setFlow(state);
      const issues = await fetchIssues(actor);
      if (!controller.signal.aborted) setChoices(issues.filter(issue => issue.id !== id));
    }
    load().catch(error => { if (!controller.signal.aborted) setMessage(String(error)); });
    return () => controller.abort();
  }, [base, id, actor, refresh]);

  async function send(request: Pending) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(base + "/" + request.op, { method: "POST", headers: { ...authHeaders(actor), "Content-Type": "application/json" }, body: request.body });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        if (response.status < 500) setPending(undefined);
        else setPending(request);
        if (response.status === 409) setRefresh(n => n + 1);
        throw Error("未保存（" + response.status + "）" + String(detail.detail ?? detail.error ?? ""));
      }
      setFlow(await response.json());
      setPending(undefined);
      setMessage("流程已保存");
    } catch (error) {
      if (error instanceof TypeError || error instanceof SyntaxError) setPending(request);
      setMessage(String(error));
    } finally { locked.current = false; setBusy(false); }
  }

  const write: Write = (op, changes) => {
    if (!flow || pending) return;
    void send({ op, body: JSON.stringify({ ...changes, expected_version: flow.version, call_id: crypto.randomUUID() }) });
  };
  const human = flow?.stages.find(stage => stage.id === flow.status)?.human;
  const next = flow?.edges.filter(edge => edge.from === flow.status) ?? [];
  return <section aria-label="工单流程">
    <h2>工单流程</h2>
    <p role="status">{message}</p>
    {pending && <button type="button" disabled={busy} onClick={() => void send(pending)}>重试本次流程操作</button>}
    <button type="button" disabled={busy || !!pending} onClick={() => {setMessage(""); setRefresh(n => n + 1);}}>刷新流程</button>
    {flow && <fieldset disabled={busy || !!pending} key={flow.version}>
      <p>{flow.configured ? "自定义流程" : "默认流程"} · 当前阶段 <strong>{flow.status}</strong> · {flow.progress}%</p>
      <progress max={100} value={flow.progress} aria-label="工单进度" />
      {next.length > 0 && <form onSubmit={e => { e.preventDefault(); write(human ? "judge" : "advance", { to_status: new FormData(e.currentTarget).get("to_status") }); }}>
        <label>{human ? "人工判断结果" : "下一阶段"}<select name="to_status" required defaultValue="">
          <option value="" disabled>选择目标阶段</option>{next.map(edge => <option key={edge.to}>{edge.to}</option>)}</select></label>
        <button>{human ? "确认人工决定" : "执行流转"}</button>
      </form>}
      <h3>前置工单</h3>
      {flow.dependencies.length ? <ul>{flow.dependencies.map(dep => <li key={dep.id}><Link href={"/issues/" + encodeURIComponent(dep.id)}>{dep.title}</Link> · {dep.status} · {dep.accepted ? "已验收" : "待验收"}</li>)}</ul> : <p>无前置工单</p>}
      <details><summary>编辑依赖</summary>
        <form onSubmit={e => { e.preventDefault(); write("dependencies", { dependencies: new FormData(e.currentTarget).getAll("dependency") }); }}>
          <label>前置工单（可多选）<select multiple name="dependency" size={Math.min(8, Math.max(3, choices.length))}
            defaultValue={flow.dependencies.map(dep => dep.id)} key={choices.map(issue => issue.id).join(",")}>
            {choices.map(issue => <option key={issue.id} value={issue.id}>{issue.title} · {issue.status}</option>)}
          </select></label><button disabled={choices.length === 0}>保存依赖</button>
        </form>
      </details>
      <FlowDefinition flow={flow} write={write} />
    </fieldset>}
  </section>;
}

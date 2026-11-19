"use client";

import { useState, type FormEvent } from "react";
import { useI18n } from "@/lib/i18n-client";

type Revision = { id: string; objects: string[] };
type Result = { module: string; revision: Revision | null };

export function NativeRepoBrowser() {
  const { locale } = useI18n();
  const zh = locale === "zh";
  const [module, setModule] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  async function lookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = module.trim();
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(name) || pending) return;
    setPending(true);
    setError(false);
    setResult(null);
    const path = `/api/v1/native/modules/${encodeURIComponent(name)}`;
    try {
      const head = await fetch(`${path}/head`, { cache: "no-store" });
      if (!head.ok) throw new Error("head is unavailable");
      const { revision } = await head.json();
      if (revision === null) {
        setResult({ module: name, revision: null });
        return;
      }
      if (typeof revision !== "string" || !/^[a-f0-9]{64}$/.test(revision)) throw new Error("invalid revision");
      const detail = await fetch(`${path}/revisions/${revision}`, { cache: "no-store" });
      if (!detail.ok) throw new Error("revision is unavailable");
      const { objects } = await detail.json();
      if (!objects || typeof objects !== "object" || Array.isArray(objects)) throw new Error("invalid objects");
      setResult({ module: name, revision: { id: revision, objects: Object.keys(objects).sort() } });
    } catch {
      setError(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="workspace-card native-repo-browser" aria-labelledby="native-repo-title">
      <h2 id="native-repo-title">{zh ? "多宝原生版本" : "Duobao native revisions"}</h2>
      <form onSubmit={lookup}>
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

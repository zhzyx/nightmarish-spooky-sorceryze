"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { authHeaders } from "@/lib/auth";
import { useActor } from "@/lib/use-actor";
import { useIdentity } from "@/components/IdentityProvider";
import { useI18n } from "@/lib/i18n-client";

export function CreateDoc() {
  const router = useRouter();
  const actor = useActor();
  const identity = useIdentity();
  const { locale } = useI18n();
  const zh = locale === "zh";
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const attempt = useRef<{ title: string; key: string } | null>(null);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = title.trim();
    if (!name || !actor || pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      if (attempt.current?.title !== name) {
        attempt.current = { title: name, key: crypto.randomUUID() };
      }
      const response = await fetch("/api/v1/docs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(actor) },
        body: JSON.stringify({ title: name, body_md: "", lang: locale, call_id: attempt.current.key }),
      });
      if (!response.ok) {
        setError(zh ? `创建失败（${response.status}），请重试。` : `Creation failed (${response.status}). Please retry.`);
        return;
      }
      const document = await response.json() as { id: string };
      router.push(`/docs/${encodeURIComponent(document.id)}`);
      router.refresh();
    } catch {
      setError(zh ? "连接失败，请重试。同一次请求会复用创建结果。" : "Connection failed. Retry to recover the same document.");
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  if (!actor || identity?.role === "viewer") return null;
  return (
    <section className="panel" aria-labelledby="create-document-title">
      <div className="section-heading">
        <h2 id="create-document-title">{zh ? "新建文档" : "Create document"}</h2>
      </div>
      <form onSubmit={create} style={{ padding: "0 26px 24px", display: "flex", flexWrap: "wrap", gap: "12px" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "8px", flex: "1 1 240px" }}>
          {zh ? "文档标题" : "Document title"}
          <input value={title} onChange={event => setTitle(event.target.value)} required disabled={busy}
            style={{ padding: "10px 12px", background: "transparent", color: "inherit", border: "1px solid currentColor", borderRadius: "6px", fontSize: "1rem" }} />
        </label>
        <button className="btn btn-primary" type="submit" disabled={busy || !title.trim()} style={{ alignSelf: "end" }}>
          {busy ? (zh ? "创建中…" : "Creating…") : (zh ? "创建并编辑" : "Create and edit")}
        </button>
        {error ? <p role="alert" style={{ width: "100%" }}>{error}</p> : null}
      </form>
    </section>
  );
}

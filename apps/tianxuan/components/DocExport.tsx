"use client";

import { useState } from "react";
import { downloadDocExport } from "@/lib/api";

function safeName(title: string): string {
  const cleaned = title.replace(/[\\/:*?"<>|\r\n]/g, " ").trim();
  return cleaned || "document";
}

export function DocExport({ docId, title }: { docId: string; title: string }) {
  const actor = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR;
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function save(format: "md" | "html" | "docx" | "pdf") {
    if (!actor) {
      return;
    }
    setBusy(format);
    setError("");
    try {
      const blob = await downloadDocExport(actor, docId, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${safeName(title)}.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "导出失败");
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="panel" aria-labelledby="doc-export-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker">DOCUMENT · EXPORT</p>
          <h2 id="doc-export-title">导出</h2>
        </div>
        <span className="section-note">Markdown / HTML / Word / PDF</span>
      </div>
      <div style={{ display: "flex", gap: 10, padding: "0 26px 22px" }}>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("md")}>
          {busy === "md" ? "导出中…" : "导出 Markdown"}
        </button>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("html")}>
          {busy === "html" ? "导出中…" : "导出 HTML"}
        </button>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("docx")}>
          {busy === "docx" ? "导出中…" : "导出 Word"}
        </button>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("pdf")}>
          {busy === "pdf" ? "导出中…" : "导出 PDF"}
        </button>
      </div>
      {!actor ? (
        <p className="section-note" style={{ padding: "0 26px 18px" }}>
          未配置 NEXT_PUBLIC_TIANXUAN_ACTOR，无法导出。
        </p>
      ) : null}
      {error ? <p className="section-note" style={{ padding: "0 26px 18px" }}>{error}</p> : null}
    </section>
  );
}

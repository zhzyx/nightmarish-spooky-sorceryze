"use client";

import { useActor } from "@/lib/use-actor";

import { useState } from "react";
import { downloadDocExport } from "@/lib/api";
import { useI18n } from "@/lib/i18n-client";

function safeName(title: string): string {
  const cleaned = title.replace(/[\\/:*?"<>|\r\n]/g, " ").trim();
  return cleaned || "document";
}

export function DocExport({ docId, title }: { docId: string; title: string }) {
  const actor = useActor();
  const { t } = useI18n();
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
      setError(cause instanceof Error ? cause.message : t("export.error"));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="panel" aria-labelledby="doc-export-title">
      <div className="section-heading">
        <div>
          <h2 id="doc-export-title">{t("export.title")}</h2>
        </div>
        <span className="section-note">Markdown / HTML / Word / PDF</span>
      </div>
      <div style={{ display: "flex", gap: 10, padding: "0 26px 22px" }}>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("md")}>
          {busy === "md" ? t("export.busy") : t("export.md")}
        </button>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("html")}>
          {busy === "html" ? t("export.busy") : t("export.html")}
        </button>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("docx")}>
          {busy === "docx" ? t("export.busy") : t("export.docx")}
        </button>
        <button className="btn btn-ghost" type="button" disabled={!actor || busy !== ""} onClick={() => save("pdf")}>
          {busy === "pdf" ? t("export.busy") : t("export.pdf")}
        </button>
      </div>
      {!actor ? (
        <p className="section-note" style={{ padding: "0 26px 18px" }}>
          {t("export.disabled")}
        </p>
      ) : null}
      {error ? <p className="section-note" style={{ padding: "0 26px 18px" }}>{error}</p> : null}
    </section>
  );
}

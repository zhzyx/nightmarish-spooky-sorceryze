"use client";

import { useEffect, useState } from "react";
import { useIdentity } from "@/components/IdentityProvider";
import { authHeaders } from "@/lib/auth";
import { useActor } from "@/lib/use-actor";
import { useI18n } from "@/lib/i18n-client";

interface FileContent { path: string; sha: string; content: string }

/** Content panel for Harness's repository tree; all Git work stays in GitService. */
export function RepoFileEditor({ repo, branch, path }: { repo: string; branch: string; path: string }) {
  const identity = useIdentity();
  const actor = useActor();
  const { locale } = useI18n();
  const zh = locale === "zh";
  const [file, setFile] = useState<FileContent | null>(null);
  const [content, setContent] = useState("");
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const url = `/api/v1/git/repos/${encodeURIComponent(repo)}/file`;

  useEffect(() => {
    const controller = new AbortController();
    setFile(null); setContent(""); setMessage(""); setNotice("");
    fetch(`${url}?${new URLSearchParams({ path, branch })}`, { headers: authHeaders(actor), signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`${zh ? "无法打开此文件" : "Cannot open this file"} (${response.status})`);
        const data = await response.json() as FileContent;
        if (!controller.signal.aborted) { setFile(data); setContent(data.content); }
      }).catch(error => { if (!controller.signal.aborted) setNotice(String(error.message)); });
    return () => controller.abort();
  }, [url, path, branch, actor, zh]);

  async function save() {
    if (!file || busy) return;
    setBusy(true); setNotice("");
    try {
      const response = await fetch(url, {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(actor) },
        body: JSON.stringify({ path, branch, content, message, expected_blob: file.sha }),
      });
      if (!response.ok) throw new Error(`${zh ? "保存失败，请重新打开文件核对版本" : "Save failed; reopen the file to check its version"} (${response.status})`);
      const result = await response.json() as { branch: string; commit: string };
      setNotice(`${zh ? "已保存至新分支，可在合入队列中提交" : "Saved to a new branch, ready for the merge queue"}: ${result.branch} · ${result.commit}`);
    } catch (error) { setNotice(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }

  return <div style={{ display: "grid", gap: 12 }}>
    <strong>{path}</strong>
    {file && <>
      <textarea aria-label={zh ? "文件内容" : "File content"} value={content} onChange={e => setContent(e.target.value)}
        readOnly={identity?.role === "viewer" || busy} rows={22} style={{ width: "100%", fontFamily: "monospace" }} />
      {identity && identity.role !== "viewer" && <>
        <input aria-label={zh ? "提交说明" : "Commit message"} placeholder={zh ? "提交说明" : "Commit message"}
          value={message} onChange={e => setMessage(e.target.value)} disabled={busy} />
        <button className="btn btn-primary" disabled={busy || !message.trim() || content === file.content} onClick={() => void save()}>
          {zh ? "保存到新分支" : "Save to a new branch"}
        </button>
      </>}
    </>}
    {notice && <p role="status">{notice}</p>}
  </div>;
}

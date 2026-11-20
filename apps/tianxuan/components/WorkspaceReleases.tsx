"use client";

import { useEffect, useRef, useState } from "react";

type Release = {
  sequence: number; selection: string; candidate: string; channel: string;
  accepted: boolean; modules: unknown; restored_from: string | null;
};
type History = { head: string | null; events: Release[] };

export function WorkspaceReleases({ entry, editable, zh }: { entry: string; editable: boolean; zh: boolean }) {
  const path = "/api/v1/native/entry/" + encodeURIComponent(entry);
  const [history, setHistory] = useState<History | null>(null);
  const [selected, setSelected] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  const pending = useRef<{ expected: string; selection: string; call_id: string } | null>(null);
  const submitting = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setHistory(null);
      setSelected("");
      let after = 0;
      const events: Release[] = [];
      for (;;) {
        const response = await fetch(path + "/releases?limit=100&after=" + after, {
          cache: "no-store", signal: controller.signal,
        });
        if (!response.ok) throw new Error(String(response.status));
        const page: History = await response.json();
        events.push(...page.events.filter(event => event.channel === "stable"));
        if (page.events.length < 100) {
          if (!controller.signal.aborted) setHistory({ head: page.head, events: events.reverse() });
          return;
        }
        after = page.events[page.events.length - 1].sequence;
      }
    }
    void load().catch(e => {
      if (!controller.signal.aborted) setError((zh ? "无法读取发布历史 " : "Could not read release history ") + e.message);
    });
    return () => controller.abort();
  }, [path, refresh, zh]);

  async function restore() {
    if (!history?.head || !selected || !editable || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setReceipt("");
    try {
      if (pending.current?.expected !== history.head || pending.current.selection !== selected) {
        pending.current = { expected: history.head, selection: selected, call_id: crypto.randomUUID() };
      }
      const response = await fetch(path + "/rollback", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pending.current),
      });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 409) {
          pending.current = null;
          setRefresh(value => value + 1);
        }
        throw new Error(String(data.detail ?? response.status));
      }
      setReceipt(data.selection);
      pending.current = null;
      setRefresh(value => value + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  const targets = history?.events.filter(event => event.accepted && event.selection !== history.head) ?? [];
  return <section className="workspace-releases">
    <h4>{zh ? "内容发布历史" : "Content release history"}</h4>
    <button type="button" className="workspace-refresh" disabled={busy}
      onClick={() => { setError(""); setRefresh(value => value + 1); }}>
      {zh ? "刷新发布历史" : "Refresh release history"}
    </button>
    {error && <p role="alert">{error}</p>}
    {receipt && <p role="status">{zh ? "回退回执 " : "Rollback receipt "}<code>{receipt}</code></p>}
    {history && <>
      <p>{zh ? "当前稳定版本 " : "Current stable release "}<code>{history.head ?? "—"}</code></p>
      {history.events.map(event => <details key={event.selection}>
        <summary>#{event.sequence} · <code>{event.selection}</code></summary>
        <p>{zh ? "候选版本 " : "Candidate "}<code>{event.candidate}</code></p>
        {event.restored_from && <p>{zh ? "恢复来源 " : "Restored from "}<code>{event.restored_from}</code></p>}
        <pre>{JSON.stringify(event.modules, null, 2)}</pre>
      </details>)}
      {editable && targets.length > 0 && <fieldset disabled={busy}>
        <label>{zh ? "历史版本" : "Historical release"}
          <select value={selected} onChange={e => setSelected(e.target.value)}>
            <option value="">{zh ? "选择已验收版本" : "Select an accepted release"}</option>
            {targets.map(event => <option value={event.selection} key={event.selection}>
              #{event.sequence} · {event.selection.length > 24 ? event.selection.slice(0, 12) + "…" + event.selection.slice(-8) : event.selection}
            </option>)}
          </select>
        </label>
        {selected && <p className="workspace-selected-release"><code>{selected}</code></p>}
        <button type="button" className="btn btn-ghost" disabled={!selected} onClick={() => void restore()}>
          {zh ? "回退到所选版本" : "Restore selected release"}
        </button>
      </fieldset>}
    </>}
  </section>;
}

"use client";

import { useIdentity } from "@/components/IdentityProvider";
import { useActor } from "@/lib/use-actor";

import Link from "next/link";
import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Icon, type IconName } from "@/components/Icon";
import { getToken } from "@/lib/auth";
import { fetchDoc, MergeConflict, mergeDoc, saveDocTitle, type ApiDocDetail } from "@/lib/api";
import type { DocRecord } from "@/lib/data";
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";

type EditorMode = "split" | "write" | "preview";
type SaveState = "saved" | "dirty" | "saving" | "synced";

function inlineMarkdown(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isBlockBoundary(line: string): boolean {
  const trimmed = line.trim();
  return (
    trimmed === "" ||
    trimmed.startsWith("```") ||
    /^#{1,3}\s/.test(trimmed) ||
    /^>\s?/.test(trimmed) ||
    /^[-*]\s/.test(trimmed) ||
    /^\d+\.\s/.test(trimmed) ||
    trimmed === "---" ||
    trimmed.startsWith("|")
  );
}

function renderMarkdown(markdown: string): ReactNode[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const nodes: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim();
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      nodes.push(
        <pre className="md-code" key={`code-${index}`}>
          {language ? <span className="md-code-lang">{language}</span> : null}
          <code>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (heading) {
      const content = inlineMarkdown(heading[2], `heading-${index}`);
      if (heading[1].length === 1) {
        nodes.push(<h1 key={`h1-${index}`}>{content}</h1>);
      } else if (heading[1].length === 2) {
        nodes.push(<h2 key={`h2-${index}`}>{content}</h2>);
      } else {
        nodes.push(<h3 key={`h3-${index}`}>{content}</h3>);
      }
      index += 1;
      continue;
    }

    if (trimmed === "---") {
      nodes.push(<hr key={`hr-${index}`} />);
      index += 1;
      continue;
    }

    if (trimmed.startsWith("|")) {
      const next = lines[index + 1] ?? "";
      if (/^\s*\|?[\s:|-]+\|?\s*$/.test(next)) {
        const headers = splitTableRow(line);
        index += 2;
        const rows: string[][] = [];
        while (index < lines.length && lines[index].trim().startsWith("|")) {
          rows.push(splitTableRow(lines[index]));
          index += 1;
        }
        nodes.push(
          <div className="md-table-wrap" key={`table-${index}`}>
            <table>
              <thead>
                <tr>
                  {headers.map((header, cellIndex) => (
                    <th key={`th-${index}-${cellIndex}`}>{inlineMarkdown(header, `th-${index}-${cellIndex}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={`tr-${index}-${rowIndex}`}>
                    {row.map((cell, cellIndex) => (
                      <td key={`td-${index}-${rowIndex}-${cellIndex}`}>
                        {inlineMarkdown(cell, `td-${index}-${rowIndex}-${cellIndex}`)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>,
        );
        continue;
      }
    }

    if (trimmed.startsWith(">")) {
      const quote: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quote.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      nodes.push(
        <blockquote key={`quote-${index}`}>
          {inlineMarkdown(quote.join(" "), `quote-${index}`)}
        </blockquote>,
      );
      continue;
    }

    if (/^[-*]\s/.test(trimmed)) {
      const items: { checked: boolean | null; text: string }[] = [];
      while (index < lines.length && /^[-*]\s/.test(lines[index].trim())) {
        let item = lines[index].trim().replace(/^[-*]\s/, "");
        let checked: boolean | null = null;
        const task = item.match(/^\[([ xX])\]\s+(.*)$/);
        if (task) {
          checked = task[1].toLowerCase() === "x";
          item = task[2];
        }
        items.push({ checked, text: item });
        index += 1;
      }
      nodes.push(
        <ul className="md-list" key={`ul-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`li-${index}-${itemIndex}`}>
              {item.checked !== null ? (
                <span
                  aria-hidden="true"
                  className={`md-checkbox${item.checked ? " is-checked" : ""}`}
                />
              ) : null}
              <span>{inlineMarkdown(item.text, `li-${index}-${itemIndex}`)}</span>
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s/, ""));
        index += 1;
      }
      nodes.push(
        <ol className="md-list md-list-ordered" key={`ol-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`oli-${index}-${itemIndex}`}>
              <span>{inlineMarkdown(item, `oli-${index}-${itemIndex}`)}</span>
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length && !isBlockBoundary(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    if (paragraph.length > 0) {
      nodes.push(
        <p key={`p-${index}`}>
          {inlineMarkdown(paragraph.join(" "), `p-${index}`)}
        </p>,
      );
    } else {
      index += 1;
    }
  }

  return nodes;
}

export interface DocEditorProps {
  doc: DocRecord;
  initialContent: string;
  version?: number;
}

export function DocEditor({ doc, initialContent, version: initialVersion }: DocEditorProps) {
  const actor = useActor();
  const identity = useIdentity();
  const isLive = Boolean(actor && doc.id.startsWith("doc_"));
  const draftKey = identity ? `tianxuan:draft:${identity.id}:${doc.id}` : null;
  const { t, locale } = useI18n();
  const modeOptions: { id: EditorMode; label: string; icon: IconName }[] = [
    { id: "split", label: t("editor.modeSplit"), icon: "grid" },
    { id: "write", label: t("editor.modeWrite"), icon: "pen" },
    { id: "preview", label: t("editor.modePreview"), icon: "eye" },
  ];
  const formatActions: {
    id: string;
    label: string;
    before: string;
    after: string;
    placeholder: string;
  }[] = [
    { id: "heading", label: t("editor.fmtHeading"), before: "\n## ", after: "", placeholder: t("editor.phTitle") },
    { id: "bold", label: t("editor.fmtBold"), before: "**", after: "**", placeholder: t("editor.phBold") },
    { id: "italic", label: t("editor.fmtItalic"), before: "_", after: "_", placeholder: t("editor.phItalic") },
    { id: "list", label: t("editor.fmtList"), before: "\n- ", after: "", placeholder: t("editor.phList") },
    { id: "quote", label: t("editor.fmtQuote"), before: "\n> ", after: "", placeholder: t("editor.phQuote") },
    { id: "code", label: t("editor.fmtCode"), before: "`", after: "`", placeholder: t("editor.phCode") },
  ];
  const [mode, setMode] = useState<EditorMode>("split");
  const [title, setTitle] = useState(doc.title);
  const [markdown, setMarkdown] = useState(initialContent);
  const [saveState, setSaveState] = useState<SaveState>(doc.id.startsWith("doc_") ? "synced" : "saved");
  const [restored, setRestored] = useState(false);
  const [legacyDrafts, setLegacyDrafts] = useState<{ title: string; markdown: string }[]>([]);
  const recoveryBlocked = useRef(false);
  const [version, setVersion] = useState(initialVersion ?? doc.version ?? 1);
  const [syncNote, setSyncNote] = useState("");
  const baseRef = useRef({ body: initialContent, title: doc.title, version: initialVersion ?? doc.version ?? 1 });
  const pendingRef = useRef(false);
  const roomRef = useRef<WebSocket | null>(null);
  const [actors, setActors] = useState<string[]>([]);
  const [conflict, setConflict] = useState<ApiDocDetail | null>(null);
  const loadedKey = useRef<string | null>(null);
  const savingRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const key = JSON.stringify([doc.id, draftKey]);
    if (loadedKey.current === key && (pendingRef.current || savingRef.current ||
        (initialVersion ?? doc.version ?? 1) <= baseRef.current.version)) return;
    loadedKey.current = key;
    baseRef.current = { body: initialContent, title: doc.title, version: initialVersion ?? doc.version ?? 1 };
    setTitle(doc.title);
    setMarkdown(initialContent);
    setVersion(initialVersion ?? doc.version ?? 1);
    setRestored(false);
    setLegacyDrafts([]);
    setConflict(null);
    pendingRef.current = false;
    recoveryBlocked.current = false;
    setSaveState(doc.id.startsWith("doc_") ? "synced" : "saved");
    setSyncNote("");
    if (!draftKey) return;
    try {
      const recoveryKey = `${draftKey}:recovery`;
      const recovered = JSON.parse(window.localStorage.getItem(recoveryKey) ?? "[]") as { title: string; markdown: string }[];
      if (!Array.isArray(recovered) || recovered.some(item => typeof item.title !== "string" || typeof item.markdown !== "string")) {
        recoveryBlocked.current = true;
        return;
      }
      setLegacyDrafts(recovered);
      const raw = window.localStorage.getItem(draftKey);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as { title?: unknown; markdown?: unknown; base?: { body?: unknown; title?: unknown; version?: unknown } };
      if (typeof parsed.title === "string" && typeof parsed.markdown === "string") {
        if (typeof parsed.base?.body !== "string" || typeof parsed.base.title !== "string" || typeof parsed.base.version !== "number") {
          const legacy = { title: parsed.title, markdown: parsed.markdown };
          const drafts = recovered.some(item => item.title === legacy.title && item.markdown === legacy.markdown)
            ? recovered : [...recovered, legacy];
          setLegacyDrafts(drafts);
          recoveryBlocked.current = true;
          window.localStorage.setItem(recoveryKey, JSON.stringify(drafts));
          recoveryBlocked.current = false;
          setSyncNote(locale === "zh" ? "发现旧草稿，缺少版本基线，请先导出本地草稿再合并。" : "An older draft needs recovery before merging because its version base is missing.");
          return;
        }
        baseRef.current = { body: parsed.base.body, title: parsed.base.title, version: parsed.base.version };
        setTitle(parsed.title);
        setMarkdown(parsed.markdown);
        pendingRef.current = true;
        setVersion(parsed.base.version);
        setRestored(true);
        setSaveState("saved");
      }
    } catch {
      recoveryBlocked.current = true;
      // Preserve existing drafts if recovery storage cannot be read or written.
    }
  }, [draftKey, doc.title, doc.version, initialContent, initialVersion]);

  useEffect(() => {
    if (saveState !== "dirty" || !draftKey) {
      return;
    }
    function keepDraft() {
      try {
        if (!draftKey || !pendingRef.current || recoveryBlocked.current) return;
        window.localStorage.setItem(
          draftKey,
          JSON.stringify({ title, markdown, base: baseRef.current }),
        );
        setSaveState("saved");
      } catch {
        // Keep the draft in memory when browser storage is unavailable.
      }
    }
    const timeout = window.setTimeout(keepDraft, 900);
    window.addEventListener("pagehide", keepDraft);
    return () => {
      window.clearTimeout(timeout);
      window.removeEventListener("pagehide", keepDraft);
    };
  }, [draftKey, markdown, saveState, title]);

  useEffect(() => {
    if (!isLive || !actor) return;
    let active = true;
    let retry = 0;
    let reading = false;
    function receive(remote: ApiDocDetail) {
      if (!active || savingRef.current || pendingRef.current || remote.id !== doc.id ||
          remote.version <= baseRef.current.version) return;
      baseRef.current = { body: remote.body_md, title: remote.title, version: remote.version };
      setMarkdown(remote.body_md);
      setTitle(remote.title);
      setVersion(remote.version);
      setSaveState("synced");
      setSyncNote("");
    }
    async function refresh() {
      if (!actor || reading || document.hidden || !navigator.onLine) return;
      reading = true;
      try {
        receive(await fetchDoc(doc.id, actor));
      } catch {
        // A disconnected editor retains its last confirmed base.
      } finally {
        reading = false;
      }
    }
    function connect() {
      if (!active || !actor || !navigator.onLine || roomRef.current) return;
      const url = new URL("/api/v1/ws/docs/" + encodeURIComponent(doc.id), window.location.origin);
      url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const token = getToken();
      url.searchParams.set(token ? "token" : "actor", token || actor);
      const room = new WebSocket(url);
      roomRef.current = room;
      room.onmessage = event => {
        if (!active) return;
        const message = JSON.parse(event.data);
        if (message.type === "presence") setActors(message.actors);
        if (message.type === "snapshot" || message.type === "updated") receive(message.doc);
        if (message.type === "changed") void refresh();
      };
      room.onclose = () => {
        if (!active) return;
        roomRef.current = null;
        setActors([]);
        retry = window.setTimeout(connect, 3000);
      };
    }
    function online() {
      connect();
      void refresh();
    }
    function localUpdate(event: Event) {
      receive((event as CustomEvent<ApiDocDetail>).detail);
    }
    window.addEventListener("tianxuan:doc-updated", localUpdate);
    connect();
    const timer = window.setInterval(refresh, 5000);
    window.addEventListener("online", online);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      active = false;
      window.removeEventListener("tianxuan:doc-updated", localUpdate);
      window.clearTimeout(retry);
      window.clearInterval(timer);
      window.removeEventListener("online", online);
      document.removeEventListener("visibilitychange", refresh);
      roomRef.current?.close();
      roomRef.current = null;
    };
  }, [actor, doc.id, isLive]);

  const preview = useMemo(() => renderMarkdown(markdown), [markdown]);
  const characters = markdown.replace(/\s/g, "").length;
  const lines = markdown.split("\n").length;
  const readingTime = Math.max(1, Math.ceil(characters / 420));

  function updateMarkdown(value: string) {
    if (savingRef.current) return;
    pendingRef.current = true;
    setMarkdown(value);
    setSyncNote("");
    setSaveState("dirty");
    setRestored(false);
  }

  function updateTitle(value: string) {
    if (savingRef.current) return;
    pendingRef.current = true;
    setTitle(value);
    setSyncNote("");
    setSaveState("dirty");
  }

  async function persistNow() {
    if (savingRef.current || (isLive && (conflict || !pendingRef.current))) return;
    try {
      if (draftKey && !recoveryBlocked.current) window.localStorage.setItem(
        draftKey,
        JSON.stringify({ title, markdown, base: baseRef.current }),
      );
    } catch {
      // The visible state still reflects the local draft.
    }
    if (!actor || !doc.id.startsWith("doc_")) {
      setSaveState("saved");
      setSyncNote(t("editor.savedLocal"));
      return;
    }
    savingRef.current = true;
    setSaveState("saving");
    try {
      const base = baseRef.current;
      const result = await mergeDoc(doc.id, actor, base.body, markdown, base.version);
      baseRef.current = { body: result.doc.body_md, title: base.title, version: result.doc.version };
      setMarkdown(result.doc.body_md);
      setVersion(result.doc.version);
      if (title !== base.title) {
        if (result.doc.title !== base.title && result.doc.title !== title) throw new MergeConflict(["title"]);
        result.doc = await saveDocTitle(doc.id, actor, result.doc, title);
      }
      baseRef.current = { body: result.doc.body_md, title: result.doc.title, version: result.doc.version };
      setTitle(result.doc.title);
      setVersion(result.doc.version);
      try {
        if (draftKey && !recoveryBlocked.current) window.localStorage.removeItem(draftKey);
      } catch {
        // A storage failure does not invalidate the server save.
      }
      pendingRef.current = false;
      setSaveState("synced");
      setSyncNote(formatMessage(t("editor.syncedServer"), { version: result.doc.version }));
    } catch (error) {
      if (error instanceof MergeConflict) {
        try { setConflict(await fetchDoc(doc.id, actor)); } catch { /* Retry after reconnection. */ }
        setSaveState("dirty");
        setSyncNote(formatMessage(t("editor.conflict"), { count: error.conflicts.length }));
      } else {
        setSaveState("dirty");
        setSyncNote(locale === "zh" ? "服务器同步失败，编辑内容已保留，请重试。" : "Server sync failed. Your edits are retained; retry saving.");
      }
    } finally {
      savingRef.current = false;
    }
  }

  function exportLegacyDraft(legacyDraft: { title: string; markdown: string }) {
    const url = URL.createObjectURL(new Blob([legacyDraft.markdown], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "recovered-draft.md";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function applyFormat(before: string, after: string, placeholder: string) {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = markdown.slice(start, end) || placeholder;
    const next = `${markdown.slice(0, start)}${before}${selected}${after}${markdown.slice(end)}`;
    updateMarkdown(next);
    window.requestAnimationFrame(() => {
      textarea.focus();
      const selectionStart = start + before.length;
      textarea.setSelectionRange(selectionStart, selectionStart + selected.length);
    });
  }

  function handleEditorKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      persistNow();
    }
  }

  const saveCopy =
    saveState === "dirty"
      ? t("editor.dirty")
      : saveState === "saving"
        ? t("editor.saving")
        : saveState === "synced"
          ? formatMessage(t("editor.syncedServer"), { version })
          : isLive
            ? (locale === "zh" ? "本地草稿，待同步" : "Local draft, awaiting sync")
            : t("editor.savedLocal");

  return (
    <div className="doc-editor-shell">
      <header className="doc-editor-top">
        <nav aria-label={t("editor.breadcrumbAria")} className="doc-breadcrumb">
          <Link href="/docs">
            <Icon name="arrowLeft" size={15} />
            {t("editor.allDocs")}
          </Link>
          <span aria-hidden="true">/</span>
          <span>{doc.spaceName}</span>
          <span aria-hidden="true">/</span>
          <span className="doc-breadcrumb-current">{doc.kind}</span>
        </nav>
        <div className="doc-editor-actions">
          <Link className="btn btn-ghost btn-sm" href="/issues">
            {t("editor.linkedIssues")}
            <Icon name="link" size={14} />
          </Link>
          <button
            className={`btn btn-primary btn-sm${saveState === "saved" ? " is-saved" : ""}`}
            disabled={saveState === "saving" || Boolean(conflict)}
            onClick={persistNow}
            type="button"
          >
            <Icon name={saveState === "saved" ? "check" : "pen"} size={14} />
            {saveCopy}
          </button>
        </div>
      </header>

      <div className="doc-meta-strip">
        <div className="doc-meta-left">
          <span className={`kind-tag kind-${doc.spaceId}`}>{doc.kind}</span>
          <span className={`save-indicator save-${saveState}`}>
            <span className="save-dot" aria-hidden="true" />
            {saveCopy}
          </span>
          {syncNote ? <span className="section-note">{syncNote}</span> : null}
          <span className="doc-meta-separator" aria-hidden="true" />
          <span>{formatMessage(t("editor.lastEdited"), { time: doc.updated })}</span>
        </div>
        <div className="doc-meta-right">
          <span className="ai-ready">
            <Icon name="sparkles" size={14} />
            {t("editor.aiReady")}
          </span>
          <div className="avatar-stack" aria-label={t("editor.collaboratorsAria")}>
            {actors.map(id => <span className="avatar avatar-xs" key={id} title={id}>{id.slice(-2)}</span>)}
          </div>
        </div>
      </div>

      {legacyDrafts.map((legacyDraft, index) => (
        <div className="restore-banner" role="status" key={index}>
          <span>{legacyDraft.title}</span>
          <button type="button" onClick={() => exportLegacyDraft(legacyDraft)}>
            {locale === "zh" ? "导出草稿 Markdown" : "Export draft Markdown"}
          </button>
        </div>
      ))}
      {conflict && (
        <section className="restore-banner" role="alert">
          <div>
            <strong>{locale === "zh" ? "远端已保存版本" : "Saved remote version"} v{conflict.version}</strong>
            <p>{conflict.title}</p>
            <pre>{conflict.body_md}</pre>
            <p>{locale === "zh" ? "对照上方版本编辑下方草稿，确认合并内容后再保存。" : "Compare this version with your draft below, edit your resolution, then confirm and save."}</p>
            <button type="button" onClick={() => {
              if (title === baseRef.current.title) setTitle(conflict.title);
              baseRef.current = { body: conflict.body_md, title: conflict.title, version: conflict.version };
              setVersion(conflict.version);
              setConflict(null);
              setSaveState("dirty");
            }}>{locale === "zh" ? "确认以此版本为合并基线" : "Confirm this version as merge base"}</button>
          </div>
        </section>
      )}
      {restored ? (
        <div className="restore-banner" role="status">
          <Icon name="history" size={15} />
          {t("editor.restored")}
          <button onClick={() => setRestored(false)} type="button">
            {t("editor.collapse")}
          </button>
        </div>
      ) : null}

      <div className="doc-title-block">
        <div className="doc-title-copy">
          <p className="section-kicker">{doc.spaceName}</p>
          <input
            disabled={saveState === "saving"}
            aria-label={t("editor.titleAria")}
            className="doc-title-input"
            onChange={(event) => updateTitle(event.target.value)}
            value={title}
          />
          <p className="doc-description">{doc.excerpt}</p>
          <div className="doc-tag-row">
            {doc.tags.map((tag) => (
              <span className="micro-tag" key={tag}>
                {tag}
              </span>
            ))}
            <span className="doc-tag-meta">{doc.readTime}</span>
          </div>
        </div>
        <div className="doc-seal" aria-hidden="true">
          <span>文曲</span>
          <small>MARKDOWN</small>
        </div>
      </div>

      <section className="editor-card" aria-label={t("editor.markdownAria")}>
        <div className="editor-toolbar">
          <div className="format-group" role="group" aria-label={t("editor.formatAria")}>
            {formatActions.map((action) => (
              <button
                aria-label={action.label}
                className="format-button"
                key={action.id}
                onClick={() => applyFormat(action.before, action.after, action.placeholder)}
                title={action.label}
                type="button"
              >
                {action.id === "bold"
                  ? "B"
                  : action.id === "italic"
                    ? "I"
                    : action.id === "heading"
                      ? "H2"
                      : action.id === "list"
                        ? "≡"
                        : action.id === "quote"
                          ? "“"
                          : "</>"}
              </button>
            ))}
          </div>
          <span className="toolbar-divider" aria-hidden="true" />
          <span className="editor-filebadge">
            <Icon name="file" size={14} />
            {doc.id}.md
          </span>
          <div className="mode-switch" role="group" aria-label={t("editor.viewAria")}>
            {modeOptions.map((option) => (
              <button
                aria-pressed={mode === option.id}
                className={mode === option.id ? "is-active" : ""}
                key={option.id}
                onClick={() => setMode(option.id)}
                type="button"
              >
                <Icon name={option.icon} size={14} />
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className={`editor-workspace mode-${mode}`}>
          {mode !== "preview" ? (
            <div className="editor-pane">
              <div className="pane-caption">
                <span>MARKDOWN</span>
                <span className="pane-hint">{isLive ? (locale === "zh" ? "Ctrl / ⌘S 同步到服务器" : "Ctrl / ⌘S saves to the server") : t("editor.saveHint")}</span>
              </div>
              <textarea
                disabled={saveState === "saving"}
                aria-label={t("editor.contentAria")}
                className="markdown-textarea"
                onChange={(event) => updateMarkdown(event.target.value)}
                onKeyDown={handleEditorKeyDown}
                ref={textareaRef}
                spellCheck={false}
                value={markdown}
              />
              <footer className="editor-pane-foot">
                <span>{formatMessage(t("editor.characters"), { count: characters.toLocaleString(locale === "en" ? "en-US" : "zh-CN") })}</span>
                <span>{formatMessage(t("editor.lines"), { count: lines })}</span>
                <span>{formatMessage(t("editor.readingTime"), { minutes: readingTime })}</span>
                <span className="editor-language">Markdown</span>
              </footer>
            </div>
          ) : null}

          {mode !== "write" ? (
            <div className="preview-pane">
              <div className="pane-caption">
                <span>{t("editor.readView")}</span>
                <span className="preview-badge">
                  <Icon name="sparkles" size={12} />
                  {t("editor.aiOptimized")}
                </span>
              </div>
              <article className="markdown-preview">{preview}</article>
            </div>
          ) : null}
        </div>
      </section>

      <p className="editor-footnote">
        <Icon name="lock" size={13} />
        {isLive ? (locale === "zh" ? "编辑时在本设备保留草稿；点击保存或按 Ctrl / ⌘S 同步到服务器。" : "Drafts are kept on this device while editing. Save or press Ctrl / ⌘S to sync to the server.") : t("editor.footnote")}
      </p>
    </div>
  );
}

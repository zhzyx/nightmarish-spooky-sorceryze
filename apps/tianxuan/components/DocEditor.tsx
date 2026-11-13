"use client";

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
import type { DocRecord } from "@/lib/data";

type EditorMode = "split" | "write" | "preview";
type SaveState = "saved" | "dirty" | "saving";

const modeOptions: { id: EditorMode; label: string; icon: IconName }[] = [
  { id: "split", label: "分栏", icon: "grid" },
  { id: "write", label: "写作", icon: "pen" },
  { id: "preview", label: "预览", icon: "eye" },
];

const formatActions: {
  id: string;
  label: string;
  before: string;
  after: string;
  placeholder: string;
}[] = [
  { id: "heading", label: "二级标题", before: "\n## ", after: "", placeholder: "标题" },
  { id: "bold", label: "加粗", before: "**", after: "**", placeholder: "重点" },
  { id: "italic", label: "斜体", before: "_", after: "_", placeholder: "语气" },
  { id: "list", label: "无序列表", before: "\n- ", after: "", placeholder: "列表项" },
  { id: "quote", label: "引用", before: "\n> ", after: "", placeholder: "值得被引用的话" },
  { id: "code", label: "行内代码", before: "`", after: "`", placeholder: "code" },
];

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
}

export function DocEditor({ doc, initialContent }: DocEditorProps) {
  const [mode, setMode] = useState<EditorMode>("split");
  const [title, setTitle] = useState(doc.title);
  const [markdown, setMarkdown] = useState(initialContent);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [restored, setRestored] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(`tianxuan:draft:${doc.id}`);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as { title?: unknown; markdown?: unknown };
      if (typeof parsed.title === "string" && typeof parsed.markdown === "string") {
        setTitle(parsed.title);
        setMarkdown(parsed.markdown);
        setRestored(true);
        setSaveState("saved");
      }
    } catch {
      // A blocked storage API must never prevent editing.
    }
  }, [doc.id]);

  useEffect(() => {
    if (saveState !== "dirty") {
      return;
    }
    const timeout = window.setTimeout(() => {
      try {
        window.localStorage.setItem(
          `tianxuan:draft:${doc.id}`,
          JSON.stringify({ title, markdown }),
        );
      } catch {
        // Keep the draft in memory when browser storage is unavailable.
      }
      setSaveState("saved");
    }, 900);
    return () => window.clearTimeout(timeout);
  }, [doc.id, markdown, saveState, title]);

  const preview = useMemo(() => renderMarkdown(markdown), [markdown]);
  const characters = markdown.replace(/\s/g, "").length;
  const lines = markdown.split("\n").length;
  const readingTime = Math.max(1, Math.ceil(characters / 420));

  function updateMarkdown(value: string) {
    setMarkdown(value);
    setSaveState("dirty");
    setRestored(false);
  }

  function updateTitle(value: string) {
    setTitle(value);
    setSaveState("dirty");
  }

  function persistNow() {
    try {
      window.localStorage.setItem(
        `tianxuan:draft:${doc.id}`,
        JSON.stringify({ title, markdown }),
      );
    } catch {
      // The visible state still reflects the local draft.
    }
    setSaveState("saved");
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
      ? "有未保存更改"
      : saveState === "saving"
        ? "正在保存"
        : "已保存至本设备";

  return (
    <div className="doc-editor-shell">
      <header className="doc-editor-top">
        <nav aria-label="文档路径" className="doc-breadcrumb">
          <Link href="/docs">
            <Icon name="arrowLeft" size={15} />
            全部文档
          </Link>
          <span aria-hidden="true">/</span>
          <span>{doc.spaceName}</span>
          <span aria-hidden="true">/</span>
          <span className="doc-breadcrumb-current">{doc.kind}</span>
        </nav>
        <div className="doc-editor-actions">
          <Link className="btn btn-ghost btn-sm" href="/issues">
            关联工单
            <Icon name="link" size={14} />
          </Link>
          <button
            className={`btn btn-primary btn-sm${saveState === "saved" ? " is-saved" : ""}`}
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
          <span className="doc-meta-separator" aria-hidden="true" />
          <span>最后编辑：{doc.updated}</span>
        </div>
        <div className="doc-meta-right">
          <span className="ai-ready">
            <Icon name="sparkles" size={14} />
            AI 阅读已就绪
          </span>
          <div className="avatar-stack" aria-label="协作者">
            <span className="avatar avatar-xs avatar-jade">文</span>
            <span className="avatar avatar-xs avatar-gold">偃</span>
            <span className="avatar avatar-xs avatar-mist">S</span>
          </div>
        </div>
      </div>

      {restored ? (
        <div className="restore-banner" role="status">
          <Icon name="history" size={15} />
          已恢复上次保存在本设备上的草稿。
          <button onClick={() => setRestored(false)} type="button">
            收起
          </button>
        </div>
      ) : null}

      <div className="doc-title-block">
        <div className="doc-title-copy">
          <p className="section-kicker">{doc.spaceName}</p>
          <input
            aria-label="文档标题"
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

      <section className="editor-card" aria-label="Markdown 编辑器">
        <div className="editor-toolbar">
          <div className="format-group" role="group" aria-label="Markdown 格式">
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
          <div className="mode-switch" role="group" aria-label="编辑器视图">
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
                <span className="pane-hint">⌘S 保存本设备草稿</span>
              </div>
              <textarea
                aria-label="Markdown 内容"
                className="markdown-textarea"
                onChange={(event) => updateMarkdown(event.target.value)}
                onKeyDown={handleEditorKeyDown}
                ref={textareaRef}
                spellCheck={false}
                value={markdown}
              />
              <footer className="editor-pane-foot">
                <span>{characters.toLocaleString("zh-CN")} 字符</span>
                <span>{lines} 行</span>
                <span>约 {readingTime} 分钟阅读</span>
                <span className="editor-language">Markdown</span>
              </footer>
            </div>
          ) : null}

          {mode !== "write" ? (
            <div className="preview-pane">
              <div className="pane-caption">
                <span>阅读视图</span>
                <span className="preview-badge">
                  <Icon name="sparkles" size={12} />
                  为 AI 优化
                </span>
              </div>
              <article className="markdown-preview">{preview}</article>
            </div>
          ) : null}
        </div>
      </section>

      <p className="editor-footnote">
        <Icon name="lock" size={13} />
        当前为前端演示：草稿仅保存在此浏览器，不发送至服务器，也不会读取任何模型凭据。
      </p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState, type DragEvent, type KeyboardEvent } from "react";
import { EmptyState } from "@/components/EmptyState";
import { Icon } from "@/components/Icon";
import {
  issueColumns,
  type IssuePriority,
  type IssueRecord,
  type IssueStatus,
} from "@/lib/data";

type BoardView = "board" | "list";

const projects = ["全部项目", "文曲", "司南", "多宝", "天璇"];

const priorityLabel: Record<IssuePriority, string> = {
  P0: "最高",
  P1: "高",
  P2: "中",
};

function issueMatches(issue: IssueRecord, query: string, project: string): boolean {
  const matchesProject = project === "全部项目" || issue.project === project;
  const haystack = `${issue.key} ${issue.title} ${issue.project} ${issue.tags.join(" ")}`.toLowerCase();
  return matchesProject && haystack.includes(query.trim().toLowerCase());
}

export interface IssueBoardProps {
  initialIssues: IssueRecord[];
}

export function IssueBoard({ initialIssues }: IssueBoardProps) {
  const [items, setItems] = useState<IssueRecord[]>(initialIssues);
  const [view, setView] = useState<BoardView>("board");
  const [query, setQuery] = useState("");
  const [project, setProject] = useState("全部项目");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<IssueStatus | null>(null);

  const filtered = items.filter((issue) => issueMatches(issue, query, project));
  const selected = items.find((issue) => issue.id === selectedId) ?? null;
  const blockedCount = items.filter((issue) => issue.blocked).length;

  useEffect(() => {
    if (!selected) {
      return;
    }
    function closeOnEscape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setSelectedId(null);
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selected]);

  function moveIssue(id: string, status: IssueStatus) {
    setItems((current) =>
      current.map((issue) => (issue.id === id ? { ...issue, status, updated: "刚刚" } : issue)),
    );
    setDraggingId(null);
    setDragOverStatus(null);
  }

  function handleDrop(event: DragEvent<HTMLElement>, status: IssueStatus) {
    event.preventDefault();
    const id = event.dataTransfer.getData("text/plain") || draggingId;
    if (id) {
      moveIssue(id, status);
    }
  }

  function openIssueWithKeyboard(event: KeyboardEvent<HTMLButtonElement>, issueId: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setSelectedId(issueId);
    }
  }

  return (
    <div className="issue-board-shell">
      <div className="board-toolbar">
        <div className="segmented-control" role="group" aria-label="工单视图">
          <button
            aria-pressed={view === "board"}
            className={view === "board" ? "is-active" : ""}
            onClick={() => setView("board")}
            type="button"
          >
            <Icon name="grid" size={14} />
            看板
          </button>
          <button
            aria-pressed={view === "list"}
            className={view === "list" ? "is-active" : ""}
            onClick={() => setView("list")}
            type="button"
          >
            <Icon name="list" size={15} />
            列表
          </button>
        </div>

        <div className="board-filters">
          <label className="field-search">
            <Icon name="search" size={15} />
            <input
              aria-label="搜索工单"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索编号、标题或标签"
              type="search"
              value={query}
            />
          </label>
          <label className="select-field">
            <Icon name="filter" size={14} />
            <span className="sr-only">按项目筛选</span>
            <select onChange={(event) => setProject(event.target.value)} value={project}>
              {projects.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <Icon name="chevronDown" size={13} />
          </label>
        </div>
      </div>

      <div className="board-caption">
        <span>
          <span className="live-dot" aria-hidden="true" />
          本地演示数据 · 拖动卡片可更新状态
        </span>
        <span>
          {filtered.length} / {items.length} 个工单
          {blockedCount > 0 ? (
            <span className="caption-alert">
              <Icon name="alert" size={12} />
              {blockedCount} 个阻塞
            </span>
          ) : null}
        </span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          actionLabel="清除筛选"
          compact
          description="换一个项目、缩短关键词，或清除筛选查看全部工单。"
          eyebrow="SINAN · NO MATCH"
          onAction={() => {
            setQuery("");
            setProject("全部项目");
          }}
          title="没有匹配的工单"
        />
      ) : view === "board" ? (
        <div className="kanban" role="region" aria-label="工单看板">
          {issueColumns.map((column) => {
            const columnIssues = filtered.filter((issue) => issue.status === column.id);
            return (
              <section
                aria-labelledby={`column-${column.id}`}
                className={`kanban-column${dragOverStatus === column.id ? " is-drag-over" : ""}`}
                key={column.id}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragOverStatus(column.id);
                }}
                onDragLeave={() => setDragOverStatus((current) => (current === column.id ? null : current))}
                onDrop={(event) => handleDrop(event, column.id)}
              >
                <header className={`kanban-head status-${column.id}`}>
                  <div className="kanban-head-title">
                    <span className="status-dot" aria-hidden="true" />
                    <h2 id={`column-${column.id}`}>{column.label}</h2>
                    <span className="column-count">{columnIssues.length}</span>
                  </div>
                  <span className="column-hint">{column.hint}</span>
                </header>

                <div className="kanban-cards">
                  {columnIssues.map((issue) => (
                    <button
                      aria-label={`${issue.key} ${issue.title}，打开详情`}
                      className={`issue-card${draggingId === issue.id ? " is-dragging" : ""}${issue.blocked ? " is-blocked" : ""}`}
                      draggable
                      key={issue.id}
                      onClick={() => setSelectedId(issue.id)}
                      onDragEnd={() => {
                        setDraggingId(null);
                        setDragOverStatus(null);
                      }}
                      onDragStart={(event) => {
                        setDraggingId(issue.id);
                        event.dataTransfer.effectAllowed = "move";
                        event.dataTransfer.setData("text/plain", issue.id);
                      }}
                      onKeyDown={(event) => openIssueWithKeyboard(event, issue.id)}
                      type="button"
                    >
                      <span className="issue-card-top">
                        <span className="mono-key">{issue.key}</span>
                        <span className={`priority priority-${issue.priority.toLowerCase()}`}>
                          {issue.priority}
                          <span className="priority-label">{priorityLabel[issue.priority]}</span>
                        </span>
                      </span>
                      <span className="issue-card-title">{issue.title}</span>
                      {issue.blocked ? (
                        <span className="blocked-note">
                          <Icon name="alert" size={12} />
                          等待判断 · 状态迁移边界
                        </span>
                      ) : null}
                      <span className="issue-tags">
                        {issue.tags.map((tag) => (
                          <span className="micro-tag" key={tag}>
                            {tag}
                          </span>
                        ))}
                      </span>
                      <span className="issue-card-foot">
                        <span className="issue-project">
                          <span className="project-dot" aria-hidden="true" />
                          {issue.project}
                        </span>
                        <span className="issue-meta">
                          <span>
                            <Icon name="comment" size={13} />
                            {issue.comments}
                          </span>
                          <span>
                            <Icon name="paperclip" size={13} />
                            {issue.attachments}
                          </span>
                        </span>
                        <span className={`avatar avatar-xs avatar-${issue.assigneeTone}`} aria-hidden="true">
                          {issue.assignee.slice(0, 1)}
                        </span>
                      </span>
                    </button>
                  ))}

                  {columnIssues.length === 0 ? (
                    <div className="column-empty">
                      <span aria-hidden="true">·</span>
                      暂无工单
                    </div>
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <section className="issue-list-panel" aria-label="工单列表">
          <header className="issue-list-head">
            <span>编号 / 标题</span>
            <span>项目</span>
            <span>优先级</span>
            <span>状态</span>
            <span>负责人</span>
            <span>更新</span>
          </header>
          {filtered.map((issue) => (
            <button
              className={`issue-list-row${issue.blocked ? " is-blocked" : ""}`}
              key={issue.id}
              onClick={() => setSelectedId(issue.id)}
              type="button"
            >
              <span className="list-title-cell">
                <span className="mono-key">{issue.key}</span>
                <span className="list-title">
                  {issue.title}
                  {issue.tags.slice(0, 1).map((tag) => (
                    <span className="micro-tag" key={tag}>
                      {tag}
                    </span>
                  ))}
                </span>
              </span>
              <span className="list-project">{issue.project}</span>
              <span>
                <span className={`priority priority-${issue.priority.toLowerCase()}`}>{issue.priority}</span>
              </span>
              <span className={`issue-status issue-status-${issue.status}`}>
                <span className="status-dot" aria-hidden="true" />
                {issueColumns.find((column) => column.id === issue.status)?.label}
              </span>
              <span className="list-assignee">
                <span className={`avatar avatar-xs avatar-${issue.assigneeTone}`} aria-hidden="true">
                  {issue.assignee.slice(0, 1)}
                </span>
                {issue.assignee}
              </span>
              <span className="list-updated">{issue.updated}</span>
            </button>
          ))}
        </section>
      )}

      {selected ? (
        <div className="drawer-layer">
          <button
            aria-label="关闭工单详情"
            className="drawer-scrim"
            onClick={() => setSelectedId(null)}
            type="button"
          />
          <aside aria-labelledby="issue-drawer-title" aria-modal="true" className="issue-drawer" role="dialog">
            <header className="drawer-head">
              <div className="drawer-key">
                <span className="mono-key">{selected.key}</span>
                <span className={`priority priority-${selected.priority.toLowerCase()}`}>{selected.priority}</span>
                {selected.blocked ? (
                  <span className="blocked-chip">
                    <Icon name="alert" size={12} />
                    阻塞
                  </span>
                ) : null}
              </div>
              <button
                aria-label="关闭详情"
                className="icon-button"
                onClick={() => setSelectedId(null)}
                type="button"
              >
                <Icon name="close" size={18} />
              </button>
            </header>

            <div className="drawer-body">
              <h2 id="issue-drawer-title">{selected.title}</h2>
              <div className="drawer-fields">
                <label className="drawer-field">
                  <span>状态</span>
                  <span className="select-field">
                    <select
                      aria-label="修改工单状态"
                      onChange={(event) => moveIssue(selected.id, event.target.value as IssueStatus)}
                      value={selected.status}
                    >
                      {issueColumns.map((column) => (
                        <option key={column.id} value={column.id}>
                          {column.label}
                        </option>
                      ))}
                    </select>
                    <Icon name="chevronDown" size={13} />
                  </span>
                </label>
                <div className="drawer-field">
                  <span>项目</span>
                  <strong>{selected.project}</strong>
                </div>
                <div className="drawer-field">
                  <span>负责人</span>
                  <strong className="drawer-person">
                    <span className={`avatar avatar-xs avatar-${selected.assigneeTone}`} aria-hidden="true">
                      {selected.assignee.slice(0, 1)}
                    </span>
                    {selected.assignee}
                  </strong>
                </div>
                <div className="drawer-field">
                  <span>更新</span>
                  <strong>{selected.updated}</strong>
                </div>
              </div>

              <section className="drawer-section">
                <p className="section-kicker">CONTEXT</p>
                <h3>说明</h3>
                <p>{selected.detail}</p>
              </section>

              <section className="drawer-section">
                <p className="section-kicker">ACCEPTANCE</p>
                <h3>验收条件</h3>
                <ul className="criteria-list">
                  {selected.criteria.map((criterion) => (
                    <li key={criterion}>
                      <span className="criteria-box" aria-hidden="true" />
                      {criterion}
                    </li>
                  ))}
                </ul>
              </section>

              <section className="drawer-links">
                {selected.docId ? (
                  <Link href={`/docs/${selected.docId}`}>
                    <Icon name="docs" size={15} />
                    关联设计文档
                    <Icon name="arrowRight" size={13} />
                  </Link>
                ) : null}
                {selected.repoId ? (
                  <Link href="/repos">
                    <Icon name="repos" size={15} />
                    关联仓库
                    <Icon name="arrowRight" size={13} />
                  </Link>
                ) : null}
              </section>
            </div>

            <footer className="drawer-foot">
              <span className="drawer-demo-note">状态变更仅保存在当前页面</span>
              <button
                className="btn btn-primary btn-sm"
                disabled={selected.status === "done"}
                onClick={() => moveIssue(selected.id, "done")}
                type="button"
              >
                <Icon name="check" size={15} />
                {selected.status === "done" ? "已完成" : "标记完成"}
              </button>
            </footer>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

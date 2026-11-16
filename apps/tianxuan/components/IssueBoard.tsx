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
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";

type BoardView = "board" | "list";

const ALL_PROJECTS = "__all__";

function issueMatches(issue: IssueRecord, query: string, project: string): boolean {
  const matchesProject = project === ALL_PROJECTS || issue.project === project;
  const haystack = `${issue.key} ${issue.title} ${issue.project} ${issue.tags.join(" ")}`.toLowerCase();
  return matchesProject && haystack.includes(query.trim().toLowerCase());
}

export interface IssueBoardProps {
  initialIssues: IssueRecord[];
}

export function IssueBoard({ initialIssues }: IssueBoardProps) {
  const { t } = useI18n();
  const projects = [
    { value: ALL_PROJECTS, label: t("board.allProjects") },
    { value: "文曲", label: "文曲" },
    { value: "司南", label: "司南" },
    { value: "多宝", label: "多宝" },
    { value: "天璇", label: "天璇" },
  ];
  const priorityLabels: Record<IssuePriority, string> = {
    P0: t("board.priorityHighest"),
    P1: t("board.priorityHigh"),
    P2: t("board.priorityMedium"),
  };
  const columnLabels: Record<string, string> = {
    backlog: t("issues.colBacklog"),
    planned: t("issues.colPlanned"),
    progress: t("issues.colProgress"),
    review: t("issues.colReview"),
    done: t("issues.colDone"),
    cancelled: t("issues.colCancelled"),
  };
  const columnHints: Record<string, string> = {
    backlog: t("issues.colBacklogHint"),
    planned: t("issues.colPlannedHint"),
    progress: t("issues.colProgressHint"),
    review: t("issues.colReviewHint"),
    done: t("issues.colDoneHint"),
    cancelled: t("issues.colCancelledHint"),
  };
  const columnLabel = (id: string): string => columnLabels[id] ?? id;
  const columnHint = (id: string): string => columnHints[id] ?? "";
  const [items, setItems] = useState<IssueRecord[]>(initialIssues);
  const [view, setView] = useState<BoardView>("board");
  const [query, setQuery] = useState("");
  const [project, setProject] = useState(ALL_PROJECTS);
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
      current.map((issue) => (issue.id === id ? { ...issue, status, updated: t("board.justNow") } : issue)),
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
        <div className="segmented-control" role="group" aria-label={t("board.viewAria")}>
          <button
            aria-pressed={view === "board"}
            className={view === "board" ? "is-active" : ""}
            onClick={() => setView("board")}
            type="button"
          >
            <Icon name="grid" size={14} />
            {t("board.board")}
          </button>
          <button
            aria-pressed={view === "list"}
            className={view === "list" ? "is-active" : ""}
            onClick={() => setView("list")}
            type="button"
          >
            <Icon name="list" size={15} />
            {t("board.list")}
          </button>
        </div>

        <div className="board-filters">
          <label className="field-search">
            <Icon name="search" size={15} />
            <input
              aria-label={t("board.searchAria")}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("board.searchPlaceholder")}
              type="search"
              value={query}
            />
          </label>
          <label className="select-field">
            <Icon name="filter" size={14} />
            <span className="sr-only">{t("board.filterProject")}</span>
            <select onChange={(event) => setProject(event.target.value)} value={project}>
              {projects.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
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
          {t("board.demoData")}
        </span>
        <span>
          {formatMessage(t("board.count"), { shown: filtered.length, total: items.length })}
          {blockedCount > 0 ? (
            <span className="caption-alert">
              <Icon name="alert" size={12} />
              {formatMessage(t("board.blocked"), { count: blockedCount })}
            </span>
          ) : null}
        </span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          actionLabel={t("board.clear")}
          compact
          description={t("board.emptyDesc")}
          eyebrow="SINAN · NO MATCH"
          onAction={() => {
            setQuery("");
            setProject(ALL_PROJECTS);
          }}
          title={t("board.emptyTitle")}
        />
      ) : view === "board" ? (
        <div className="kanban" role="region" aria-label={t("board.boardAria")}>
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
                    <h2 id={`column-${column.id}`}>{columnLabel(column.id)}</h2>
                    <span className="column-count">{columnIssues.length}</span>
                  </div>
                  <span className="column-hint">{columnHint(column.id)}</span>
                </header>

                <div className="kanban-cards">
                  {columnIssues.map((issue) => (
                    <button
                      aria-label={formatMessage(t("board.openAria"), { key: issue.key, title: issue.title })}
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
                          <span className="priority-label">{priorityLabels[issue.priority]}</span>
                        </span>
                      </span>
                      <span className="issue-card-title">{issue.title}</span>
                      {issue.blocked ? (
                        <span className="blocked-note">
                          <Icon name="alert" size={12} />
                          {t("board.blockedNote")}
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
                      {t("board.noIssues")}
                    </div>
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <section className="issue-list-panel" aria-label={t("board.listAria")}>
          <header className="issue-list-head">
            <span>{t("board.colKeyTitle")}</span>
            <span>{t("board.colProject")}</span>
            <span>{t("board.colPriority")}</span>
            <span>{t("board.colStatus")}</span>
            <span>{t("board.colAssignee")}</span>
            <span>{t("board.colUpdated")}</span>
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
                {columnLabel(issue.status)}
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
            aria-label={t("board.closeDetails")}
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
                    {t("board.blockedChip")}
                  </span>
                ) : null}
              </div>
              <button
                aria-label={t("board.close")}
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
                  <span>{t("board.status")}</span>
                  <span className="select-field">
                    <select
                      aria-label={t("board.changeStatus")}
                      onChange={(event) => moveIssue(selected.id, event.target.value as IssueStatus)}
                      value={selected.status}
                    >
                      {issueColumns.map((column) => (
                        <option key={column.id} value={column.id}>
                          {columnLabel(column.id)}
                        </option>
                      ))}
                    </select>
                    <Icon name="chevronDown" size={13} />
                  </span>
                </label>
                <div className="drawer-field">
                  <span>{t("board.colProject")}</span>
                  <strong>{selected.project}</strong>
                </div>
                <div className="drawer-field">
                  <span>{t("board.colAssignee")}</span>
                  <strong className="drawer-person">
                    <span className={`avatar avatar-xs avatar-${selected.assigneeTone}`} aria-hidden="true">
                      {selected.assignee.slice(0, 1)}
                    </span>
                    {selected.assignee}
                  </strong>
                </div>
                <div className="drawer-field">
                  <span>{t("board.colUpdated")}</span>
                  <strong>{selected.updated}</strong>
                </div>
              </div>

              <section className="drawer-section">
                <p className="section-kicker">CONTEXT</p>
                <h3>{t("board.description")}</h3>
                <p>{selected.detail}</p>
              </section>

              <section className="drawer-section">
                <p className="section-kicker">ACCEPTANCE</p>
                <h3>{t("board.acceptance")}</h3>
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
                    {t("board.linkedDoc")}
                    <Icon name="arrowRight" size={13} />
                  </Link>
                ) : null}
                {selected.repoId ? (
                  <Link href="/repos">
                    <Icon name="repos" size={15} />
                    {t("board.linkedRepo")}
                    <Icon name="arrowRight" size={13} />
                  </Link>
                ) : null}
              </section>
            </div>

            <footer className="drawer-foot">
              <span className="drawer-demo-note">{t("board.demoNote")}</span>
              <button
                className="btn btn-primary btn-sm"
                disabled={selected.status === "done"}
                onClick={() => moveIssue(selected.id, "done")}
                type="button"
              >
                <Icon name="check" size={15} />
                {selected.status === "done" ? t("issues.colDone") : t("board.markDone")}
              </button>
            </footer>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

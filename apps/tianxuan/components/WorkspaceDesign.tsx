"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { useI18n } from "@/lib/i18n-client";
import { stages, workspaceRequest, type Conversation, type Stage } from "@/lib/workspace-conversations";

const labels: Record<Stage, [string, string]> = {
  direction: ["方向", "Direction"],
  plan: ["策划", "Plan"],
  design: ["详细设计", "Detailed design"],
};

type DraftFields = { body: string; title: string; acceptance: string; basedOn?: number };

type Props = {
  conversation: Conversation;
  editable: boolean;
  busy: boolean;
  change: (action: (conversation: Conversation) => Promise<Conversation>) => Promise<void>;
};

export function WorkspaceDesign({ conversation, editable, busy, change }: Props) {
  const { locale } = useI18n();
  const zh = locale === "zh";
  const field = useId();
  const label = (stage: Stage) => labels[stage][zh ? 0 : 1];
  const active = stages.map((name) =>
    conversation.revisions.find((revision) => revision.revision === conversation.current[name]));
  const [stage, setStage] = useState<Stage>(() =>
    stages.find((_, index) => !active[index]?.confirmed_at) ?? "design");
  const index = stages.indexOf(stage);
  const revision = active[index];
  const saved = { body: revision?.body ?? "", title: revision?.title ?? "",
    acceptance: revision?.acceptance ?? "", basedOn: revision?.revision };
  const [drafts, setDrafts] = useState<Partial<Record<Stage, DraftFields>>>({});
  const local = drafts[stage];
  const { body, title, acceptance } = local ?? saved;
  const [suggesting, setSuggesting] = useState(false);
  const [suggestionError, setSuggestionError] = useState(false);
  useEffect(() => { setSuggestionError(false); }, [stage]);

  function edit(fields: Partial<DraftFields>) {
    setDrafts((previous) => ({ ...previous, [stage]: { ...(previous[stage] ?? saved), ...fields } }));
  }

  function clearLocal() {
    setDrafts((previous) => {
      const next = { ...previous };
      delete next[stage];
      return next;
    });
  }

  const validPrefix = index === 0 || active.slice(0, index).every((item) => Boolean(item?.confirmed_at));
  const canEdit = editable && !conversation.requirement_id && validPrefix;
  const locked = busy || suggesting;
  const bodyTooLong = Array.from(body).length > 8000;
  const detailsComplete = stage !== "design" || Boolean(title.trim() && acceptance.trim());
  const unsaved = stages.filter((name, position) => {
    const draft = drafts[name];
    const stored = active[position];
    return draft && (draft.body !== (stored?.body ?? "") || (name === "design" &&
      (draft.title.trim() !== (stored?.title ?? "") || draft.acceptance.trim() !== (stored?.acceptance ?? ""))));
  });
  const changed = unsaved.includes(stage);
  const prefix = `/${conversation.id}/design/${stage}`;

  async function suggest() {
    setSuggesting(true);
    setSuggestionError(false);
    try {
      const reply = await workspaceRequest<{ content: string }>(prefix + "/suggest", {
        expected_version: conversation.version, lang: locale, draft_body: body,
      });
      if (Array.from(reply.content).length > 8000) throw new Error("draft too long");
      setDrafts((previous) => {
        const current = previous[stage] ?? saved;
        return current.body === body ? { ...previous, [stage]: { ...current, body: reply.content } } : previous;
      });
    } catch {
      setSuggestionError(true);
    } finally {
      setSuggesting(false);
    }
  }

  return (
    <details className="workspace-design">
      <summary>{zh ? "将对话转为需求" : "Turn conversation into a requirement"}</summary>
      <nav aria-label={zh ? "需求确认阶段" : "Requirement stages"} className="workspace-starters">
        {stages.map((name, position) => (
          <button type="button" aria-pressed={name === stage} key={name} disabled={locked ||
            active.slice(0, position).some((item) => !item?.confirmed_at)} onClick={() => setStage(name)}>
            {label(name)}{active[position]?.confirmed_at ? (zh ? " · 已确认" : " · Confirmed") : ""}
          </button>
        ))}
      </nav>
      {local && changed && (local.basedOn !== saved.basedOn || !canEdit) && (
        <div role="status">
          <p>{zh ? "该阶段已更新。你的本地草稿已保留，可核对已保存的内容。" :
            "This stage has changed. Your local draft is available to compare with the saved version."}</p>
          <pre>{[saved.title, saved.body, saved.acceptance].filter(Boolean).join("\n\n")}</pre>
          {!canEdit && <pre>{[title, body, acceptance].filter(Boolean).join("\n\n")}</pre>}
          <button type="button" disabled={locked} onClick={clearLocal}>{zh ? "采用已保存版本" : "Use saved version"}</button>
        </div>
      )}
      {canEdit ? (
        <div className="workspace-stage-editor">
          {stage === "design" && <div className="workspace-stage-field">
            <label htmlFor={`${field}-title`}>{zh ? "需求标题" : "Requirement title"}</label>
            <input id={`${field}-title`} value={title} readOnly={busy} maxLength={150} onChange={(event) => edit({ title: event.target.value })} />
          </div>}
          <div className="workspace-stage-field">
            <label htmlFor={`${field}-body`}>{label(stage)}</label>
            <textarea id={`${field}-body`} rows={5} value={body} readOnly={busy} aria-invalid={bodyTooLong}
              onChange={(event) => edit({ body: event.target.value })} />
          </div>
          {stage === "design" && <div className="workspace-stage-field">
            <label htmlFor={`${field}-acceptance`}>{zh ? "验收标准" : "Acceptance criteria"}</label>
            <textarea id={`${field}-acceptance`} rows={3} value={acceptance} readOnly={busy} maxLength={8000}
              onChange={(event) => edit({ acceptance: event.target.value })} />
          </div>}
          <div className="workspace-starters">
            <button type="button" disabled={locked || bodyTooLong} onClick={suggest}>
              {suggesting ? (zh ? "生成中…" : "Drafting…") : body.trim()
                ? (zh ? "从对话补充草稿" : "Extend draft from conversation")
                : (zh ? "从对话生成草稿" : "Draft from conversation")}
            </button>
            <button type="button" disabled={locked || bodyTooLong || !changed || !body.trim() || !detailsComplete}
              onClick={() => void change(async (current) => {
                const result = await workspaceRequest<Conversation>(prefix + "/drafts", {
                  expected_version: current.version, body,
                  ...(stage === "design" ? { title, acceptance } : {}),
                });
                clearLocal();
                return result;
              })}>
              {zh ? "保存新版本" : "Save new revision"}
            </button>
            {revision && !revision.confirmed_at && (
              <button type="button" disabled={locked || changed} onClick={async () => {
                await change((current) => workspaceRequest(prefix + "/confirm", {
                  expected_version: current.version, revision: revision.revision,
                }));
              }}>
                {zh ? `确认版本 ${revision.revision}` : `Confirm revision ${revision.revision}`}
              </button>
            )}
          </div>
          {bodyTooLong && <p role="alert">{zh ? "草稿超过 8000 字符，请缩短后继续。" : "Shorten the draft to 8,000 characters to continue."}</p>}
          {suggestionError && <p role="alert">{zh ? "无法生成草稿。你可以直接填写。" : "Drafting failed. You can edit the draft here."}</p>}
          {revision?.confirmed_at && changed && index < stages.length - 1 && active[index + 1] && (
            <p>{zh ? "保存此修订后，后续阶段需要重新确认。" : "Saving this revision requires downstream stages to be confirmed again."}</p>
          )}
        </div>
      ) : revision && <p className="workspace-revision-body">{revision.body}</p>}
      {conversation.revisions.some((item) => item.stage === stage) && (
        <details className="workspace-revisions">
          <summary>{zh ? "版本历史" : "Revision history"}</summary>
          {conversation.revisions.filter((item) => item.stage === stage).slice().reverse().map((item) => (
            <details key={item.revision}>
              <summary>{zh ? `版本 ${item.revision}` : `Revision ${item.revision}`}
                {item.confirmed_at && (zh ? " · 曾确认" : " · Confirmed")}
                {item.revision === revision?.revision && (zh ? " · 当前" : " · Current")}
              </summary>
              {item.title && <strong>{item.title}</strong>}
              <p className="workspace-revision-body">{item.body}</p>
              {item.acceptance && <p className="workspace-revision-body">{item.acceptance}</p>}
            </details>
          ))}
        </details>
      )}
      {conversation.requirement_id ? (
        <Link className="text-link" href={`/docs/${encodeURIComponent(conversation.requirement_id)}`}>
          {zh ? "打开已保存需求" : "Open saved requirement"}
        </Link>
      ) : editable && active.every((item) => Boolean(item?.confirmed_at)) && (
        <button type="button" className="btn btn-ghost" disabled={locked || unsaved.length > 0}
          onClick={() => void change((current) => workspaceRequest(`/${current.id}/requirement`, {
            expected_version: current.version, lang: locale,
          }))}>
          {zh ? "保存需求" : "Save requirement"}
        </button>
      )}
    </details>
  );
}

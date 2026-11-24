"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { useIdentity } from "@/components/IdentityProvider";
import { WorkspaceDesign } from "@/components/WorkspaceDesign";
import { WorkspaceExecution } from "@/components/WorkspaceExecution";
import { useI18n } from "@/lib/i18n-client";
import {
  WorkspaceRequestError, workspaceRequest,
  type Conversation, type ConversationPage, type Summary,
} from "@/lib/workspace-conversations";

export function AICommandBar() {
  const identity = useIdentity();
  return <ConversationPanel key={identity?.id ?? "signed-out"} identity={identity} />;
}

function ConversationPanel({ identity }: { identity: ReturnType<typeof useIdentity> }) {
  const { locale, t } = useI18n();
  const zh = locale === "zh";
  const identityId = identity?.id;
  const editable = Boolean(identity && identity.role !== "viewer");
  const starters = [
    ["ai.starterDraft", "ai.starterDraftPrompt"],
    ["ai.starterSplit", "ai.starterSplitPrompt"],
    ["ai.starterWeekly", "ai.starterWeeklyPrompt"],
  ] as const;
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const working = useRef(false);
  const [draft, setDraft] = useState("");
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(identity));
  const [busy, setBusy] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState<number | "connection" | null>(null);
  const pending = conversation?.turns.find((turn) => turn.state === "pending");
  const lastTurn = conversation?.turns.at(-1);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [conversation?.id, lastTurn?.id, lastTurn?.state]);

  useEffect(() => {
    if (!identityId) return;
    let active = true;
    async function load() {
      try {
        const page = await workspaceRequest<ConversationPage>();
        const latest = page.conversations[0]
          ? await workspaceRequest<Conversation>(`/${page.conversations[0].id}`)
          : null;
        if (active) {
          setSummaries(page.conversations);
          setCursor(page.next);
          setConversation(latest);
        }
      } catch {
        if (active) setLoadFailed(true);
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [identityId]);

  function remember(value: Conversation) {
    setConversation(value);
    const { id, title, updated_at } = value;
    setSummaries((previous) => [{ id, title, updated_at }, ...previous.filter((item) => item.id !== id)]);
  }

  async function useWorkspace(action: () => Promise<void>) {
    if (working.current) return;
    working.current = true;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (failure) {
      setError(failure instanceof WorkspaceRequestError ? failure.status : "connection");
    } finally {
      working.current = false;
      setBusy(false);
    }
  }

  async function select(value: string) {
    if (!value) {
      setConversation(null);
      setError(null);
      setDraft("");
      input.current?.focus();
      return;
    }
    await useWorkspace(async () => {
      setConversation(await workspaceRequest<Conversation>(`/${value}`));
      setDraft("");
    });
  }

  async function more() {
    if (!cursor) return;
    await useWorkspace(async () => {
      const page = await workspaceRequest<ConversationPage>(`?before=${encodeURIComponent(cursor)}`);
      setSummaries((previous) => {
        const known = new Set(previous.map((item) => item.id));
        return [...previous, ...page.conversations.filter((item) => !known.has(item.id))];
      });
      setCursor(page.next);
    });
  }

  async function refresh() {
    await useWorkspace(async () => {
      const page = await workspaceRequest<ConversationPage>();
      const key = conversation?.id ?? page.conversations[0]?.id;
      const current = key ? await workspaceRequest<Conversation>(`/${key}`) : null;
      if (current && !page.conversations.some((item) => item.id === current.id)) {
        const { id, title, updated_at } = current;
        page.conversations.push({ id, title, updated_at });
      }
      setConversation(current);
      setSummaries(page.conversations);
      setCursor(page.next);
      setLoadFailed(false);
    });
  }

  async function change(action: (current: Conversation) => Promise<Conversation>) {
    if (!conversation) return;
    await useWorkspace(async () => {
      try {
        remember(await action(conversation));
      } catch (failure) {
        if (failure instanceof WorkspaceRequestError && failure.status === 409) {
          remember(await workspaceRequest<Conversation>(`/${conversation.id}`));
        }
        throw failure;
      }
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!editable || !content || working.current || pending || loading || loadFailed) return;
    await useWorkspace(async () => {
      const current = conversation ??
        await workspaceRequest<Conversation>("", { id: crypto.randomUUID() });
      if (!conversation) remember(current);
      const id = crypto.randomUUID();
      try {
        const result = await workspaceRequest<Conversation>(`/${current.id}/turns`, {
          id, content, expected_version: current.version,
        });
        remember(result);
        setDraft("");
      } catch (failure) {
        // A lost HTTP response can follow a committed turn. Read back before
        // presenting another send and let the user resolve a pending receipt.
        try {
          const observed = await workspaceRequest<Conversation>(`/${current.id}`);
          remember(observed);
          if (observed.turns.some((turn) => turn.id === id)) {
            setDraft("");
            return;
          }
        } catch {
          setLoadFailed(true);
        }
        throw failure;
      }
    });
    input.current?.focus();
  }

  const errorMessage = error === 409
    ? (zh ? "会话已更新，请核对当前版本后继续。" : "The conversation changed. Review the current version.")
    : (zh ? "暂时无法完成此操作，已保存内容可刷新查看。" : "The action could not finish. Refresh to check saved content.");

  return (
    <section className="workspace-card workspace-chat" aria-labelledby="workspace-chat-title">
      <header className="workspace-chat-header">
        <h2 id="workspace-chat-title"><span className="workspace-ai-symbol"><Icon name="sparkles" size={23} /></span>{zh ? "AI 对话" : "AI conversation"}</h2>
        {editable && (conversation || summaries.length > 0) && <button className="workspace-refresh" type="button"
          disabled={busy || loading} onClick={() => void select("")}>{zh ? "新对话" : "New conversation"}</button>}
      </header>
      {identity && <div className="workspace-conversation-nav">
        {summaries.length > 0 && (
          <select aria-label={zh ? "对话历史" : "Conversation history"} className="theme-select"
            value={conversation?.id ?? ""} disabled={busy || loading} onChange={(event) => void select(event.target.value)}>
            <option value="">{zh ? "新对话" : "New conversation"}</option>
            {summaries.map((item) => <option key={item.id} value={item.id}>
              {item.title || (zh ? "未命名对话" : "Untitled conversation")}
            </option>)}
          </select>
        )}
        {cursor && <button type="button" className="workspace-refresh" disabled={busy} onClick={more}>
          {zh ? "更多对话" : "More conversations"}
        </button>}
        {(pending || loadFailed) && <button type="button" className="workspace-refresh" disabled={busy} onClick={refresh}>
          {zh ? "刷新对话" : "Refresh conversation"}
        </button>}
      </div>}
      {busy && <p role="status">{zh ? "正在处理…" : "Working…"}</p>}
      {loading && <p role="status">{zh ? "正在读取对话…" : "Loading conversations…"}</p>}
      {loadFailed && <p role="alert">{zh ? "暂时无法读取会话，请刷新。" : "Conversations could not be read. Refresh to try again."}</p>}
      <div ref={log} role="log" aria-label={zh ? "对话记录" : "Conversation log"}
        tabIndex={lastTurn ? 0 : undefined} className="workspace-chat-history">
        {conversation?.turns.map((turn) => <div key={turn.id} className="workspace-turn">
          <article className="workspace-message workspace-message-user">
            <strong>{zh ? "你" : "You"}</strong><p>{turn.content}</p>
          </article>
          {turn.state === "answered" && <article className="workspace-message workspace-message-assistant">
            <strong>{turn.model || "AI"}</strong><p>{turn.answer}</p>
          </article>}
          {turn.state === "pending" && <p role="status">
            {zh ? "等待已发送消息的回执。" : "Waiting for the submitted message."}
          </p>}
          {turn.state === "unanswered" && <p className="workspace-error">
            {turn.error === 503
              ? (zh ? "消息已保存。此部署尚未接通对话模型。" : "Message saved. This deployment has no chat model configured.")
              : turn.error === 429
                ? (zh ? "消息已保存。模型额度不足。" : "Message saved. The model budget has been reached.")
                : (zh ? "消息已保存，本轮没有可读取的模型回复。" : "Message saved. No model reply is available for this turn.")}
          </p>}
        </div>)}
      </div>
      {pending && editable && <button type="button" className="workspace-refresh" disabled={busy}
        onClick={() => void change((current) => workspaceRequest(`/${current.id}/turns/${pending.id}/stop-waiting`, {
          expected_version: current.version,
        }))}>
        {zh ? "停止等待此回复" : "Stop waiting for this reply"}
      </button>}
      {editable ? (
        <>
          <form className="workspace-composer" onSubmit={submit}>
            <label htmlFor="workspace-chat-input" className="sr-only">{t("ai.inputLabel")}</label>
            <textarea id="workspace-chat-input" ref={input} rows={2} maxLength={8000}
              readOnly={busy || loading || loadFailed || Boolean(pending)} value={draft}
              placeholder={zh ? "描述需求，或提出开发问题…" : "Describe a requirement or ask a development question…"}
              onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }} />
            <button type="submit" className="workspace-send"
              disabled={!draft.trim() || busy || loading || loadFailed || Boolean(pending)}
              aria-label={zh ? "发送消息" : "Send message"}>
              <Icon name="arrowUp" size={20} />
            </button>
          </form>
          {!conversation?.turns.length && <div className="workspace-starters">
            {starters.map(([label, prompt]) => (
              <button type="button" key={label} disabled={busy || loading || loadFailed} onClick={() => {
                setDraft(t(prompt));
                input.current?.focus();
              }}>{t(label)}</button>
            ))}
          </div>}
        </>
      ) : identity ? <p>{zh ? "当前账号为只读。" : "Your account is read-only."}</p>
        : <div className="workspace-welcome">
            <p>{zh ? "登录后可以继续已有对话、起草需求并查看执行进度。" :
              "Sign in to resume a conversation, draft a requirement, and follow its execution."}</p>
            <Link className="workspace-signin" href="/login">{zh ? "登录后开始对话" : "Sign in to start a conversation"}</Link>
          </div>}
      {error && <p role="alert" className="workspace-error">{errorMessage}</p>}
      {conversation && conversation.turns.length > 0 && (
        <WorkspaceDesign key={`design-${conversation.id}`} conversation={conversation}
          editable={editable && !loadFailed} busy={busy} change={change} />
      )}
      {conversation?.requirement_id && (
        <WorkspaceExecution key={`execution-${conversation.id}`} conversation={conversation}
          editable={editable && !loadFailed} busy={busy} change={change} />
      )}
    </section>
  );
}

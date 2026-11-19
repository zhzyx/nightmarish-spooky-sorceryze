"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { useIdentity } from "@/components/IdentityProvider";
import { useI18n } from "@/lib/i18n-client";

type Message = { role: "user" | "assistant"; content: string };

const chatErrorCodes: Record<number, string> = {
  400: "invalid_messages", 401: "session_required", 403: "chat_forbidden",
  404: "chat_unconfigured", 422: "invalid_messages", 429: "chat_budget", 503: "chat_unconfigured",
};

const chatErrors: Record<string, [string, string]> = {
  session_required: ["登录已失效，请重新登录。", "Your session expired. Sign in again."],
  chat_forbidden: ["当前账号没有发送消息的权限。", "Your account cannot send messages."],
  chat_unconfigured: ["此部署尚未配置对话模型。", "This deployment has no chat model configured."],
  chat_budget: ["模型额度不足。", "The model budget has been reached."],
  invalid_messages: ["消息超出支持范围，请开始新对话。", "The message exceeds supported limits. Start a new conversation."],
  chat_failed: ["未收到模型回复，消息已保留在输入框。", "No reply was received. Your draft is still in the composer."],
};

export function AICommandBar() {
  const identity = useIdentity();
  const { locale, t } = useI18n();
  const zh = locale === "zh";
  const input = useRef<HTMLTextAreaElement>(null);
  const requestPending = useRef(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [model, setModel] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!identity || identity.role === "viewer" || !content || requestPending.current) return;
    requestPending.current = true;
    setPending(true);
    setError("");
    const userMessage: Message = { role: "user", content };
    try {
      const context = [...messages.slice(-24), userMessage];
      const response = await fetch("/api/v1/workspace/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: context }),
      });
      if (!response.ok) {
        setError(chatErrorCodes[response.status] ?? "chat_failed");
        return;
      }
      const result = await response.json();
      if (typeof result.content !== "string" || !result.content.trim() || typeof result.model !== "string") {
        setError("chat_failed");
        return;
      }
      setMessages([...messages, userMessage, { role: "assistant", content: result.content }]);
      setModel(result.model);
      setDraft("");
    } catch {
      setError("chat_failed");
    } finally {
      requestPending.current = false;
      setPending(false);
      input.current?.focus();
    }
  }

  function reset() {
    setMessages([]);
    setModel("");
    setError("");
    setDraft("");
    input.current?.focus();
  }

  const starterKeys = [
    ["ai.starterDraft", "ai.starterDraftPrompt"],
    ["ai.starterSplit", "ai.starterSplitPrompt"],
    ["ai.starterWeekly", "ai.starterWeeklyPrompt"],
  ] as const;

  return (
    <section className="workspace-card workspace-chat" aria-labelledby="workspace-chat-title">
      <header className="workspace-chat-header">
        <h2 id="workspace-chat-title"><Icon name="sparkles" size={18} />{zh ? "AI 对话" : "AI conversation"}</h2>
        {messages.length > 0 && <button className="workspace-refresh" type="button"
          disabled={pending} onClick={reset}>{zh ? "新对话" : "New conversation"}</button>}
      </header>
      <div role="log" aria-label={zh ? "对话记录" : "Conversation history"} className="workspace-chat-history">
        {messages.map((message, index) => (
          <article className={`workspace-message workspace-message-${message.role}`} key={index}>
            <strong>{message.role === "user" ? (zh ? "你" : "You") : "AI"}</strong>
            <p>{message.content}</p>
          </article>
        ))}
      </div>
      {identity && identity.role !== "viewer" ? (
        <>
          <form className="workspace-composer" onSubmit={submit}>
            <label htmlFor="workspace-chat-input" className="sr-only">{t("ai.inputLabel")}</label>
            <textarea id="workspace-chat-input" ref={input} rows={2} maxLength={8000}
              readOnly={pending} value={draft} placeholder={zh ? "输入消息…" : "Type a message…"}
              onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }} />
            <button type="submit" className="workspace-send" disabled={!draft.trim() || pending}
              aria-label={zh ? "发送消息" : "Send message"}>
              <Icon name="arrowUp" size={20} />
            </button>
          </form>
          {messages.length === 0 && <div className="workspace-starters">
            {starterKeys.map(([label, prompt]) => (
              <button type="button" key={label} disabled={pending} onClick={() => {
                setDraft(t(prompt));
                input.current?.focus();
              }}>{t(label)}</button>
            ))}
          </div>}
        </>
      ) : identity ? <p>{zh ? "当前账号为只读。" : "Your account is read-only."}</p>
        : <Link className="text-link" href="/login">{zh ? "登录后开始对话" : "Sign in to start a conversation"}</Link>}
      {pending && <p role="status">{zh ? "正在等待模型回复…" : "Waiting for the model…"}</p>}
      {error && <p role="alert" className="workspace-error">{chatErrors[error][zh ? 0 : 1]}</p>}
      {model && <p className="workspace-model">{model}</p>}
    </section>
  );
}

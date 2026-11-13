"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Icon } from "@/components/Icon";

const starterPrompts = [
  {
    label: "起草需求",
    prompt: "根据最近的设计讨论，起草一份「文档块级协同」需求。",
  },
  {
    label: "拆分工单",
    prompt: "把天璇平台基线拆成可独立交付的工单，并标注依赖。",
  },
  {
    label: "生成周报",
    prompt: "汇总本周文档、工单与仓库进展，形成一页周报。",
  },
  {
    label: "查找风险",
    prompt: "检查当前迭代里没有验收证据的工单和阻塞项。",
  },
];

const planSteps = [
  "读取工作区上下文：4 个空间、8 份近期文档、9 个未闭环工单。",
  "整理为一份带来源引用的行动草案，标注责任人、依赖与验收条件。",
  "等待人工确认后，再写入偃师需求或司南工单。",
];

export function AICommandBar() {
  const formRef = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [prompt, setPrompt] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null);

  function runCommand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = prompt.trim();
    if (!value) {
      inputRef.current?.focus();
      return;
    }
    setSubmittedPrompt(value);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  function useStarter(value: string) {
    setPrompt(value);
    setSubmittedPrompt(null);
    inputRef.current?.focus();
  }

  return (
    <section className="ai-command" aria-labelledby="ai-command-title">
      <div className="ai-command-glow" aria-hidden="true" />
      <div className="ai-command-head">
        <div className="ai-identity">
          <span className="ai-orb" aria-hidden="true">
            <Icon name="sparkles" size={16} />
          </span>
          <div>
            <p className="ai-kicker">TIANXUAN INTELLIGENCE</p>
            <h2 id="ai-command-title">今天，想推进什么？</h2>
          </div>
        </div>
        <span className="prototype-pill">
          <span className="prototype-dot" aria-hidden="true" />
          原型演示 · 未连接模型
        </span>
      </div>

      <form className="ai-command-form" onSubmit={runCommand} ref={formRef}>
        <label className="sr-only" htmlFor="ai-command-input">
          向天璇描述要推进的工作
        </label>
        <textarea
          id="ai-command-input"
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="告诉天璇你想推进什么，例如：整理本周验收证据，生成司南工单…"
          ref={inputRef}
          rows={2}
          value={prompt}
        />
        <button className="ai-run-button" type="submit">
          <span>运行</span>
          <span className="ai-run-icon">
            <Icon name="arrowUp" size={16} />
          </span>
        </button>
      </form>

      <div className="ai-command-foot">
        <div className="prompt-chips" aria-label="快捷指令">
          {starterPrompts.map((starter) => (
            <button
              className="prompt-chip"
              key={starter.label}
              onClick={() => useStarter(starter.prompt)}
              type="button"
            >
              <span aria-hidden="true">/</span>
              {starter.label}
            </button>
          ))}
        </div>
        <span className="ai-context">
          <Icon name="layers" size={14} />
          已带入工作区上下文
        </span>
      </div>

      <div aria-live="polite">
        {submittedPrompt ? (
          <div className="ai-plan">
            <div className="ai-plan-head">
              <span className="status-tag status-tag-gold">
                <span className="status-dot" aria-hidden="true" />
                计划草稿
              </span>
              <span className="ai-plan-note">仅界面预览，不会写入数据</span>
              <button
                aria-label="收起计划草稿"
                className="quiet-icon-button"
                onClick={() => setSubmittedPrompt(null)}
                type="button"
              >
                <Icon name="close" size={15} />
              </button>
            </div>
            <p className="ai-plan-request">{submittedPrompt}</p>
            <ol className="ai-plan-steps">
              {planSteps.map((step, index) => (
                <li key={step}>
                  <span className="plan-index">{String(index + 1).padStart(2, "0")}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            <div className="ai-plan-actions">
              <Link className="text-link" href="/requirements">
                打开需求工作台
                <Icon name="arrowRight" size={14} />
              </Link>
              <span className="ai-plan-context">建议来源将在此处逐条列出</span>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

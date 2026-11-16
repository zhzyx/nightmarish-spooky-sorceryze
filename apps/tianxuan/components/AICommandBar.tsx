"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Icon } from "@/components/Icon";
import { useI18n } from "@/lib/i18n-client";

export function AICommandBar() {
  const { t } = useI18n();
  const formRef = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [prompt, setPrompt] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null);

  const starterPrompts = [
    { label: t("ai.starterDraft"), prompt: t("ai.starterDraftPrompt") },
    { label: t("ai.starterSplit"), prompt: t("ai.starterSplitPrompt") },
    { label: t("ai.starterWeekly"), prompt: t("ai.starterWeeklyPrompt") },
    { label: t("ai.starterRisks"), prompt: t("ai.starterRisksPrompt") },
  ];
  const planSteps = [t("ai.step1"), t("ai.step2"), t("ai.step3")];

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
            <h2 id="ai-command-title">{t("ai.title")}</h2>
          </div>
        </div>
        <span className="prototype-pill">
          <span className="prototype-dot" aria-hidden="true" />
          {t("ai.prototype")}
        </span>
      </div>

      <form className="ai-command-form" onSubmit={runCommand} ref={formRef}>
        <label className="sr-only" htmlFor="ai-command-input">
          {t("ai.inputLabel")}
        </label>
        <textarea
          id="ai-command-input"
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("ai.placeholder")}
          ref={inputRef}
          rows={2}
          value={prompt}
        />
        <button className="ai-run-button" type="submit">
          <span>{t("ai.run")}</span>
          <span className="ai-run-icon">
            <Icon name="arrowUp" size={16} />
          </span>
        </button>
      </form>

      <div className="ai-command-foot">
        <div className="prompt-chips" aria-label={t("ai.quickAria")}>
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
          {t("ai.context")}
        </span>
      </div>

      <div aria-live="polite">
        {submittedPrompt ? (
          <div className="ai-plan">
            <div className="ai-plan-head">
              <span className="status-tag status-tag-gold">
                <span className="status-dot" aria-hidden="true" />
                {t("ai.planDraft")}
              </span>
              <span className="ai-plan-note">{t("ai.planNote")}</span>
              <button
                aria-label={t("ai.collapseAria")}
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
                {t("ai.openRequirements")}
                <Icon name="arrowRight" size={14} />
              </Link>
              <span className="ai-plan-context">{t("ai.planContext")}</span>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

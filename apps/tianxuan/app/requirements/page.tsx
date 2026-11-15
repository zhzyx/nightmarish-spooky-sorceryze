import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import {
  getDoc,
  requirements,
  type RequirementStatus,
} from "@/lib/data";
import {
  fetchRequirementProgress,
  fetchRequirements,
  type ApiRequirement,
  type ApiRequirementProgress,
} from "@/lib/requirements-api";
import { LOCALE_COOKIE, formatMessage, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "req.title") };
}

// 实时需求依赖每次请求的 TIANXUAN_ACTOR，禁用静态化。
export const dynamic = "force-dynamic";

const LIVE_REQUIREMENT_LIMIT = 8;

const statusClass: Record<RequirementStatus, string> = {
  澄清中: "is-clarifying",
  已成稿: "is-ready",
  拆单中: "is-split",
  已拆单: "is-split",
  已验收: "is-accepted",
};



/** 把后端百分比收敛到 0–100 的整数，避免异常值撑破进度条。 */
function normalizePercent(progress: ApiRequirementProgress | null | undefined): number {
  const percent = Number(progress?.percent);
  if (!Number.isFinite(percent)) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round(percent)));
}

/**
 * 读取实时需求：先取列表，再并行为前 8 条回读详情（进度与 request_id）。
 *
 * 任意一次请求失败都会向上抛出，由页面静默回退到示例数据。
 */
async function loadLiveRequirements(actor: string): Promise<ApiRequirement[]> {
  const listed = await fetchRequirements(actor);
  const head = listed.slice(0, LIVE_REQUIREMENT_LIMIT);
  return Promise.all(
    head.map(async (requirement) => {
      const detail = await fetchRequirementProgress(actor, requirement.id);
      return {
        ...requirement,
        request_id: detail.request_id ?? requirement.request_id ?? null,
        progress: detail.progress ?? requirement.progress ?? null,
      };
    }),
  );
}

export default async function RequirementsPage() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);
  const flowSteps = [
    { index: "01", title: t("req.step1Title"), copy: t("req.step1Copy") },
    { index: "02", title: t("req.step2Title"), copy: t("req.step2Copy") },
    { index: "03", title: t("req.step3Title"), copy: t("req.step3Copy") },
    { index: "04", title: t("req.step4Title"), copy: t("req.step4Copy") },
  ];
  const actor = process.env.TIANXUAN_ACTOR?.trim() ?? "";
  let liveRequirements: ApiRequirement[] = [];
  if (actor || process.env.TIANXUAN_TOKEN) {
    try {
      liveRequirements = await loadLiveRequirements(actor);
    } catch {
      // 后端不可用时静默回退到示例数据，保持页面结构与文案不变。
      liveRequirements = [];
    }
  }

  const clarifying = requirements.filter((requirement) => requirement.status === "澄清中").length;
  const drafted = requirements.filter((requirement) => requirement.status === "已成稿").length;
  const accepted = requirements.filter((requirement) => requirement.status === "已验收").length;
  const tickets = requirements.reduce(
    (total, requirement) => ({
      done: total.done + requirement.ticketsDone,
      all: total.all + requirement.ticketsTotal,
    }),
    { done: 0, all: 0 },
  );

  return (
    <div className="page-stack requirements-page">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            YANSHI · REQUIREMENTS
          </p>
          <h1>
            {t("req.title")}
            {locale === "zh" ? <span className="title-period">。</span> : null}
          </h1>
          <p className="page-lede">{t("req.lede")}</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/docs/tianxuan-platform">
            <Icon name="docs" size={16} />
            {t("req.designBaseline")}
          </Link>
          <Link className="btn btn-primary" href="/">
            <Icon name="sparkles" size={16} />
            {t("req.draft")}
          </Link>
        </div>
      </header>

      {liveRequirements.length > 0 ? (
        <section className="panel" aria-labelledby="live-requirements-title">
          <header className="panel-head">
            <div>
              <p className="section-kicker">LIVE API</p>
              <h2 id="live-requirements-title">{t("req.liveTitle")}</h2>
            </div>
            <span className="section-note">{formatMessage(t("req.liveNote"), { count: liveRequirements.length })}</span>
          </header>

          <div className="reading-list live-list">
            {liveRequirements.map((requirement, index) => {
              const percent = normalizePercent(requirement.progress);
              return (
                <Link className="reading-item" href={`/docs/${requirement.id}`} key={requirement.id}>
                  <span className="reading-index">{String(index + 1).padStart(2, "0")}</span>
                  <span className="reading-copy">
                    <strong>{requirement.title}</strong>
                    <span>
                      {requirement.request_id ? formatMessage(t("req.requestPrefix"), { id: requirement.request_id }) : ""}
                      v{requirement.version} · {requirement.status}
                    </span>
                    <span className="meter" aria-hidden="true">
                      <span style={{ width: `${percent}%` }} />
                    </span>
                    <span>
                      {requirement.progress
                        ? formatMessage(t("req.progress"), {
                            done: requirement.progress.done,
                            total: requirement.progress.total,
                            percent,
                          })
                        : t("req.progressPending")}
                    </span>
                  </span>
                  <Icon name="chevronRight" size={14} />
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="requirement-hero">
        <div className="requirement-hero-copy">
          <p className="section-kicker">REQUIREMENT INTAKE</p>
          <h2>
            {t("req.heroA")}
            <br />
            <span>{t("req.heroB")}</span>
          </h2>
          <p>{t("req.heroLede")}</p>
          <div className="requirement-hero-tags">
            <span>
              <Icon name="sparkles" size={13} />
              {t("req.autoDraft")}
            </span>
            <span>
              <Icon name="link" size={13} />
              {t("req.bidirectional")}
            </span>
            <span>
              <Icon name="shield" size={13} />
              {t("req.human")}
            </span>
          </div>
        </div>

        <div className="requirement-flow" aria-label={t("req.flowAria")}>
          {flowSteps.map((step, index) => (
            <div className="flow-step" key={step.index}>
              <span className="flow-index">{step.index}</span>
              <div>
                <strong>{step.title}</strong>
                <p>{step.copy}</p>
              </div>
              {index < flowSteps.length - 1 ? <span className="flow-connector" aria-hidden="true" /> : null}
            </div>
          ))}
        </div>

        <span className="requirement-hero-watermark" aria-hidden="true">
          需
        </span>
      </section>

      <section className="requirement-stats" aria-label={t("req.statsAria")}>
        <div className="requirement-stat">
          <span className="requirement-stat-label">{t("req.pool")}</span>
          <strong>{String(requirements.length).padStart(2, "0")}</strong>
          <small>{t("req.demoEntries")}</small>
        </div>
        <div className="requirement-stat">
          <span className="requirement-stat-label">{t("req.clarifying")}</span>
          <strong>{String(clarifying).padStart(2, "0")}</strong>
          <small>{t("req.clarifyingNote")}</small>
        </div>
        <div className="requirement-stat">
          <span className="requirement-stat-label">{t("req.drafted")}</span>
          <strong>{String(drafted).padStart(2, "0")}</strong>
          <small>{t("req.draftedNote")}</small>
        </div>
        <div className="requirement-stat">
          <span className="requirement-stat-label">{t("req.issueProgress")}</span>
          <strong>
            {tickets.done}
            <span>/{tickets.all}</span>
          </strong>
          <small>{formatMessage(t("req.acceptedCount"), { count: accepted })}</small>
        </div>
      </section>

      <div className="requirements-layout">
        <section className="panel requirement-pool" aria-labelledby="requirement-pool-title">
          <header className="panel-head">
            <div>
              <p className="section-kicker">THE POOL</p>
              <h2 id="requirement-pool-title">{t("req.pool")}</h2>
            </div>
            <span className="section-note">{t("req.sorted")}</span>
          </header>

          <div className="req-table-head" aria-hidden="true">
            <span>{t("req.colRequirement")}</span>
            <span>{t("req.colProgress")}</span>
            <span>{t("req.colIssues")}</span>
            <span>{t("req.colOwner")}</span>
            <span>{t("req.colStatus")}</span>
          </div>

          <div className="requirement-list">
            {requirements.map((requirement) => {
              const doc = getDoc(requirement.docId);
              return (
                <Link className="requirement-row" href={`/docs/${requirement.docId}`} key={requirement.id}>
                  <span className="req-main">
                    <span className="req-id">
                      {requirement.id}
                      <span className={`req-status ${statusClass[requirement.status]}`}>
                        <span className="status-dot" aria-hidden="true" />
                        {requirement.status}
                      </span>
                    </span>
                    <span className="req-title">{requirement.title}</span>
                    <span className="req-summary">{requirement.summary}</span>
                    <span className="req-link-doc">
                      <Icon name="docs" size={12} />
                      {doc ? doc.title : t("req.linkedDoc")}
                    </span>
                  </span>

                  <span className="req-progress">
                    <span className="req-progress-value">
                      <strong>{requirement.progress}%</strong>
                      <span>{requirement.updated}</span>
                    </span>
                    <span className={`meter tone-${requirement.tone}`} aria-hidden="true">
                      <span style={{ width: `${requirement.progress}%` }} />
                    </span>
                  </span>

                  <span className="req-tickets">
                    <strong>{requirement.ticketsDone}</strong>
                    <span>/{requirement.ticketsTotal}</span>
                    <small>{t("req.ticketsSuffix")}</small>
                  </span>

                  <span className="req-owner">
                    <span className={`avatar avatar-sm avatar-${requirement.tone}`} aria-hidden="true">
                      {requirement.owner.slice(0, 1)}
                    </span>
                    <span>{requirement.owner}</span>
                  </span>

                  <span className={`req-status req-status-wide ${statusClass[requirement.status]}`}>
                    <span className="status-dot" aria-hidden="true" />
                    {requirement.status}
                  </span>

                  <Icon className="req-arrow" name="chevronRight" size={15} />
                </Link>
              );
            })}
          </div>

          <footer className="panel-foot">
            <span>
              <Icon name="link" size={14} />
              {t("req.footerDoc")}
            </span>
            <span>{t("req.synced")}</span>
          </footer>
        </section>

        <aside className="requirements-side">
          <section className="panel yanshi-card" aria-labelledby="yanshi-title">
            <header className="yanshi-head">
              <span className="agent-orb" aria-hidden="true">
                偃
              </span>
              <span>
                <strong id="yanshi-title">偃师</strong>
                <small>
                  <span className="live-dot" aria-hidden="true" />
                  {t("req.yanshiAgent")}
                </small>
              </span>
              <Icon className="yanshi-mark" name="sparkles" size={18} />
            </header>
            <p className="yanshi-intro">
              {t("req.yanshiIntro")}
            </p>
            <div className="suggestion-list">
              <div className="suggestion">
                <span className="suggestion-index">01</span>
                <span>
                  <strong>{t("req.suggestion1")}</strong>
                  <small>{t("req.suggestion1Note")}</small>
                </span>
                <Icon name="chevronRight" size={14} />
              </div>
              <div className="suggestion">
                <span className="suggestion-index">02</span>
                <span>
                  <strong>{t("req.suggestion2")}</strong>
                  <small>{t("req.suggestion2Note")}</small>
                </span>
                <Icon name="chevronRight" size={14} />
              </div>
            </div>
            <Link className="text-link yanshi-link" href="/docs/ai-native-docs">
              {t("req.viewSource")}
              <Icon name="arrowRight" size={14} />
            </Link>
          </section>

          <section className="panel requirement-guide" aria-labelledby="guide-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">GOOD REQUIREMENT</p>
                <h2 id="guide-title">{t("req.guideTitle")}</h2>
              </div>
              <Icon className="panel-head-icon" name="requirements" size={18} />
            </header>
            <ul className="guide-list">
              <li>
                <span className="guide-index">壹</span>
                <span>
                  <strong>{t("req.guideScope")}</strong>
                  <small>{t("req.guideScopeNote")}</small>
                </span>
              </li>
              <li>
                <span className="guide-index">贰</span>
                <span>
                  <strong>{t("req.guideAccept")}</strong>
                  <small>{t("req.guideAcceptNote")}</small>
                </span>
              </li>
              <li>
                <span className="guide-index">叁</span>
                <span>
                  <strong>{t("req.guideOrder")}</strong>
                  <small>{t("req.guideOrderNote")}</small>
                </span>
              </li>
            </ul>
          </section>

          <section className="aside-quote aside-quote-warm">
            <span className="aside-quote-mark" aria-hidden="true">
              〝
            </span>
            <p>{t("req.quote")}</p>
            <span>{t("req.quoteCaption")}</span>
          </section>
        </aside>
      </div>
    </div>
  );
}

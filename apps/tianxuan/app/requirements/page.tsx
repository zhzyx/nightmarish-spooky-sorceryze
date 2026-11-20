import { currentActor } from "@/lib/server-api";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import {
  fetchRequirementProgress,
  fetchRequirements,
  type ApiRequirement,
  type ApiRequirementProgress,
} from "@/lib/server-api";
import { LOCALE_COOKIE, formatMessage, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "req.title") };
}

// 实时需求依赖每次请求的 TIANXUAN_ACTOR，禁用静态化。
export const dynamic = "force-dynamic";

const LIVE_REQUIREMENT_LIMIT = 8;

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
 * 请求失败时由页面提供重试入口。
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

  const actor = await currentActor();
  let liveRequirements: ApiRequirement[] = [];
  let failed = false;
  if (actor) {
    try {
      liveRequirements = await loadLiveRequirements(actor);
    } catch {
      failed = true;
    }
  }

  return (
    <div className="page-stack requirements-page">
      <header className="page-header">
        <div className="page-title-group">
          <h1>
            {t("req.title")}
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
              <h2 id="live-requirements-title">{t("req.liveTitle")}</h2>
            </div>
            <span className="section-note">{formatMessage(t("req.liveNote"), { count: liveRequirements.length })}</span>
          </header>

          <div className="reading-list live-list">
            {liveRequirements.map((requirement) => {
              const percent = normalizePercent(requirement.progress);
              return (
                <Link className="reading-item" href={`/docs/${encodeURIComponent(requirement.id)}`} key={requirement.id}>
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
      ) : (
        <section className="panel route-state">
          <p role="status">{!actor
            ? (locale === "zh" ? "登录后查看需求。" : "Sign in to view requirements.")
            : failed ? (locale === "zh" ? "无法读取需求。" : "Requirements could not be loaded.")
            : (locale === "zh" ? "暂无需求。可在工作台创建第一份草稿。" : "No requirements yet. Start a draft in the workspace.")}</p>
          {!actor && <Link className="btn btn-primary" href="/login">{locale === "zh" ? "登录" : "Sign in"}</Link>}
          {failed && <a className="btn btn-ghost" href="/requirements">{locale === "zh" ? "重新加载" : "Reload"}</a>}
        </section>
      )}
    </div>
  );
}

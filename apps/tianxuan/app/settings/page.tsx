import { currentActor } from "@/lib/server-api";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { IdentityBindings } from "@/components/IdentityBindings";
import { ThemeSelect } from "@/components/ThemeSelect";
import { fetchGiteaStatus, fetchHealth, type ApiGiteaStatus } from "@/lib/server-api";
import { LOCALE_COOKIE, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "settings.title") };
}

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);
  const actor = await currentActor();
  let apiOnline = false;
  let gitea: ApiGiteaStatus | null = null;
  try {
    await fetchHealth();
    apiOnline = true;
  } catch {
    apiOnline = false;
  }
  try {
    gitea = await fetchGiteaStatus();
  } catch {
    gitea = null;
  }

  return (
    <div className="page-stack settings-page">
      <header className="page-header">
        <div className="page-title-group">
          <h1>
            {t("settings.title")}
          </h1>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/docs/onboarding">
            <Icon name="docs" size={16} />
            {t("settings.guide")}
          </Link>
        </div>
      </header>

      <section className="panel settings-preferences">
        <div>
          <h2 id="appearance">{t("settings.appearanceTitle")}</h2>
          <ThemeSelect />
        </div>
        <div>
          <h2>{locale === "zh" ? "账号与访问" : "Account and access"}</h2>
          <Link className="btn btn-ghost" href="/accounts">{locale === "zh" ? "管理账号" : "Manage account"}</Link>
        </div>
      </section>
      <section className="panel" aria-labelledby="system-status-title">
        <div className="section-heading">
          <div>
            <h2 id="system-status-title">{t("settings.systemTitle")}</h2>
          </div>
          <span className="section-note">{t("settings.systemNote")}</span>
        </div>
        <div className="reading-list live-list">
          <div className="reading-item">
            <span className="reading-index">API</span>
            <span className="reading-copy">
              <strong>{apiOnline ? t("settings.connected") : t("settings.unreachable")}</strong>
              <span>/api/v1/health</span>
            </span>
          </div>
          <div className="reading-item">
            <span className="reading-index">Git</span>
            <span className="reading-copy">
              <strong>{gitea?.configured ? t("settings.giteaConfigured") : t("settings.giteaMissing")}</strong>
              <span>{gitea?.owner ? `owner: ${gitea.owner}` : t("settings.giteaHint")}</span>
            </span>
          </div>
          <div className="reading-item">
            <span className="reading-index">Actor</span>
            <span className="reading-copy">
              <strong>{actor || t("settings.actorMissing")}</strong>
              <span>TIANXUAN_ACTOR</span>
            </span>
          </div>
        </div>
      </section>

      <IdentityBindings />
    </div>
  );
}

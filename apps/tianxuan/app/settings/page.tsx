import { currentActor } from "@/lib/server-api";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Icon, type IconName } from "@/components/Icon";
import { IdentityBindings } from "@/components/IdentityBindings";
import { fetchGiteaStatus, fetchHealth, type ApiGiteaStatus } from "@/lib/server-api";
import { LOCALE_COOKIE, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "settings.title") };
}

export const dynamic = "force-dynamic";

const members = [
  { name: "Sail", handle: "sail", role: "管理员", tone: "jade", status: "在线" },
  { name: "文曲", handle: "wenqu", role: "Agent · 文档", tone: "jade", status: "运行中" },
  { name: "偃师", handle: "yanshi", role: "Agent · 需求", tone: "gold", status: "运行中" },
  { name: "司南", handle: "sinan", role: "Agent · 工单", tone: "cinnabar", status: "运行中" },
  { name: "多宝", handle: "duobao", role: "Agent · 仓库", tone: "gold", status: "空闲" },
];

export default async function SettingsPage() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);
  const settingsNav: { href: string; label: string; icon: IconName }[] = [
    { href: "#profile", label: t("settings.navProfile"), icon: "users" },
    { href: "#appearance", label: t("settings.navAppearance"), icon: "eye" },
    { href: "#workspace", label: t("settings.navWorkspace"), icon: "home" },
    { href: "#ai", label: t("settings.navAi"), icon: "sparkles" },
    { href: "#notifications", label: t("settings.navNotifications"), icon: "bell" },
    { href: "#members", label: t("settings.navMembers"), icon: "lock" },
    { href: "#security", label: t("settings.navSecurity"), icon: "alert" },
  ];
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
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            ORGANIZATION · SETTINGS
          </p>
          <h1>
            {t("settings.title")}
            {locale === "zh" ? <span className="title-period">。</span> : null}
          </h1>
          <p className="page-lede">{t("settings.lede")}</p>
        </div>
        <div className="page-actions">
          <span className="settings-prototype">
            <span className="live-dot" aria-hidden="true" />
            {t("settings.prototype")}
          </span>
          <Link className="btn btn-ghost" href="/docs/onboarding">
            <Icon name="docs" size={16} />
            {t("settings.guide")}
          </Link>
        </div>
      </header>

      <section className="panel" aria-labelledby="system-status-title">
        <div className="section-heading">
          <div>
            <p className="section-kicker">SYSTEM · STATUS</p>
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

      <div className="settings-layout">
        <nav aria-label={t("settings.navAria")} className="settings-nav">
          <p className="sidebar-label">{t("settings.navGroup")}</p>
          {settingsNav.map((item, index) => (
            <a className={index === 0 ? "is-active" : ""} href={item.href} key={item.href}>
              <Icon name={item.icon} size={16} />
              {item.label}
            </a>
          ))}
          <div className="settings-nav-note">
            <span className="settings-nav-seal" aria-hidden="true">
              静
            </span>
            <p>{t("settings.quote")}</p>
            <small>{t("settings.quoteCaption")}</small>
          </div>
        </nav>

        <div className="settings-content">
          <section className="panel settings-card" id="profile" aria-labelledby="profile-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">IDENTITY</p>
                <h2 id="profile-title">{t("settings.profileTitle")}</h2>
                <p>{t("settings.profileDesc")}</p>
              </div>
              <Icon className="panel-head-icon" name="users" size={19} />
            </header>

            <div className="profile-edit-row">
              <span className="avatar avatar-xl avatar-jade">S</span>
              <div className="profile-edit-copy">
                <strong>{t("settings.avatarTitle")}</strong>
                <span>{t("settings.avatarDesc")}</span>
              </div>
              <span className="role-pill">{t("settings.adminRole")}</span>
            </div>

            <div className="settings-form-grid">
              <label className="settings-field">
                <span>{t("settings.displayName")}</span>
                <input defaultValue="Sail" />
              </label>
              <label className="settings-field">
                <span>{t("settings.workspaceHandle")}</span>
                <input defaultValue="sail" spellCheck={false} />
              </label>
              <label className="settings-field settings-field-wide">
                <span>{t("settings.bio")}</span>
                <input defaultValue={t("settings.bioDefault")} />
              </label>
            </div>
          </section>

          <section className="panel settings-card" id="appearance" aria-labelledby="appearance-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">APPEARANCE</p>
                <h2 id="appearance-title">{t("settings.appearanceTitle")}</h2>
                <p>{t("settings.appearanceDesc")}</p>
              </div>
              <span className="settings-tag">{t("settings.darkFirst")}</span>
            </header>

            <div className="theme-options">
              <label className="theme-option is-selected">
                <input defaultChecked name="theme" type="radio" value="ink" />
                <span className="theme-preview theme-preview-dark">
                  <span className="theme-preview-side" />
                  <span className="theme-preview-main">
                    <span />
                    <span />
                    <span />
                  </span>
                </span>
                <span className="theme-option-copy">
                  <strong>{t("settings.ink")}</strong>
                  <small>{t("settings.inkNote")}</small>
                </span>
                <span className="theme-check">
                  <Icon name="check" size={12} />
                </span>
              </label>

              <label className="theme-option">
                <input name="theme" type="radio" value="warm" />
                <span className="theme-preview theme-preview-warm">
                  <span className="theme-preview-side" />
                  <span className="theme-preview-main">
                    <span />
                    <span />
                    <span />
                  </span>
                </span>
                <span className="theme-option-copy">
                  <strong>{t("settings.warm")}</strong>
                  <small>{t("settings.warmNote")}</small>
                </span>
              </label>

              <label className="theme-option is-disabled">
                <input disabled name="theme" type="radio" value="paper" />
                <span className="theme-preview theme-preview-paper">
                  <span className="theme-preview-side" />
                  <span className="theme-preview-main">
                    <span />
                    <span />
                    <span />
                  </span>
                </span>
                <span className="theme-option-copy">
                  <strong>{t("settings.paper")}</strong>
                  <small>{t("settings.paperNote")}</small>
                </span>
                <span className="theme-lock">
                  <Icon name="lock" size={12} />
                </span>
              </label>
            </div>

            <div className="accent-row">
              <span className="settings-label">{t("settings.accentLabel")}</span>
              <span className="accent-swatch accent-ink" title={t("settings.inkSwatch")} />
              <span className="accent-swatch accent-paper" title={t("settings.paperSwatch")} />
              <span className="accent-swatch accent-cinnabar" title={t("settings.cinnabarSwatch")} />
              <span className="accent-swatch accent-jade" title={t("settings.jadeSwatch")} />
              <span className="accent-swatch accent-gold" title={t("settings.goldSwatch")} />
              <span className="accent-caption">{t("settings.accentCaption")}</span>
            </div>
          </section>

          <section className="panel settings-card" id="workspace" aria-labelledby="workspace-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">WORKSPACE</p>
                <h2 id="workspace-title">{t("settings.workspaceTitle")}</h2>
                <p>{t("settings.workspaceDesc")}</p>
              </div>
              <Icon className="panel-head-icon" name="home" size={19} />
            </header>

            <div className="settings-form-grid">
              <label className="settings-field">
                <span>{t("settings.workspaceName")}</span>
                <input defaultValue="共工工坊" />
              </label>
              <label className="settings-field">
                <span>{t("settings.handle")}</span>
                <input defaultValue="gonggong" spellCheck={false} />
              </label>
              <label className="settings-field">
                <span>{t("settings.language")}</span>
                <select defaultValue="zh-CN">
                  <option value="zh-CN">{t("settings.langZh")}</option>
                  <option value="en">English</option>
                </select>
              </label>
              <label className="settings-field">
                <span>{t("settings.timezone")}</span>
                <select defaultValue="Asia/Shanghai">
                  <option value="Asia/Shanghai">Asia / Shanghai</option>
                  <option value="UTC">UTC</option>
                </select>
              </label>
            </div>
          </section>

          <section className="panel settings-card settings-ai-card" id="ai" aria-labelledby="ai-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">AI &amp; MODELS</p>
                <h2 id="ai-title">{t("settings.aiTitle")}</h2>
                <p>{t("settings.aiDesc")}</p>
              </div>
              <span className="settings-tag settings-tag-muted">{t("settings.notConnected")}</span>
            </header>

            <div className="ai-provider">
              <span className="ai-provider-icon">
                <Icon name="sparkles" size={18} />
              </span>
              <span className="ai-provider-copy">
                <strong>{t("settings.gateway")}</strong>
                <small>{t("settings.gatewayNote")}</small>
              </span>
              <span className="ai-provider-state">
                <span className="status-dot" aria-hidden="true" />
                {t("settings.prototypeNotConnected")}
              </span>
            </div>

            <div className="settings-meta-grid">
              <div className="settings-meta">
                <span>{t("settings.defaultModel")}</span>
                <strong>{t("settings.router")}</strong>
                <small>{t("settings.routerNote")}</small>
              </div>
              <div className="settings-meta">
                <span>{t("settings.credentials")}</span>
                <strong>{t("settings.vault")}</strong>
                <small>{t("settings.vaultNote")}</small>
              </div>
              <div className="settings-meta settings-meta-usage">
                <span>{t("settings.usage")}</span>
                <strong>34%</strong>
                <span className="meter" aria-hidden="true">
                  <span style={{ width: "34%" }} />
                </span>
                <small>{t("settings.usageNote")}</small>
              </div>
            </div>

            <div className="toggle-list">
              <label className="toggle-row">
                <span>
                  <strong>{t("settings.allowDraft")}</strong>
                  <small>{t("settings.allowDraftNote")}</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>{t("settings.confirmIssues")}</strong>
                  <small>{t("settings.confirmIssuesNote")}</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>{t("settings.audit")}</strong>
                  <small>{t("settings.auditNote")}</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
            </div>
          </section>

          <section className="panel settings-card" id="notifications" aria-labelledby="notifications-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">NOTIFICATIONS</p>
                <h2 id="notifications-title">{t("settings.notificationsTitle")}</h2>
                <p>{t("settings.notificationsDesc")}</p>
              </div>
              <Icon className="panel-head-icon" name="bell" size={19} />
            </header>
            <div className="toggle-list">
              <label className="toggle-row">
                <span>
                  <strong>{t("settings.notifyReview")}</strong>
                  <small>{t("settings.notifyReviewNote")}</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>{t("settings.notifyDocs")}</strong>
                  <small>{t("settings.notifyDocsNote")}</small>
                </span>
                <span className="switch">
                  <input type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-row">
                <span>
                  <strong>{t("settings.notifyDaily")}</strong>
                  <small>{t("settings.notifyDailyNote")}</small>
                </span>
                <span className="switch">
                  <input defaultChecked type="checkbox" />
                  <span className="switch-track" aria-hidden="true" />
                </span>
              </label>
            </div>
          </section>

          <section className="panel settings-card" id="members" aria-labelledby="members-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">MEMBERS &amp; ACCESS</p>
                <h2 id="members-title">{t("settings.membersTitle")}</h2>
                <p>{t("settings.membersDesc")}</p>
              </div>
              <span className="settings-tag">{t("settings.memberLimit")}</span>
            </header>

            <div className="member-table">
              <div className="member-table-head" aria-hidden="true">
                <span>{t("settings.colMember")}</span>
                <span>{t("settings.colRole")}</span>
                <span>{t("settings.colStatus")}</span>
              </div>
              {members.map((member) => (
                <div className="member-row" key={member.handle}>
                  <span className="member-identity">
                    <span className={`avatar avatar-sm avatar-${member.tone}`} aria-hidden="true">
                      {member.name.slice(0, 1)}
                    </span>
                    <span>
                      <strong>{member.name}</strong>
                      <small>@{member.handle}</small>
                    </span>
                  </span>
                  <span className="member-role">{member.role}</span>
                  <span className="member-status">
                    <span className="live-dot" aria-hidden="true" />
                    {member.status}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel settings-card settings-security" id="security" aria-labelledby="security-title">
            <header className="settings-card-head">
              <div>
                <p className="section-kicker">SECURITY &amp; DATA</p>
                <h2 id="security-title">{t("settings.securityTitle")}</h2>
                <p>{t("settings.securityDesc")}</p>
              </div>
              <Icon className="panel-head-icon" name="lock" size={19} />
            </header>

            <div className="security-rows">
              <div className="security-row">
                <span>
                  <strong>{t("settings.session")}</strong>
                  <small>{t("settings.sessionNote")}</small>
                </span>
                <span className="security-state">{t("settings.previewOnly")}</span>
              </div>
              <div className="security-row">
                <span>
                  <strong>{t("settings.exportTitle")}</strong>
                  <small>{t("settings.exportNote")}</small>
                </span>
                <button className="btn btn-ghost btn-sm" disabled type="button">
                  {t("settings.exportBtn")}
                </button>
              </div>
              <div className="security-row security-row-danger">
                <span>
                  <strong>{t("settings.archiveTitle")}</strong>
                  <small>{t("settings.archiveNote")}</small>
                </span>
                <button className="btn btn-danger btn-sm" disabled type="button">
                  {t("settings.archiveBtn")}
                </button>
              </div>
            </div>
          </section>

          <p className="settings-footnote">
            <Icon name="lock" size={13} />
            {t("settings.footer")}
          </p>
        </div>
      </div>
    </div>
  );
}

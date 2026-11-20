"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { useIdentity } from "@/components/IdentityProvider";
import { ApiStatus } from "@/components/ApiStatus";
import { useI18n } from "@/lib/i18n-client";
import { routeTitleKey, type MessageKey } from "@/lib/i18n";
import { ThemeSelect } from "@/components/ThemeSelect";

interface NavItem {
  href: string;
  key: MessageKey;
  icon: IconName;
}

const primaryNav: NavItem[] = [
  { href: "/", key: "nav.home", icon: "home" },
  { href: "/docs", key: "nav.docs", icon: "docs" },
  { href: "/game-config", key: "nav.gameConfig", icon: "settings" },
  { href: "/issues", key: "nav.issues", icon: "issues" },
  { href: "/repos", key: "nav.repos", icon: "repos" },
  { href: "/requirements", key: "nav.requirements", icon: "requirements" },
];

const utilityNav: NavItem[] = [
  { href: "/migration", key: "nav.migration", icon: "history" },
  { href: "/search", key: "nav.search", icon: "search" },
  { href: "/settings", key: "nav.settings", icon: "settings" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const identity = useIdentity();
  const { t, locale, setLocale } = useI18n();
  const profileName = identity?.name || identity?.email || (locale === "zh" ? "未登录" : "Signed out");
  const roles: Record<string, string> = {viewer: "只读", editor: "编辑", admin: "管理员"};
  const profileRole = identity ? (locale === "zh" ? (roles[identity.role] ?? identity.role) : identity.role) : "";
  const profileInitial = identity ? profileName.slice(0, 1).toUpperCase() : "?";
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const currentTitle = t(routeTitleKey(pathname));

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  return (
    <>
      <a className="skip-link" href="#main-content">
        {t("shell.skip")}
      </a>
      <div className="app-frame">
        <aside
          aria-label={t("shell.navAria")}
          className={`sidebar${mobileNavOpen ? " is-open" : ""}`}
          id="app-sidebar"
        >
          <div className="sidebar-brand">
            <Link className="brand" href="/" aria-label={t("shell.brandAria")}>
              <span className="brand-mark" aria-hidden="true">
                <span>璇</span>
              </span>
              <span className="brand-wordmark">
                <strong>天璇</strong>
              </span>
            </Link>
            <button
              aria-label={t("shell.closeNav")}
              className="icon-button sidebar-close"
              onClick={() => setMobileNavOpen(false)}
              type="button"
            >
              <Icon name="close" size={18} />
            </button>
          </div>

          <nav aria-label={t("shell.navAria")} className="sidebar-nav">
            <p className="sidebar-label">{t("shell.workspace")}</p>
            {primaryNav.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={`nav-item${active ? " is-active" : ""}`}
                  href={item.href}
                  key={item.href}
                >
                  <span className="nav-icon">
                    <Icon name={item.icon} size={18} />
                  </span>
                  <span>{t(item.key)}</span>
                </Link>
              );
            })}

            <p className="sidebar-label sidebar-label-spaced">{t("shell.explore")}</p>
            {utilityNav.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={`nav-item${active ? " is-active" : ""}`}
                  href={item.href}
                  key={item.href}
                >
                  <span className="nav-icon">
                    <Icon name={item.icon} size={18} />
                  </span>
                  <span>{t(item.key)}</span>
                </Link>
              );
            })}
          </nav>

          <div className="sidebar-footer">
            <ApiStatus />
            <Link className="profile-card" href="/accounts">
              <span className="avatar avatar-jade">{profileInitial}</span>
              <span className="profile-copy">
                <strong>{profileName}</strong>
                <small>{profileRole}</small>
              </span>
              <Icon name="more" size={16} />
            </Link>
          </div>
        </aside>

        {mobileNavOpen ? (
          <button
            aria-label={t("shell.closeScrim")}
            className="sidebar-scrim"
            onClick={() => setMobileNavOpen(false)}
            type="button"
          />
        ) : null}

        <div className="app-main">
          <header className="topbar">
            <div className="topbar-left">
              <button
                aria-controls="app-sidebar"
                aria-expanded={mobileNavOpen}
                aria-label={t("shell.openNav")}
                className="icon-button menu-button"
                onClick={() => setMobileNavOpen(true)}
                type="button"
              >
                <Icon name="menu" size={20} />
              </button>
              <div className="breadcrumbs" aria-label={t("shell.breadcrumbsAria")}>
                <Link href="/">{t("shell.workspaceName")}</Link>
                <span aria-hidden="true">/</span>
                <span aria-current="page">{currentTitle}</span>
              </div>
            </div>

            <div className="topbar-actions">
              <form action="/search" className="topbar-search" role="search">
                <Icon name="search" size={16} />
                <input
                  aria-label={t("shell.searchAria")}
                  name="q"
                  placeholder={t("shell.searchPlaceholder")}
                  type="search"
                />
                <span className="search-scope">{t("shell.searchScope")}</span>
              </form>
              <Link aria-label={t("shell.searchAria")} className="icon-button mobile-search-link" href="/search">
                <Icon name="search" size={19} />
              </Link>
              <button
                aria-label={t("shell.languageToggle")}
                className="icon-button"
                onClick={() => setLocale(locale === "zh" ? "en" : "zh")}
                type="button"
              >
                {locale === "zh" ? "EN" : "中"}
              </button>
              <ThemeSelect />
              <Link className="topbar-avatar" href="/settings" aria-label={t("shell.settingsAria")}>
                <span className="avatar avatar-jade">{profileInitial}</span>
              </Link>
            </div>
          </header>

          <main className="page-content" id="main-content">
            {children}
          </main>
        </div>
      </div>
    </>
  );
}

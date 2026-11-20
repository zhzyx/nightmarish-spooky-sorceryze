"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
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

const projectNav: NavItem[] = [
  { href: "/", key: "nav.home", icon: "home" },
  { href: "/requirements", key: "nav.requirements", icon: "requirements" },
  { href: "/issues", key: "nav.issues", icon: "issues" },
  { href: "/docs", key: "nav.docs", icon: "docs" },
];

const libraryNav: NavItem[] = [
  { href: "/repos", key: "nav.repos", icon: "repos" },
  { href: "/game-config", key: "nav.gameConfig", icon: "layers" },
  { href: "/migration", key: "nav.migration", icon: "history" },
  { href: "/search", key: "nav.search", icon: "search" },
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

  const sidebar = useRef<HTMLElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const mobileSearch = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if (event.defaultPrevented || event.isComposing || event.repeat) return;
      if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey || event.key.toLowerCase() !== "k" || mobileNavOpen) return;
      event.preventDefault();
      if (search.current?.getClientRects().length) {
        search.current.focus();
        search.current.select();
      } else {
        mobileSearch.current?.click();
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [mobileNavOpen]);

  useEffect(() => {
    if (!mobileNavOpen || !sidebar.current || !content.current) return;
    const panel = sidebar.current;
    const background = content.current;
    const desktop = matchMedia("(min-width: 1021px)");
    const previousOverflow = document.body.style.overflow;
    function closeOnResize() {
      if (desktop.matches) setMobileNavOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMobileNavOpen(false);
      if (event.key !== "Tab") return;
      const controls = Array.from(panel.querySelectorAll<HTMLElement>("a[href], button:enabled"));
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    background.inert = true;
    document.body.style.overflow = "hidden";
    panel.querySelector<HTMLElement>('[aria-current="page"], .sidebar-close')?.focus();
    desktop.addEventListener("change", closeOnResize);
    panel.addEventListener("keydown", onKey);
    return () => {
      background.inert = false;
      document.body.style.overflow = previousOverflow;
      desktop.removeEventListener("change", closeOnResize);
      panel.removeEventListener("keydown", onKey);
      if (!desktop.matches) menu.current?.focus();
    };
  }, [mobileNavOpen]);

  return (
    <>
      <a className="skip-link" href="#main-content">
        {t("shell.skip")}
      </a>
      <div className="app-frame">
        <aside
          ref={sidebar}
          role={mobileNavOpen ? "dialog" : undefined}
          aria-modal={mobileNavOpen || undefined}
          onClick={event => { if ((event.target as Element).closest("a[href]")) setMobileNavOpen(false); }}
          aria-label={t("shell.navAria")}
          className={`sidebar${mobileNavOpen ? " is-open" : ""}`}
          id="app-sidebar"
        >
          <div className="sidebar-brand">
            <Link className="brand" href="/" aria-label={t("shell.brandAria")}>
              <span className="brand-mark" aria-hidden="true">
                <Icon name="layers" size={23} />
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
            {[
              { label: t("shell.workspace"), items: projectNav },
              { label: locale === "zh" ? "资源" : "Resources", items: libraryNav },
            ].map(group => (
              <div className="nav-group" key={group.items[0].href}>
                <p className="sidebar-label">{group.label}</p>
                {group.items.map(item => {
                  const active = isActive(pathname, item.href);
                  return <Link aria-current={active ? "page" : undefined}
                    className={`nav-item${active ? " is-active" : ""}`} href={item.href} key={item.href}>
                    <span className="nav-icon"><Icon name={item.icon} size={19} /></span>
                    <span>{t(item.key)}</span>
                  </Link>;
                })}
              </div>
            ))}
          </nav>

          <div className="sidebar-footer">
            <Link className={`nav-item${pathname === "/settings" ? " is-active" : ""}`} href="/settings"
              aria-current={pathname === "/settings" ? "page" : undefined}>
              <span className="nav-icon"><Icon name="settings" size={19} /></span>{t("nav.settings")}
            </Link>
            <ApiStatus />
            <Link className="profile-card" href={identity ? "/accounts" : "/login"}>
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
            tabIndex={-1}
            type="button"
          />
        ) : null}

        <div className="app-main" ref={content}>
          <header className="topbar">
            <div className="topbar-left">
              <button
                ref={menu}
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
                  ref={search}
                  name="q"
                  placeholder={t("shell.searchPlaceholder")}
                  type="search"
                />
                <kbd className="search-scope" aria-hidden="true">Ctrl / ⌘ K</kbd>
              </form>
              <Link ref={mobileSearch} aria-label={t("shell.searchAria")} className="icon-button mobile-search-link" href="/search">
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

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { spaces } from "@/lib/data";

interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  badge?: string;
}

const primaryNav: NavItem[] = [
  { href: "/", label: "工作台", icon: "home" },
  { href: "/docs", label: "文档", icon: "docs" },
  { href: "/issues", label: "工单", icon: "issues", badge: "3" },
  { href: "/repos", label: "代码仓库", icon: "repos" },
  { href: "/requirements", label: "需求", icon: "requirements" },
];

const utilityNav: NavItem[] = [
  { href: "/search", label: "全局搜索", icon: "search" },
  { href: "/settings", label: "设置", icon: "settings" },
];

const routeTitles: Record<string, string> = {
  "": "工作台",
  docs: "文档",
  issues: "工单",
  repos: "代码仓库",
  requirements: "需求",
  settings: "设置",
  search: "全局搜索",
};

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function sectionLabel(pathname: string): string {
  const first = pathname.split("/")[1] ?? "";
  if (first === "docs" && pathname.split("/").length > 2) {
    return "文档 / 阅读视图";
  }
  return routeTitles[first] ?? "工作台";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const currentTitle = sectionLabel(pathname);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  return (
    <>
      <a className="skip-link" href="#main-content">
        跳到主内容
      </a>
      <div className="ambient" aria-hidden="true">
        <span className="ambient-orbit ambient-orbit-one" />
        <span className="ambient-orbit ambient-orbit-two" />
        <span className="ambient-grid" />
      </div>

      <div className="app-frame">
        <aside
          aria-label="主导航"
          className={`sidebar${mobileNavOpen ? " is-open" : ""}`}
          id="app-sidebar"
        >
          <div className="sidebar-brand">
            <Link className="brand" href="/" aria-label="天璇工作台">
              <span className="brand-mark" aria-hidden="true">
                <span>璇</span>
              </span>
              <span className="brand-wordmark">
                <strong>天璇</strong>
                <small>TIANXUAN</small>
              </span>
            </Link>
            <button
              aria-label="关闭导航"
              className="icon-button sidebar-close"
              onClick={() => setMobileNavOpen(false)}
              type="button"
            >
              <Icon name="close" size={18} />
            </button>
          </div>

          <button className="workspace-switch" type="button">
            <span className="workspace-avatar" aria-hidden="true">
              共
            </span>
            <span className="workspace-copy">
              <strong>共工工坊</strong>
              <small>单组织 · 10 人</small>
            </span>
            <Icon className="workspace-chevron" name="chevronDown" size={14} />
          </button>

          <nav aria-label="工作区导航" className="sidebar-nav">
            <p className="sidebar-label">工作区</p>
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
                  <span>{item.label}</span>
                  {item.badge ? <span className="nav-badge">{item.badge}</span> : null}
                </Link>
              );
            })}

            <p className="sidebar-label sidebar-label-spaced">探索</p>
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
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="sidebar-spaces">
            <div className="sidebar-label-row">
              <p className="sidebar-label">空间</p>
              <Link aria-label="浏览全部文档空间" className="quiet-icon-link" href="/docs">
                <Icon name="plus" size={14} />
              </Link>
            </div>
            {spaces.slice(0, 3).map((space) => (
              <Link className="space-shortcut" href="/docs" key={space.id}>
                <span className={`space-dot tone-${space.tone}`} aria-hidden="true" />
                <span>{space.short}</span>
                <span className="space-count">{space.pages}</span>
              </Link>
            ))}
          </div>

          <div className="sidebar-footer">
            <div className="usage-card">
              <div className="usage-card-head">
                <span>本月 AI 用量</span>
                <strong>34%</strong>
              </div>
              <div className="meter" aria-hidden="true">
                <span style={{ width: "34%" }} />
              </div>
              <small>演示数据 · 不计量真实调用</small>
            </div>
            <Link className="profile-card" href="/settings">
              <span className="avatar avatar-jade">S</span>
              <span className="profile-copy">
                <strong>Sail</strong>
                <small>产品工程 · 管理员</small>
              </span>
              <Icon name="more" size={16} />
            </Link>
          </div>
        </aside>

        {mobileNavOpen ? (
          <button
            aria-label="关闭导航遮罩"
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
                aria-label="打开导航"
                className="icon-button menu-button"
                onClick={() => setMobileNavOpen(true)}
                type="button"
              >
                <Icon name="menu" size={20} />
              </button>
              <div className="breadcrumbs" aria-label="面包屑">
                <Link href="/">共工工坊</Link>
                <span aria-hidden="true">/</span>
                <span aria-current="page">{currentTitle}</span>
              </div>
            </div>

            <div className="topbar-actions">
              <form action="/search" className="topbar-search" role="search">
                <Icon name="search" size={16} />
                <input
                  aria-label="全局搜索"
                  name="q"
                  placeholder="搜索文档、工单、仓库"
                  type="search"
                />
                <span className="search-scope">全局</span>
              </form>
              <Link aria-label="全局搜索" className="icon-button mobile-search-link" href="/search">
                <Icon name="search" size={19} />
              </Link>
              <button aria-label="通知（3 条未读）" className="icon-button notification-button" type="button">
                <Icon name="bell" size={19} />
                <span className="notification-dot" aria-hidden="true" />
              </button>
              <Link className="topbar-avatar" href="/settings" aria-label="打开个人设置">
                <span className="avatar avatar-jade">S</span>
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

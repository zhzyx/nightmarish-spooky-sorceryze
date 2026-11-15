/** 天璇 Web 文案字典与语言解析（不依赖 React，可在服务端/客户端复用）。 */

export type Locale = "zh" | "en";

export const LOCALE_COOKIE = "tianxuan_locale";

const zh = {
  "nav.home": "工作台",
  "nav.docs": "文档",
  "nav.issues": "工单",
  "nav.repos": "代码仓库",
  "nav.requirements": "需求",
  "nav.search": "全局搜索",
  "nav.settings": "设置",
  "shell.skip": "跳到主内容",
  "shell.brandAria": "天璇工作台",
  "shell.closeNav": "关闭导航",
  "shell.openNav": "打开导航",
  "shell.closeScrim": "关闭导航遮罩",
  "shell.navAria": "工作区导航",
  "shell.workspace": "工作区",
  "shell.explore": "探索",
  "shell.spaces": "空间",
  "shell.browseSpacesAria": "浏览全部文档空间",
  "shell.workspaceName": "共工工坊",
  "shell.workspaceMeta": "单组织 · 10 人",
  "shell.usageTitle": "本月 AI 用量",
  "shell.usageNote": "演示数据 · 不计量真实调用",
  "shell.profileRole": "产品工程 · 管理员",
  "shell.breadcrumbsAria": "面包屑",
  "shell.searchAria": "全局搜索",
  "shell.searchPlaceholder": "搜索文档、工单、仓库",
  "shell.searchScope": "全局",
  "shell.notificationsAria": "通知（3 条未读）",
  "shell.settingsAria": "打开个人设置",
  "shell.docReader": "文档 / 阅读视图",
  "shell.languageToggle": "切换语言",
  "login.title": "登录",
  "login.lede": "使用已注册账号换取会话 token。登录后浏览器请求携带 Bearer token；服务端渲染可配置 TIANXUAN_TOKEN。",
  "login.session": "会话登录",
  "login.email": "邮箱",
  "login.password": "密码",
  "login.submit": "登录",
  "login.busy": "登录中…",
  "login.invalid": "邮箱或密码不正确",
  "login.failed": "登录失败",
  "login.missingToken": "登录响应缺少 token",
  "login.network": "无法连接服务器",
} as const;

export type MessageKey = keyof typeof zh;

const en: Record<MessageKey, string> = {
  "nav.home": "Workspace",
  "nav.docs": "Documents",
  "nav.issues": "Issues",
  "nav.repos": "Repositories",
  "nav.requirements": "Requirements",
  "nav.search": "Search",
  "nav.settings": "Settings",
  "shell.skip": "Skip to content",
  "shell.brandAria": "Tianxuan workspace",
  "shell.closeNav": "Close navigation",
  "shell.openNav": "Open navigation",
  "shell.closeScrim": "Close navigation overlay",
  "shell.navAria": "Workspace navigation",
  "shell.workspace": "Workspace",
  "shell.explore": "Explore",
  "shell.spaces": "Spaces",
  "shell.browseSpacesAria": "Browse all document spaces",
  "shell.workspaceName": "Gonggong Studio",
  "shell.workspaceMeta": "Single organization · 10 members",
  "shell.usageTitle": "AI usage this month",
  "shell.usageNote": "Demo data · real calls are not metered",
  "shell.profileRole": "Product engineering · Admin",
  "shell.breadcrumbsAria": "Breadcrumbs",
  "shell.searchAria": "Search",
  "shell.searchPlaceholder": "Search documents, issues, repositories",
  "shell.searchScope": "All",
  "shell.notificationsAria": "Notifications (3 unread)",
  "shell.settingsAria": "Open personal settings",
  "shell.docReader": "Documents / Reader",
  "shell.languageToggle": "Switch language",
  "login.title": "Sign in",
  "login.lede": "Sign in with a registered account to obtain a session token. Browser requests then use a Bearer token; server rendering can use TIANXUAN_TOKEN.",
  "login.session": "Session sign-in",
  "login.email": "Email",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.busy": "Signing in…",
  "login.invalid": "Invalid email or password",
  "login.failed": "Sign-in failed",
  "login.missingToken": "Sign-in response is missing a token",
  "login.network": "Cannot reach the server",
};

export function normalizeLocale(value: string | null | undefined): Locale {
  return value === "en" ? "en" : "zh";
}

export function translate(locale: Locale, key: MessageKey): string {
  return locale === "en" ? en[key] : zh[key];
}

export function routeTitleKey(pathname: string): MessageKey {
  const first = pathname.split("/")[1] ?? "";
  if (first === "docs" && pathname.split("/").length > 2) {
    return "shell.docReader";
  }
  switch (first) {
    case "":
      return "nav.home";
    case "docs":
      return "nav.docs";
    case "issues":
      return "nav.issues";
    case "repos":
      return "nav.repos";
    case "requirements":
      return "nav.requirements";
    case "search":
      return "nav.search";
    case "settings":
      return "nav.settings";
    default:
      return "nav.home";
  }
}

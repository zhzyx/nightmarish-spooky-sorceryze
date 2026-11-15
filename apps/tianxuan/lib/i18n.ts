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
  "repos.title": "代码仓库",
  "repos.lede": "分支是工作的方法，合并回执是交付的证据。多宝复用可信 Git 服务，把评审、工单与精确候选放在同一条路径上。",
  "repos.guide": "工程规范",
  "repos.viewQueue": "查看合并队列",
  "repos.login": "登录",
  "repos.liveTitle": "实时仓库",
  "repos.liveNote": "个仓库来自 Gitea",
  "repos.private": "私",
  "repos.public": "公",
  "repos.defaultBranch": "默认分支",
  "repos.treeTitle": "文件与分支",
  "repos.treeHint": "登录或配置 NEXT_PUBLIC_TIANXUAN_ACTOR 后可浏览仓库。",
  "repos.repoListAria": "本地仓库列表",
  "repos.noRepos": "没有本地仓库",
  "repos.branch": "分支",
  "repos.selectBranch": "选择分支",
  "repos.newBranch": "新分支名",
  "repos.create": "新建",
  "repos.deleteBranch": "删除当前分支",
  "repos.up": "上一级",
  "repos.loading": "加载中…",
  "repos.loadTreeError": "读取文件树失败",
  "repos.loadRepoError": "读取仓库失败",
  "repos.loadReposError": "读取本地仓库失败",
  "repos.createBranchError": "创建分支失败",
  "repos.deleteBranchError": "删除分支失败",
  "repos.importError": "导入仓库失败",
  "repos.treeAria": "文件树",
  "repos.directory": "目录",
  "repos.file": "文件",
  "repos.emptyTree": "空目录，或仓库还没有提交",
  "repos.tagsLabel": "标签",
  "repos.deleteConfirm": "删除分支",
  "repos.importName": "仓库名，例如 app.git",
  "repos.importSource": "https://… 或本机绝对路径",
  "repos.import": "导入",
  "repos.importAria": "导入仓库",
  "repos.importNameAria": "导入仓库名",
  "repos.imported": "已导入",
  "repos.branches": "分支",
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
  "repos.title": "Repositories",
  "repos.lede":
    "Branches are how we work; merge receipts are the evidence we deliver. Duobao reuses trusted Git services so reviews, issues and exact candidates share one path.",
  "repos.guide": "Engineering guide",
  "repos.viewQueue": "View merge queue",
  "repos.login": "Sign in",
  "repos.liveTitle": "Live repositories",
  "repos.liveNote": "repositories from Gitea",
  "repos.private": "Private",
  "repos.public": "Public",
  "repos.defaultBranch": "Default branch",
  "repos.treeTitle": "Files and branches",
  "repos.treeHint": "Sign in or configure NEXT_PUBLIC_TIANXUAN_ACTOR to browse repositories.",
  "repos.repoListAria": "Local repositories",
  "repos.noRepos": "No local repositories",
  "repos.branch": "Branch",
  "repos.selectBranch": "Select branch",
  "repos.newBranch": "New branch name",
  "repos.create": "Create",
  "repos.deleteBranch": "Delete current branch",
  "repos.up": "Up",
  "repos.loading": "Loading…",
  "repos.loadTreeError": "Failed to load the file tree",
  "repos.loadRepoError": "Failed to load the repository",
  "repos.loadReposError": "Failed to load local repositories",
  "repos.createBranchError": "Failed to create the branch",
  "repos.deleteBranchError": "Failed to delete the branch",
  "repos.importError": "Failed to import the repository",
  "repos.treeAria": "File tree",
  "repos.directory": "Directory",
  "repos.file": "File",
  "repos.emptyTree": "Empty directory, or the repository has no commits yet",
  "repos.tagsLabel": "Tags",
  "repos.deleteConfirm": "Delete branch",
  "repos.importName": "Repository name, e.g. app.git",
  "repos.importSource": "https://… or an absolute local path",
  "repos.import": "Import",
  "repos.importAria": "Import repository",
  "repos.importNameAria": "Import repository name",
  "repos.imported": "Imported",
  "repos.branches": "branches",
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

export type Tone = "jade" | "cinnabar" | "gold" | "mist";

export interface DocSpace {
  id: string;
  name: string;
  short: string;
  description: string;
  pages: number;
  members: number;
  updated: string;
  tone: Tone;
  aiReady: boolean;
}

export type DocKind = "需求" | "设计" | "规范" | "记录" | "手册";

export interface DocRecord {
  id: string;
  title: string;
  spaceId: string;
  spaceName: string;
  kind: DocKind;
  excerpt: string;
  updated: string;
  updatedBy: string;
  readTime: string;
  tags: string[];
  words: number;
  content?: string;
}

export interface PageTreeNode {
  id: string;
  title: string;
  children?: PageTreeNode[];
}

export interface PageTreeBranch {
  label: string;
  spaceId: string;
  pages: PageTreeNode[];
}

export const spaces: DocSpace[] = [
  {
    id: "wenqu",
    name: "文曲 · 产品与设计",
    short: "文曲",
    description: "AI-native 文档、编辑器与设计系统基线。",
    pages: 128,
    members: 8,
    updated: "8 分钟前",
    tone: "jade",
    aiReady: true,
  },
  {
    id: "sinan",
    name: "司南 · 工单与交付",
    short: "司南",
    description: "事件驱动的工单流、验收记录与决策留痕。",
    pages: 64,
    members: 6,
    updated: "26 分钟前",
    tone: "cinnabar",
    aiReady: true,
  },
  {
    id: "duobao",
    name: "多宝 · 工程与仓库",
    short: "多宝",
    description: "仓库规范、分支策略与并发合入设计。",
    pages: 47,
    members: 5,
    updated: "1 小时前",
    tone: "gold",
    aiReady: true,
  },
  {
    id: "handbook",
    name: "团队手册",
    short: "手册",
    description: "新成员指南、协作约定与常用入口。",
    pages: 23,
    members: 10,
    updated: "昨天",
    tone: "mist",
    aiReady: false,
  },
];

const architectureDoc = `# AI-native 文档架构

> 文档的第一读者是 AI，第二读者才是人。Markdown 始终是唯一权威来源。

## 当前结论

- **权威层**：Markdown + frontmatter，进入版本库后不可被富文本反向覆盖。
- **机器层**：稳定块 ID、标题锚点、摘要与向量索引共同构成可检索的阅读视图。
- **人类层**：编辑器与预览只是投影，不承担持久化职责。
- **归属**：内容归文曲，事件归谛听，推进归司南，代码归多宝。

## 为什么不是富文本

富文本把语义锁在编辑器模型里，AI 每次都要重新猜测结构。Markdown 的分段、标题和代码块是稳定的，模型可以直接读取，也可以在生成时保持格式。

> 好文档不是排得漂亮，而是能被下一次生成准确复用。

## 内容结构

1. 元数据：标题、空间、作者、关联工单、稳定 ID。
2. 摘要块：给检索与 AI 首屏使用的三行事实。
3. 正文块：按标题锚点切片，块之间可以独立更新。
4. 引用块：文档、工单、提交与验收证据的双向链接。

\`\`\`ts
type DocBlock = {
  id: string;
  heading: string;
  markdown: string;
  links: { kind: "issue" | "repo" | "doc"; id: string }[];
};
\`\`\`

## 读写路径

| 路径 | 行为 | 一致性 |
| --- | --- | --- |
| 人类编辑 | 保存完整 Markdown | 乐观并发 + 版本快照 |
| AI 更新 | 只提交目标块 | 块级 ETag + 审计事件 |
| 搜索 | 标题权重 > 摘要 > 正文 | 写入后异步重建索引 |
| 导出 | md / html / pdf | 从权威层单向生成 |

## 下一步

- [ ] 为块级更新补齐冲突合并策略。
- [ ] 把引用关系写入统一事件流。
- [ ] 在编辑器侧展示 AI 读取到的摘要与锚点。
`;

const platformDoc = `# 天璇平台设计基线

> 把复杂留给系统，把清晰留给人。

## 范围

- 文曲：Markdown 文档、自动归类、语义检索与评审批次。
- 司南：最小可配置状态机、事件推进与验收闭环。
- 多宝：仓库、分支、合并请求与并发合入。
- 产品壳：单组织工作台、全局搜索、AI 指挥台与通知。

## 设计原则

1. **深色优先**：墨色背景承载内容，宣纸白只用于高对比文本。
2. **克制的中国风**：云纹与回纹只作低对比背景，不装饰正文。
3. **毛玻璃分层**：浮层、工具栏与侧栏使用同一材质，不用重阴影。
4. **AI 在路径上**：不是独立聊天框，而是每个动作旁的下一步建议。

## 垂直切片

当前切片先打通“文档 → 工单 → 仓库 → 验收”的只读视图，再接入真实服务。

\`\`\`text
需求 (偃师)
  └─ 设计文档 (文曲)
       └─ 工单树 (司南)
            └─ 提交 / PR (多宝)
                 └─ 验收记录 (司南)
\`\`\`

## 视觉令牌

- Ink \`#0B0E11\`
- Paper \`#F5F2EA\`
- Cinnabar \`#C8402F\`
- Jade \`#3E8E7E\`
- Gold \`#C9A227\`

## 待确认

- [ ] 评论与建议模式是否进入首版。
- [ ] 多宝合并队列的优先级规则。
- [ ] 全局搜索的索引一致性窗口。
`;

const designLanguageDoc = `# 扁平中国风 · 视觉语言 v0.1

## 一件事

深色墨底、宣纸文字、朱砂点睛、青玉表示完成、鎏金表示秩序。纹样只作为空间刻度，不抢内容。

## 材质

- 背景：墨色渐变 + 大尺度径向光晕。
- 浮层：半透明墨玻璃，18px 模糊，1px 内外描边。
- 卡片：不使用浮夸投影，以细线、留白和局部高光分层。
- 动效：160–240ms，只用于状态切换与浮层进入。

## 字与留白

标题优先使用衬线体，正文使用系统无衬线体。中文标题字间距收紧，段落行高保持 1.9。页面主内容最大宽度 1440px，常用栏间距 24px。
`;

const duobaoDoc = `# 多宝 Git 编排与并发合入

> 不重写 Git 协议，只编排可信的 Git 服务。

## 合入队列

1. 候选分支创建后冻结 base 提交。
2. 合并请求进入分片队列，按仓库与目标分支分组。
3. 预检读取保护规则、路径权限与关联工单。
4. 合入前再次校验 base，冲突进入隔离评审。
5. 成功后广播事件，司南推进工单状态。

## 冲突策略

- 同一路径锁粒度为分支级，不阻塞其他路径评审。
- 语义冲突由合契介入，不在队列中静默自动解决。
- 每个候选保留精确 SHA，不使用浮动的分支名作为证据。

## 任务

- [ ] 队列可视化的等待原因。
- [ ] 批量评审与按路径局部合入。
- [ ] PR 摘要与风险提示的模型调用审计。
`;

const sinanDoc = `# 司南事件与自动推进

## 事件优先级

1. 验收证据回填
2. 合并请求状态变化
3. 工单依赖解除
4. 文档更新与评论

## 状态机

\`\`\`text
待梳理 → 进行中 → 评审中 → 已完成
             ↘ 阻塞（需要人工判断）
\`\`\`

自动推进只做提议，不覆盖人工决定。每个提议写入事件流，并附带触发的文档、工单或提交引用。

## 边界

- 不替代司南的协调与派发责任。
- 不将模型判断直接当作验收结论。
- 阻塞超过一个工作日自动提醒责任人，而不是批量升级。
`;

const acceptanceDoc = `# 验收记录 · #1085

> 记录来自真实回读，不使用估算用量。

## 已回读

- 设计基线与素材清单已进入当前分支。
- 领域核心具备可独立运行的测试入口。
- Web 壳与静态视觉样张在当前切片交付。

## 待验收

- [ ] 文曲编辑器接入真实持久化。
- [ ] 多宝服务选型与合并队列压测。
- [ ] 模型调用、额度与审计链路。
- [ ] 中英文切换与离线草稿合并。

## 证据

本页与关联工单保持双向链接；回填时只追加实际文件、提交和事件。
`;

const toolsDoc = `# AI 工具面与权限边界

## 工具面

文档工具、工单工具、仓库工具与需求工具共享同一套幂等语义。每个调用携带范围、操作者与审计 ID。

## 权限边界

- AI 可以搜索、读取、起草与提议。
- 涉及删除、权限变更与强制合入的动作必须由人确认。
- 所有模型输出附带来源引用，不将生成内容写成既成事实。

## 审计

每次工具调用记录：输入摘要、来源范围、模型路由、操作结果与人工确认人。凭据不进入日志与仓库。
`;

const onboardingDoc = `# 新成员工作区指南

## 第一小时

1. 浏览工作台，确认所在空间与当前迭代。
2. 阅读《天璇平台设计基线》。
3. 在司南查看分配给自己的工单。
4. 配置通知，不需要配置任何模型凭据。

## 协作约定

- 文档先于工单，验收证据回填到原文。
- 分支和 PR 关联真实工单编号。
- 讨论结论写回文档，不在聊天里结束决策。

## 常用入口

- 文档空间：文曲
- 工单看板：司南
- 代码仓库：多宝
`;

export const docs: DocRecord[] = [
  {
    id: "ai-native-docs",
    title: "AI-native 文档架构",
    spaceId: "wenqu",
    spaceName: "文曲 · 产品与设计",
    kind: "设计",
    excerpt: "Markdown 作为唯一权威，稳定锚点与块索引让 AI 可检索、可增量更新。",
    updated: "8 分钟前",
    updatedBy: "文曲",
    readTime: "6 分钟阅读",
    tags: ["架构", "文曲", "检索"],
    words: 1840,
    content: architectureDoc,
  },
  {
    id: "tianxuan-platform",
    title: "天璇平台设计基线",
    spaceId: "wenqu",
    spaceName: "文曲 · 产品与设计",
    kind: "需求",
    excerpt: "文曲、司南、多宝与产品壳的首版范围、视觉原则和垂直切片。",
    updated: "22 分钟前",
    updatedBy: "偃师",
    readTime: "8 分钟阅读",
    tags: ["基线", "需求", "天璇"],
    words: 2260,
    content: platformDoc,
  },
  {
    id: "design-language",
    title: "扁平中国风 · 视觉语言 v0.1",
    spaceId: "wenqu",
    spaceName: "文曲 · 产品与设计",
    kind: "设计",
    excerpt: "墨、纸、朱砂、青玉与鎏金的使用秩序，以及毛玻璃浮层的材质规范。",
    updated: "1 小时前",
    updatedBy: "Sail",
    readTime: "4 分钟阅读",
    tags: ["设计系统", "视觉"],
    words: 980,
    content: designLanguageDoc,
  },
  {
    id: "ai-tools",
    title: "AI 工具面与权限边界",
    spaceId: "wenqu",
    spaceName: "文曲 · 产品与设计",
    kind: "规范",
    excerpt: "工具幂等、范围化与审计的统一约定，明确哪些动作必须由人确认。",
    updated: "2 小时前",
    updatedBy: "文曲",
    readTime: "5 分钟阅读",
    tags: ["AI", "治理", "审计"],
    words: 1120,
    content: toolsDoc,
  },
  {
    id: "duobao-git",
    title: "多宝 Git 编排与并发合入",
    spaceId: "duobao",
    spaceName: "多宝 · 工程与仓库",
    kind: "设计",
    excerpt: "复用开源 Git 服务，围绕分片队列、路径锁与精确候选设计合入流程。",
    updated: "今天 08:36",
    updatedBy: "多宝",
    readTime: "7 分钟阅读",
    tags: ["多宝", "Git", "并发"],
    words: 1680,
    content: duobaoDoc,
  },
  {
    id: "sinan-events",
    title: "司南事件与自动推进",
    spaceId: "sinan",
    spaceName: "司南 · 工单与交付",
    kind: "规范",
    excerpt: "事件优先级、最小状态机与人工决定边界。",
    updated: "昨天 21:18",
    updatedBy: "司南",
    readTime: "5 分钟阅读",
    tags: ["司南", "状态机", "事件"],
    words: 1240,
    content: sinanDoc,
  },
  {
    id: "acceptance-1085",
    title: "验收记录 · #1085",
    spaceId: "sinan",
    spaceName: "司南 · 工单与交付",
    kind: "记录",
    excerpt: "Web 壳、领域核心与视觉样张的当前回读结果和剩余验收。",
    updated: "昨天 19:04",
    updatedBy: "夸父",
    readTime: "3 分钟阅读",
    tags: ["验收", "1085"],
    words: 640,
    content: acceptanceDoc,
  },
  {
    id: "onboarding",
    title: "新成员工作区指南",
    spaceId: "handbook",
    spaceName: "团队手册",
    kind: "手册",
    excerpt: "首次进入天璇的浏览路径、协作约定与常用入口。",
    updated: "11 月 12 日",
    updatedBy: "Sail",
    readTime: "3 分钟阅读",
    tags: ["手册", "入职"],
    words: 720,
    content: onboardingDoc,
  },
];

export const pageTree: PageTreeBranch[] = [
  {
    label: "产品与设计",
    spaceId: "wenqu",
    pages: [
      {
        id: "tianxuan-platform",
        title: "天璇平台设计基线",
        children: [
          { id: "ai-native-docs", title: "AI-native 文档架构" },
          { id: "design-language", title: "扁平中国风 · 视觉语言" },
          { id: "ai-tools", title: "AI 工具面与权限边界" },
        ],
      },
    ],
  },
  {
    label: "工单与交付",
    spaceId: "sinan",
    pages: [
      { id: "sinan-events", title: "司南事件与自动推进" },
      { id: "acceptance-1085", title: "验收记录 · #1085" },
    ],
  },
  {
    label: "工程与仓库",
    spaceId: "duobao",
    pages: [{ id: "duobao-git", title: "多宝 Git 编排与并发合入" }],
  },
  {
    label: "团队手册",
    spaceId: "handbook",
    pages: [{ id: "onboarding", title: "新成员工作区指南" }],
  },
];

export const recentDocIds = [
  "ai-native-docs",
  "sinan-events",
  "duobao-git",
  "acceptance-1085",
];

export function getDoc(id: string): DocRecord | undefined {
  return docs.find((doc) => doc.id === id);
}

export function getSpace(spaceId: string): DocSpace | undefined {
  return spaces.find((space) => space.id === spaceId);
}

export function getDocContent(doc: DocRecord): string {
  return (
    doc.content ??
    `# ${doc.title}

> ${doc.excerpt}

## 摘要

本页属于“${doc.spaceName}”，当前为工作区内的可编辑知识页。

## 待补充

- [ ] 补充背景、决策与关联证据。
- [ ] 将结论回填到关联工单。
`
  );
}

export type IssueStatus = "backlog" | "progress" | "review" | "done";
export type IssuePriority = "P0" | "P1" | "P2";
export type IssueKind = "需求" | "缺陷" | "任务" | "设计";

export interface IssueRecord {
  id: string;
  key: string;
  title: string;
  status: IssueStatus;
  priority: IssuePriority;
  kind: IssueKind;
  project: "文曲" | "司南" | "多宝" | "天璇";
  assignee: string;
  assigneeTone: Tone;
  updated: string;
  comments: number;
  attachments: number;
  blocked?: boolean;
  tags: string[];
  detail: string;
  criteria: string[];
  docId?: string;
  repoId?: string;
}

export const issueColumns: {
  id: IssueStatus;
  label: string;
  hint: string;
}[] = [
  { id: "backlog", label: "待梳理", hint: "进入迭代前" },
  { id: "progress", label: "进行中", hint: "正在推进" },
  { id: "review", label: "评审中", hint: "等待判断" },
  { id: "done", label: "已完成", hint: "本周闭环" },
];

export const issues: IssueRecord[] = [
  {
    id: "issue-312",
    key: "TX-312",
    title: "实现 AI-native 文档块编辑器",
    status: "progress",
    priority: "P0",
    kind: "需求",
    project: "文曲",
    assignee: "文曲",
    assigneeTone: "jade",
    updated: "12 分钟前",
    comments: 6,
    attachments: 2,
    tags: ["前端", "编辑器"],
    detail:
      "围绕 Markdown 权威层实现块级编辑、标题锚点和 AI 摘要侧栏，允许模型只更新目标块。",
    criteria: ["块级锚点稳定", "预览与保存结果一致", "AI 更新有审计记录"],
    docId: "ai-native-docs",
  },
  {
    id: "issue-318",
    key: "TX-318",
    title: "接入文档语义检索与自动归类",
    status: "review",
    priority: "P1",
    kind: "需求",
    project: "文曲",
    assignee: "偃师",
    assigneeTone: "gold",
    updated: "34 分钟前",
    comments: 9,
    attachments: 1,
    tags: ["检索", "AI"],
    detail:
      "使用标题、摘要和引用关系形成空间分类，并为搜索结果附带原文锚点。",
    criteria: ["建立可回读的索引样本", "归类可由人纠正"],
    docId: "ai-native-docs",
  },
  {
    id: "issue-326",
    key: "TX-326",
    title: "多宝分支保护与并发合入队列",
    status: "progress",
    priority: "P0",
    kind: "任务",
    project: "多宝",
    assignee: "多宝",
    assigneeTone: "gold",
    updated: "1 小时前",
    comments: 4,
    attachments: 3,
    tags: ["Git", "并发"],
    detail:
      "为仓库合并请求建立分片队列，按目标分支隔离锁，并在合入前复核精确 base。",
    criteria: ["同路径冲突可隔离", "候选 SHA 可回读", "失败原因可见"],
    repoId: "tianxuan-core",
  },
  {
    id: "issue-309",
    key: "TX-309",
    title: "司南事件状态机与自动推进",
    status: "progress",
    priority: "P1",
    kind: "任务",
    project: "司南",
    assignee: "司南",
    assigneeTone: "cinnabar",
    updated: "2 小时前",
    comments: 7,
    attachments: 0,
    blocked: true,
    tags: ["事件", "工单"],
    detail:
      "把文档、工单、代码与验收事件映射为状态迁移提议。当前等待状态机边界确认。",
    criteria: ["提议不覆盖人工决定", "事件可追溯", "阻塞原因可读"],
    docId: "sinan-events",
  },
  {
    id: "issue-331",
    key: "TX-331",
    title: "全局搜索聚合文档 / 工单 / 仓库",
    status: "backlog",
    priority: "P2",
    kind: "需求",
    project: "天璇",
    assignee: "Sail",
    assigneeTone: "mist",
    updated: "昨天",
    comments: 2,
    attachments: 1,
    tags: ["搜索", "产品壳"],
    detail:
      "在一个结果面板内按来源展示文档、工单、需求与仓库结果，保留原文锚点。",
    criteria: ["跨来源结果统一排序", "空结果有明确下一步"],
  },
  {
    id: "issue-334",
    key: "TX-334",
    title: "验收回填：Web Shell 与静态样张",
    status: "review",
    priority: "P0",
    kind: "任务",
    project: "天璇",
    assignee: "夸父",
    assigneeTone: "cinnabar",
    updated: "今天 09:06",
    comments: 3,
    attachments: 2,
    tags: ["验收", "前端"],
    detail:
      "复核 Web 壳路由、交互骨架、视觉令牌与无构建样张，并将证据回填到 #1085。",
    criteria: ["文件树完整", "令牌一致", "样张无需网络即可打开"],
    docId: "acceptance-1085",
  },
  {
    id: "issue-301",
    key: "TX-301",
    title: "注册与单组织工作台骨架",
    status: "done",
    priority: "P1",
    kind: "需求",
    project: "天璇",
    assignee: "Sail",
    assigneeTone: "mist",
    updated: "昨天 18:40",
    comments: 8,
    attachments: 1,
    tags: ["产品壳", "工作台"],
    detail: "完成首版工作台信息架构与空间导航的交互骨架。",
    criteria: ["首屏路径清晰", "移动端可导航"],
  },
  {
    id: "issue-305",
    key: "TX-305",
    title: "天璇视觉语言与毛玻璃材质",
    status: "done",
    priority: "P1",
    kind: "设计",
    project: "天璇",
    assignee: "偃师",
    assigneeTone: "gold",
    updated: "昨天 16:22",
    comments: 5,
    attachments: 4,
    tags: ["设计系统", "视觉"],
    detail: "确定墨、纸、朱砂、青玉与鎏金令牌，并完成玻璃浮层规范。",
    criteria: ["令牌可复用", "暗色对比稳定"],
    docId: "design-language",
  },
  {
    id: "issue-338",
    key: "TX-338",
    title: "设置页 BYOK 模型凭据托管",
    status: "backlog",
    priority: "P2",
    kind: "任务",
    project: "文曲",
    assignee: "文曲",
    assigneeTone: "jade",
    updated: "昨天 14:08",
    comments: 1,
    attachments: 0,
    tags: ["AI", "设置"],
    detail:
      "只展示托管状态与用量入口，密钥读取和写入始终发生在服务端保险库。",
    criteria: ["页面不回显密钥", "用量与审计入口可见"],
  },
];

export interface RepoFile {
  name: string;
  kind: "dir" | "file";
  message: string;
  author: string;
  when: string;
}

export interface CommitRecord {
  sha: string;
  message: string;
  author: string;
  when: string;
}

export interface PullRequestRecord {
  id: string;
  title: string;
  author: string;
  status: "待评审" | "已通过" | "有冲突";
  comments: number;
  age: string;
}

export interface RepoRecord {
  id: string;
  name: string;
  namespace: string;
  description: string;
  language: string;
  tone: Tone;
  visibility: "私有" | "组织内" | "只读镜像";
  branch: string;
  openPRs: number;
  commits: number;
  updated: string;
  status: "稳定" | "进行中" | "只读";
  files: RepoFile[];
  commitLog: CommitRecord[];
  pullRequests: PullRequestRecord[];
}

export const repos: RepoRecord[] = [
  {
    id: "tianxuan-web",
    name: "tianxuan/web",
    namespace: "tianxuan",
    description: "天璇 Web 产品壳，Next.js App Router 与文曲编辑器界面。",
    language: "TypeScript",
    tone: "jade",
    visibility: "组织内",
    branch: "tianxuan/web-shell",
    openPRs: 3,
    commits: 128,
    updated: "6 分钟前",
    status: "进行中",
    files: [
      { name: "app", kind: "dir", message: "feat(web-shell): dashboard first paint", author: "Sail", when: "8 分钟前" },
      { name: "components", kind: "dir", message: "feat(web-shell): editor split view", author: "文曲", when: "26 分钟前" },
      { name: "preview", kind: "dir", message: "design: static visual prototype", author: "Sail", when: "1 小时前" },
      { name: "lib", kind: "dir", message: "chore: seed local demo data", author: "文曲", when: "2 小时前" },
      { name: "package.json", kind: "file", message: "chore: pin app dependencies", author: "Sail", when: "3 小时前" },
      { name: "README.md", kind: "file", message: "docs: web shell routes and preview", author: "Sail", when: "昨天" },
    ],
    commitLog: [
      { sha: "a71c9d4", message: "feat(web-shell): dashboard first paint", author: "Sail", when: "8 分钟前" },
      { sha: "e04b3a8", message: "feat(web-shell): editor split view", author: "文曲", when: "26 分钟前" },
      { sha: "c38f712", message: "design: add static preview", author: "Sail", when: "1 小时前" },
      { sha: "91adc2e", message: "chore: seed local demo data", author: "文曲", when: "2 小时前" },
      { sha: "40cdebf", message: "feat(tianxuan): add design baseline", author: "Sail", when: "今天 08:18" },
    ],
    pullRequests: [
      { id: "#112", title: "feat: global command bar states", author: "Sail", status: "待评审", comments: 4, age: "18 分钟" },
      { id: "#109", title: "feat: docs page tree and spaces", author: "文曲", status: "已通过", comments: 2, age: "2 小时" },
      { id: "#104", title: "design: frosted glass tokens", author: "偃师", status: "有冲突", comments: 7, age: "昨天" },
    ],
  },
  {
    id: "tianxuan-core",
    name: "tianxuan/core",
    namespace: "tianxuan",
    description: "天璇领域核心，覆盖文档、工单状态机与审计事件。",
    language: "Python",
    tone: "cinnabar",
    visibility: "组织内",
    branch: "feat/duobao-merge-queue",
    openPRs: 1,
    commits: 341,
    updated: "34 分钟前",
    status: "进行中",
    files: [
      { name: "server", kind: "dir", message: "feat: merge queue proposal event", author: "多宝", when: "34 分钟前" },
      { name: "server/tianxuan_core.py", kind: "file", message: "refactor: expose block anchors", author: "文曲", when: "3 小时前" },
      { name: "server/test_tianxuan_core.py", kind: "file", message: "test: event transition coverage", author: "夸父", when: "昨天" },
      { name: "docs", kind: "dir", message: "docs: acceptance readback", author: "Sail", when: "昨天" },
      { name: "pyproject.toml", kind: "file", message: "chore: pin domain runtime", author: "多宝", when: "11 月 11 日" },
    ],
    commitLog: [
      { sha: "f23c9a1", message: "feat: merge queue proposal event", author: "多宝", when: "34 分钟前" },
      { sha: "a91b04e", message: "refactor: expose block anchors", author: "文曲", when: "3 小时前" },
      { sha: "c04f68d", message: "test: event transition coverage", author: "夸父", when: "昨天" },
      { sha: "38acb11", message: "docs: acceptance readback", author: "Sail", when: "昨天" },
    ],
    pullRequests: [
      { id: "#88", title: "feat: branch lock by target", author: "多宝", status: "待评审", comments: 3, age: "1 小时" },
    ],
  },
  {
    id: "wenqu-editor",
    name: "wenqu/editor",
    namespace: "wenqu",
    description: "文曲 Markdown 编辑器与协同层，Keep the source plain。",
    language: "TypeScript",
    tone: "gold",
    visibility: "私有",
    branch: "main",
    openPRs: 2,
    commits: 214,
    updated: "2 小时前",
    status: "稳定",
    files: [
      { name: "src", kind: "dir", message: "feat: block anchor gutter", author: "文曲", when: "2 小时前" },
      { name: "src/editor.ts", kind: "file", message: "feat: split preview bridge", author: "文曲", when: "5 小时前" },
      { name: "src/block-model.ts", kind: "file", message: "fix: stable block ids", author: "Sail", when: "昨天" },
      { name: "tests", kind: "dir", message: "test: incremental block updates", author: "夸父", when: "昨天" },
      { name: "README.md", kind: "file", message: "docs: keep the source plain", author: "文曲", when: "11 月 12 日" },
    ],
    commitLog: [
      { sha: "b81fa34", message: "feat: block anchor gutter", author: "文曲", when: "2 小时前" },
      { sha: "0e7d5c2", message: "feat: split preview bridge", author: "文曲", when: "5 小时前" },
      { sha: "4ac22b9", message: "fix: stable block ids", author: "Sail", when: "昨天" },
    ],
    pullRequests: [
      { id: "#47", title: "feat: AI summary gutter", author: "文曲", status: "待评审", comments: 5, age: "2 小时" },
      { id: "#44", title: "fix: caret restore on preview", author: "Sail", status: "已通过", comments: 1, age: "昨天" },
    ],
  },
  {
    id: "tianxuan-design",
    name: "tianxuan/design",
    namespace: "tianxuan",
    description: "设计令牌、纹样与素材清单的只读镜像。",
    language: "CSS",
    tone: "mist",
    visibility: "只读镜像",
    branch: "main",
    openPRs: 0,
    commits: 76,
    updated: "昨天",
    status: "只读",
    files: [
      { name: "tokens", kind: "dir", message: "design: add ink paper palette", author: "偃师", when: "昨天" },
      { name: "tokens/color.css", kind: "file", message: "design: amber focus ring", author: "偃师", when: "前天" },
      { name: "patterns", kind: "dir", message: "design: css-only cloud motif", author: "Sail", when: "11 月 12 日" },
      { name: "README.md", kind: "file", message: "docs: asset handoff note", author: "偃师", when: "11 月 11 日" },
    ],
    commitLog: [
      { sha: "db8a533", message: "design: add ink paper palette", author: "偃师", when: "昨天" },
      { sha: "758c1d0", message: "design: css-only cloud motif", author: "Sail", when: "11 月 12 日" },
    ],
    pullRequests: [],
  },
];

export interface ActivityRecord {
  id: string;
  actor: string;
  actorTone: Tone;
  action: string;
  target: string;
  meta: string;
  time: string;
  kind: "文档" | "工单" | "仓库" | "需求";
  href: string;
}

export const activityFeed: ActivityRecord[] = [
  {
    id: "act-1",
    actor: "文曲",
    actorTone: "jade",
    action: "更新了文档",
    target: "AI-native 文档架构",
    meta: "新增「块级更新」与 3 个稳定性标记",
    time: "8 分钟前",
    kind: "文档",
    href: "/docs/ai-native-docs",
  },
  {
    id: "act-2",
    actor: "司南",
    actorTone: "cinnabar",
    action: "将工单移入评审",
    target: "TX-318 语义检索与自动归类",
    meta: "附上 2 条待回读的验收项",
    time: "34 分钟前",
    kind: "工单",
    href: "/issues",
  },
  {
    id: "act-3",
    actor: "多宝",
    actorTone: "gold",
    action: "推送了 3 个提交",
    target: "tianxuan/core",
    meta: "feat/duobao-merge-queue · f23c9a1",
    time: "1 小时前",
    kind: "仓库",
    href: "/repos",
  },
  {
    id: "act-4",
    actor: "偃师",
    actorTone: "gold",
    action: "生成了验收记录",
    target: "验收记录 · #1085",
    meta: "等待人工确认 4 个未完成项",
    time: "昨天 19:04",
    kind: "需求",
    href: "/docs/acceptance-1085",
  },
  {
    id: "act-5",
    actor: "夸父",
    actorTone: "cinnabar",
    action: "关闭了一个阻塞",
    target: "TX-309 状态机边界",
    meta: "阻塞原因：状态迁移缺少回退路径",
    time: "昨天 18:27",
    kind: "工单",
    href: "/issues",
  },
];

export type RequirementStatus = "澄清中" | "已成稿" | "拆单中" | "已拆单" | "已验收";

export interface RequirementRecord {
  id: string;
  title: string;
  summary: string;
  owner: string;
  status: RequirementStatus;
  progress: number;
  ticketsDone: number;
  ticketsTotal: number;
  updated: string;
  docId: string;
  tone: Tone;
}

export const requirements: RequirementRecord[] = [
  {
    id: "RQ-042",
    title: "AI-native 文档协同 v1",
    summary: "评论、建议模式与块级增量更新进入同一版本快照。",
    owner: "文曲",
    status: "拆单中",
    progress: 64,
    ticketsDone: 7,
    ticketsTotal: 11,
    updated: "12 分钟前",
    docId: "ai-native-docs",
    tone: "jade",
  },
  {
    id: "RQ-039",
    title: "多宝并发合入队列",
    summary: "在不重写 Git 的前提下，隔离分支锁并缩短合入等待。",
    owner: "多宝",
    status: "已成稿",
    progress: 38,
    ticketsDone: 3,
    ticketsTotal: 8,
    updated: "1 小时前",
    docId: "duobao-git",
    tone: "gold",
  },
  {
    id: "RQ-036",
    title: "BYOK 模型凭据与调用审计",
    summary: "凭据在服务端托管，页面只显示状态、额度与最近审计。",
    owner: "文曲",
    status: "澄清中",
    progress: 18,
    ticketsDone: 1,
    ticketsTotal: 6,
    updated: "昨天",
    docId: "ai-tools",
    tone: "mist",
  },
  {
    id: "RQ-031",
    title: "单组织注册与权限边界",
    summary: "首版仅支持单组织与十个以内的协作者。",
    owner: "Sail",
    status: "已验收",
    progress: 100,
    ticketsDone: 5,
    ticketsTotal: 5,
    updated: "11 月 12 日",
    docId: "tianxuan-platform",
    tone: "jade",
  },
  {
    id: "RQ-045",
    title: "全局语义搜索首屏",
    summary: "跨文档、工单与仓库的统一结果，附原文锚点与 AI 摘要。",
    owner: "偃师",
    status: "澄清中",
    progress: 12,
    ticketsDone: 0,
    ticketsTotal: 4,
    updated: "今天 09:20",
    docId: "ai-tools",
    tone: "cinnabar",
  },
];

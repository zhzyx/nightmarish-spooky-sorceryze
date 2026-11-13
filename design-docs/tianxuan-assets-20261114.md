# 天璇 · 美术素材清单与 AI 生成提示词

统一风格：扁平化中国风 + 毛玻璃，深色优先；留白、圆角、对称；云纹/回纹/水波纹作点缀；不出现文字。
色板：墨黑 `#0B0E11`、宣纸白 `#F5F2EA`、朱砂 `#C8402F`、青玉 `#3E8E7E`、鎏金 `#C9A227`、雾灰 `#8A9199`。

> 使用方式：把每条 prompt 直接交给图像 AI；图标/Logo 优先要 SVG 或可矢量化结果，插画要 PNG 透明底。生成后按文件名归档到 `apps/tianxuan/assets/`。

## A. 品牌

| ID | 素材 | 规格 | 提示词 |
|---|---|---|---|
| A1 | Logo 图形（天璇） | 512×512，SVG | Flat vector logo mark for a Chinese-style AI knowledge platform, abstract star/compass constellation inspired by the Big Dipper's Tianxuan star, geometric jade-green and cinnabar-red lines on ink-black, frosted glass halo, minimal, symmetrical, no text, no gradient banding, clean SVG. |
| A2 | Logo 横版 | 1200×320，SVG | Horizontal lockup: the Tianxuan star mark on the left, generous whitespace on the right reserved for a wordmark, flat Chinese aesthetic, ink-black background, jade and cinnabar accents, no text, vector. |
| A3 | 应用图标 | 1024×1024，PNG | App icon, rounded square, deep ink-black frosted glass, centered minimal Chinese star compass mark in jade green with a thin gold ring, subtle paper texture, soft inner glow, flat, no text. |
| A4 | Favicon | 64×64，PNG/SVG | Simplified Tianxuan star glyph, two-tone jade and cinnabar, dark rounded square, crisp at 32px, no text. |

## B. 图标（线性 + 圆角，24×24，SVG）

| ID | 素材 | 提示词 |
|---|---|---|
| B1 | 导航图标组（首页/文档/工单/仓库/搜索/AI/设置/通知/用户/退出） | Minimal line icon set, 24px grid, 2px rounded strokes, Chinese flat aesthetic, subtle seal-script corner detail, monochrome ink with optional jade accent, no text, SVG. |
| B2 | 状态图标（待办/计划/进行中/评审/完成/阻塞） | Status glyph set, circular badges, flat, jade for done, cinnabar for blocked, gold for review, muted gray for backlog, minimal, 24px, SVG. |
| B3 | 动作图标（新建/编辑/删除/评论/分享/导出/筛选/排序/历史/分支/提交/PR/合并/冲突） | Action icon set, 24px, rounded 2px strokes, flat Chinese minimal, consistent visual weight, no text, SVG. |
| B4 | 文档块图标（标题/列表/任务/代码/表格/引用/图片/附件/嵌入） | Editor block icon set, 24px, flat, ink line style with jade accents, no text, SVG. |

## C. 空状态插画（800×600，PNG 透明底）

| ID | 素材 | 提示词 |
|---|---|---|
| C1 | 暂无文档 | Flat Chinese-style empty state illustration: an open scroll on a frosted glass desk, faint cloud pattern, ink-black background, jade and cinnabar accents, generous negative space, no text, transparent PNG. |
| C2 | 暂无工单 | Empty state: a minimal kanban board outline with empty cards, floating seal stamp, frosted glass, Chinese flat style, no text, transparent PNG. |
| C3 | 暂无仓库 | Empty state: a stylized git branch as a jade vine over ink-black, subtle gold nodes, flat Chinese minimal, no text, transparent PNG. |
| C4 | 无搜索结果 | Empty state: a magnifier over faint cloud patterns, muted ink palette, frosted glass, no text, transparent PNG. |
| C5 | 离线 | Empty state: a paper kite disconnected from a thin gold line, calm ink background, no text, transparent PNG. |
| C6 | AI 空白 | Empty state: a soft glowing orb with a Chinese cloud ring, jade core, frosted glass, no text, transparent PNG. |

## D. 引导插画（1200×800，PNG）

| ID | 素材 | 提示词 |
|---|---|---|
| D1 | 需求→文档 | Flat Chinese-style onboarding illustration: a conversation bubble flowing into a scroll, ink-black background, jade and cinnabar accents, frosted glass layers, no text, 1200×800. |
| D2 | 文档→工单 | Onboarding illustration: scroll transforming into a kanban card tree, thin gold connectors, flat Chinese minimal, no text. |
| D3 | 工单→代码 | Onboarding illustration: kanban card connecting to a git branch and commit nodes, jade line, ink background, no text. |

## E. 材质与背景

| ID | 素材 | 提示词 |
|---|---|---|
| E1 | 毛玻璃底纹 | Seamless frosted glass texture, dark ink background, very subtle noise and blur, no visible pattern, 2048×2048, PNG. |
| E2 | 中国纹样平铺 | Seamless flat Chinese cloud-and-wave pattern (云纹/回纹), low-contrast ink on dark, 1024×1024, PNG/SVG. |
| E3 | 背景渐变 | Deep ink to charcoal gradient with faint jade aurora, smooth, no banding, 2560×1440. |
| E4 | 顶栏材质 | Frosted glass top bar texture, translucent, subtle blur, dark, 2560×128. |

## F. 社交与占位

| ID | 素材 | 提示词 |
|---|---|---|
| F1 | OG 分享图 | 1200×630 social card: Tianxuan star mark, frosted glass panel, flat Chinese style, ink background, jade/cinnabar accents, no text. |
| F2 | 头像占位组 | 8 flat Chinese-style abstract avatars, geometric seal motifs, muted palette, circular, no text, SVG/PNG. |
| F3 | 加载动画帧 | Minimal Tianxuan star orbit loader, 12 frames, flat, jade on ink, no text, PNG sequence. |

## G. 交付约定

- 图标与 Logo：优先 SVG，统一 24px 网格与 2px 描边。
- 插画：PNG 透明底，长边 ≥1600px。
- 命名：`<ID>-<slug>.<ext>`，例如 `A1-logo-mark.svg`。
- 生成后由天璇设计系统落地为 tokens 与组件，不直接把位图当 UI 图标。

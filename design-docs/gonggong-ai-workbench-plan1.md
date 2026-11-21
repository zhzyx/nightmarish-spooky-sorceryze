<!-- gonggong-request:gonggong-ai-workbench-plan1 -->

# Godot 原生 AI 工作台整合设计 · 方案一

面向策划、程序、美术及其他获准职能，在 Windows 和 macOS 的 Godot 编辑器内，通过一个原生入口访问 AI。上下文按业务模块与工单隔离。用户可引用当前页面、节点、脚本、资源和文档，在原窗口预览并验证。

默认咨询，讨论形成偃师可编辑的设计文档。确认设计后，由对应用户逐个指定任务执行到的目标阶段及到达条件。司南根据能力分配本机模型和 Agent。创意选择由发起人负责，可转给其他用户。人可以直接修改文档、代码或资产，AI 从实际的新修订继续工作。

退出 Godot 时保存检查点并停下本任务进程。再次打开时优先呈现需要本人判断的事项，其他已授权工作按原目标接续。产品最终由天璇记录工单与设计，多宝管理代码历史、分支、提交与合入；历史工单可打开原件。

[GitHub 总单 #1709](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1709)。来源为已确认的方案一工作簿。登记操作者 Sail-Li，模块责任者在领取对应子项时登记，创意仍由发起人或受让人判断。

## 本次登记与完成判定

本批在 GitHub 登记方案一工作簿的全部 164 个单点。M0 至 M7 的八张 K 系列验收卡同时作为原生阶段父单，各在 164 项内计一次。总单额外设一张，不计入 164。本次登记授权仅涵盖建单、设计关联和依赖登记，产品开发按各自授权推进。

每一项以实际修订、候选接收和该卡通过条件为依据。验收通过即可独立按 completed 关单。关单回执须列出直接后继并复核其余前置。取消、重复标记、未验证合入或仅写计划均不计完成。所有 164 项都已验收并以 completed 关闭、K07 组合验收成立后，再关闭总单。重开子项时复核阶段和总单。

四个初始单点为 B01、B02、B03、B04。工作簿四槽示例共 49 批，每个普通节点预估 45–60 分钟主动工作；机器长作业与人工判断另计。

## 任务清单

## M0　基线与复用边界

### B01

[编辑器入口及复现路径](gonggong-ai-workbench-b01.md)

**清点 Godot 原生入口** · [B01 #1873](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1873)

列出现有 AI Chat、天枢、3D 面板、工具弹窗和其他可交互表面，标记现有挂载点。

验收：每个现有入口有源码定位、替代去向和可复现打开方式，保留马良等独立业务能力。

前置：可首先领取。后继：[B05 #1827](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1827)、[B06 #1872](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1872)、[B07 #1719](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1719)。

### B02

[天璇与偃师接口矩阵](gonggong-ai-workbench-b02.md)

**核对天璇与偃师已有接口** · [B02 #1870](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870)

从服务与已有用例编制工单、文档、会话、判断能力矩阵。

验收：每个需求对应一个现有接口及证据，或一个具名缺口；注明身份、版本与访问范围。

前置：可首先领取。后继：[B05 #1827](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1827)、[B07 #1719](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1719)、[C01 #1868](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1868)、[D14 #1867](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867)、[I12 #1790](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1790)。

### B03

[天枢与司南执行路径](gonggong-ai-workbench-b03.md)

**核对天枢与司南执行路径** · [B03 #1874](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1874)

追踪当前一单从聊天到本机、阶段回执和退出的调用路径。

验收：有一个正常入口、一条失败回执和一份本机生命周期差异表。

前置：可首先领取。后继：[B06 #1872](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1872)、[B07 #1719](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1719)、[D01 #1862](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1862)。

### B04

[Git 与多宝历史标识对照](gonggong-ai-workbench-b04.md)

**核对多宝历史承载能力** · [B04 #1853](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1853)

比对原仓库历史、分支、标签语义与多宝现有导入、合入接口。

验收：以一个真实提交和一个标签给出双侧定位；列出标识能否原样保留。

前置：可首先领取。后继：[B07 #1719](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1719)、[G01 #1837](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1837)、[G02 #1852](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1852)。

### B05

[交付清单与验证](gonggong-ai-workbench-b05.md)

**建立最小业务样例** · [B05 #1827](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1827)

建立角色移动、角色动画两个模块及一个共用资产的隔离样例。

验收：可重复重置，能区分两模块、两用户、同名工单及共享资产。

前置：[B01 #1873](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1873)、[B02 #1870](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870)。后继：[C03 #1806](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1806)、[K00 #1718](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1718)。

### B06

**核定原生构建与回退边界** · [B06 #1872](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1872)

给外壳、资源包与宿主桥各登记实际构建输入及上一可用版本。

验收：改一项输入可判断要重编还是更换资源，并有可执行的回退动作。

前置：[B01 #1873](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1873)、[B03 #1874](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1874)。后继：[K00 #1718](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1718)、[U01 #1871](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1871)。

### B07

[交付清单与验证](gonggong-ai-workbench-b07.md)

**建立需求到任务的基线表** · [B07 #1719](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1719)

映射本次决定、旧设计、本次任务和已有候选归属。

验收：关停策略、工单权威源、存量 PR 建议分别可追溯；可复用候选有修订和接收者。

前置：[B01 #1873](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1873)、[B02 #1870](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870)、[B03 #1874](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1874)、[B04 #1853](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1853)。后继：[K00 #1718](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1718)。

### K00

**基础接口与归属已核对** · [K00 #1718](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1718)

核收入口、复用接口、运行路径、历史映射与回退边界。

验收：能从同一基线找到每个生产者、接收者及未验缺口。

前置：[B05 #1827](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1827)、[B06 #1872](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1872)、[B07 #1719](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1719)。后继：[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[K06 #1712](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1712)。

## M1　现场 AI 与模块上下文

### C01

**建立业务模块稳定标识** · [C01 #1868](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1868)

接入项目内模块标识、名称及旧数据默认映射。

验收：两个同名模块可区分，重命名后工单引用不变。

前置：[B02 #1870](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870)。后继：[C02 #1866](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1866)、[C03 #1806](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1806)。

### C02

**建立模块和工单关系** · [C02 #1866](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1866)

保存一模块多工单的查询和关联。

验收：同名工单可分别定位，按模块查询不串单。

前置：[C01 #1868](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1868)。后继：[C04 #1784](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1784)、[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)、[I01 #1859](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859)。

### C03

**关联跨模块的共享资产** · [C03 #1806](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1806)

为同一资源标识保存显式的多个模块关系。

验收：同一模型能从两个模块打开，解除一条关系不破坏另一条。

前置：[B05 #1827](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1827)、[C01 #1868](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1868)。后继：[C07 #1785](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785)、[V07 #1801](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1801)。

### C04

**恢复模块的最近工作位置** · [C04 #1784](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1784)

按用户、项目和模块保存活动工单、对话与位置。

验收：A 切 B 再回 A 恢复 A；另一用户登录看不到 A 的私人位置。

前置：[C02 #1866](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1866)。后继：[C06 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744)、[D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748)、[I13 #1755](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755)。

### C05

**形成单次消息的上下文快照** · [C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)

在发送时固定项目、模块、工单、对象和所用修订。

验收：发送后切选区，已发送消息仍指向原对象与修订。

前置：[C02 #1866](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1866)。后继：[C08 #1839](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1839)、[D01 #1862](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1862)、[U08 #1829](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1829)、[U10 #1760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1760)、[U11 #1811](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1811)、[U12 #1809](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1809)、[U15 #1810](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1810)。

### C06

**显式切换业务模块** · [C06 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744)

将模块选择器接到已有工作位置。

验收：切换两次能回到原工单、会话及草稿。

前置：[C04 #1784](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1784)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)。

### C07

**处理无归属和多归属资产** · [C07 #1785](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785)

从单独打开的资产选择已有业务关系，或仅作引用。

验收：无关系不擅自建单，多关系需选择，从工单打开沿用原归属。

前置：[C03 #1806](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1806)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[U14 #1761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)。

### C08

**关联失效时更新当前引用** · [C08 #1839](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1839)

处理资源删除、场景切换和过期节点路径。

验收：删除或换场景后显示失效，发送时不能误用同名替代节点。

前置：[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)。后继：[U07 #1828](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828)、[U09 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830)。

### U01

**注册全局原生命令** · [U01 #1871](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1871)

给工作台建立唯一可路由的打开命令，保留已有布局可启动。

验收：从两个主屏调用同一命令得到同一实例；重复触发不新建。

前置：[B06 #1872](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1872)。后继：[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。

### U02

**挂载可停靠原生侧栏** · [U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)

为该命令挂载原生侧栏并在关闭时还原焦点。

验收：输入中打开、收起后焦点回到原控件，场景视口可继续编辑。

前置：[U01 #1871](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1871)。后继：[C06 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744)、[C07 #1785](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785)、[D14 #1867](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867)、[G09 #1780](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1780)、[G10 #1844](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1844)、[I12 #1790](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1790)、[U03 #1807](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1807)、[U04 #1808](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1808)、[U05 #1840](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1840)、[U06 #1745](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745)、[U07 #1828](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828)、[U08 #1829](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1829)、[U09 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830)、[U12 #1809](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1809)、[U15 #1810](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1810)。

### U03

**从固定按钮唤起侧栏** · [U03 #1807](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1807)

在编辑器外壳注册唯一可见工作台按钮。

验收：从 2D、3D、脚本主屏打开同一侧栏，焦点落到输入框。

前置：[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[U13 #1791](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791)。

### U04

**接入可重绑定快捷键** · [U04 #1808](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1808)

通过编辑器快捷键系统唤起同一面板。

验收：默认与重绑定键均可用，输入框内普通快捷键不被截获。

前置：[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[U13 #1791](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791)。

### U05

**展开与还原完整工作台** · [U05 #1840](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1840)

保留侧栏状态并在原生完整视图与侧栏之间切换。

验收：往返后草稿、滚动位置、选区与光标可恢复。

前置：[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835)、[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[S07 #1763](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1763)、[U13 #1791](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791)。

### U06

**从弹窗和辅助窗口请求 AI** · [U06 #1745](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745)

将宿主管理的模态或独立编辑窗口映射到同一工作台会话。

验收：模态内可引用当前内容并返回，未保存输入与原焦点保留。

前置：[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)。

### U07

**把 2D 和 3D 节点作为引用** · [U07 #1828](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828)

在共用场景节点接口传递节点路径、场景修订与选区。

验收：分别选 2D、3D 节点后对应草稿引用准确，多选可辨识。

前置：[C08 #1839](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1839)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)、[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[U14 #1761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)。

### U08

**把脚本选段作为引用** · [U08 #1829](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1829)

提取脚本、行区间和文本修订。

验收：两个同名脚本路径可区分，切换前后的发送内容正确。

前置：[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[E03 #1816](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1816)、[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)。

### U09

**把检查器与文件系统选择作为引用** · [U09 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830)

复用资源定位接口从检查器与文件列表引入对象。

验收：同名资源分目录可区分，未保存资源显示临时身份。

前置：[C08 #1839](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1839)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)、[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)。

### U12

**给其他编辑器页面提供通用引用** · [U12 #1809](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1809)

为未提供专用选区的内置或扩展页面提供页面级引用。

验收：在清单中挑一个扩展页，发送前可见页面名、模块和实际可读范围。

前置：[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[U16 #1793](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1793)。

### U15

**显示本轮引用并允许移除** · [U15 #1810](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1810)

输入框上方呈现模块、工单、选区及引用修订。

验收：移除脚本引用后发送，载荷和可见内容一致，工单不变。

前置：[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748)、[U16 #1793](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1793)。

### K01

**从编辑现场抵达模块对话** · [K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)

用两模块共享资产的样例走进出编辑器的最小路径。

验收：现场打开 AI、明确归属并返回原视口，跨模块草稿隔离。

前置：[C06 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744)、[C07 #1785](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785)、[D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748)、[K00 #1718](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1718)、[U03 #1807](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1807)、[U04 #1808](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1808)、[U05 #1840](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1840)、[U06 #1745](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745)、[U07 #1828](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828)、[U08 #1829](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1829)、[U09 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830)、[U12 #1809](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1809)。后继：[K02 #1716](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1716)。

## M2　设计与天璇工单

### D01

**建立咨询会话并隔离执行** · [D01 #1862](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1862)

接入当前模型对话，默认只回答和形成草稿。

验收：“请改代码”在未授权会话仅输出建议；可在同一会话继续追问。

前置：[B03 #1874](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1874)、[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)。后继：[D03 #1860](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860)、[D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748)。

### D02

**在 Godot 打开设计文档** · [D02 #1865](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1865)

用既有天璇文档标识打开可定位段落的原生视图。

验收：从两份同名文档跳转至目标段，修订号一致。

前置：[D14 #1867](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867)。后继：[D03 #1860](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860)、[D04 #1863](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1863)、[U10 #1760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1760)。

### D03

**从咨询形成偃师设计草稿** · [D03 #1860](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860)

把讨论形成的目标、方案、待决项与验收写入设计草稿。

验收：问答能追溯到文档；用户已写段落不被重复生成。

前置：[D01 #1862](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1862)、[D02 #1865](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1865)。后继：[D05 #1786](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1786)、[D09 #1858](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1858)。

### D04

**手工创建并保存设计正文** · [D04 #1863](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1863)

允许先写后聊，首次保存建立修订并可再编辑。

验收：纯手工编写、关闭、重开，段落与作者可回读。

前置：[D02 #1865](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1865)。后继：[D05 #1786](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1786)、[D06 #1861](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861)、[D07 #1787](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1787)。

### D05

**AI 局部更新设计段落** · [D05 #1786](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1786)

把建议应用为指定段落的候选修订。

验收：接受一段只改该段，其余段落逐字一致。

前置：[D03 #1860](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860)、[D04 #1863](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1863)。后继：[D11 #1747](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1747)、[Q14 #1727](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1727)。

### D06

**审阅设计差异与恢复版本** · [D06 #1861](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861)

复用版本比较和恢复入口，恢复写入新修订。

验收：A 改 B 再恢复 A，完整历史仍可定位。

前置：[D04 #1863](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1863)。后继：[D09 #1858](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1858)。

### D07

**处理双用户文档编辑** · [D07 #1787](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1787)

接入现有协作通道的远端修订通知。

验收：两人修改不同段均可见；修改同一段提示冲突并保留两份文字。

前置：[D04 #1863](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1863)。后继：[D08 #1746](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1746)。

### D08

**保存断线时的文档草稿** · [D08 #1746](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1746)

重连前保留本地编辑，重连后比较服务器修订。

验收：断线编辑再重连，旧服务器版本不覆盖人的草稿。

前置：[D07 #1787](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1787)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### D09

**确认指定的设计修订** · [D09 #1858](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1858)

记录确认人、修订和验收条件，只授权设计版本。

验收：双击确认只产生一份回执；后来修改正文不会继承旧确认。

前置：[D03 #1860](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860)、[D06 #1861](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861)。后继：[D10 #1857](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1857)、[D13 #1749](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1749)。

### D10

**把已确认设计拆为模块任务** · [D10 #1857](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1857)

把一份设计中可独立验收的条目映射为工单并固定设计修订。

验收：一份设计生成程序和动画两单，各自可追溯同一修订，重复请求不增单。

前置：[D09 #1858](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1858)、[I01 #1859](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859)。后继：[A01 #1856](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1856)。

### D11

**把新需求或局部改动放回既有文档** · [D11 #1747](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1747)

按用户指定的新建或追加目标登记增量设计。

验收：已有角色需求二次调整仅增加本次修订；独立需求可建另一份文档。

前置：[D05 #1786](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1786)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### D12

**恢复模块会话及未发草稿** · [D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748)

保存对话、附件引用与未发内容，按工单重开。

验收：切模块再重开后两份草稿互不覆盖，已经发送的消息不重复。

前置：[C04 #1784](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1784)、[D01 #1862](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1862)、[U15 #1810](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1810)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### D13

**在原生视图追踪偃师设计阶段** · [D13 #1749](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1749)

映射方向、策划、详设的当前状态、确认版本与退回意见。

验收：从原生视图打开对应版本，确认一阶段不会误批后一阶段。

前置：[D09 #1858](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1858)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### D14

**按业务身份接入原生天璇会话** · [D14 #1867](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867)

复用现有认证并把真实用户、项目与权限带入原生请求。

验收：切换账号后读取各自内容，失效凭据提示重新认证且不写入项目。

前置：[B02 #1870](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[D02 #1865](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1865)、[I01 #1859](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859)。

### I01

**通过天璇创建工单** · [I01 #1859](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859)

将新工单写入天璇并返回权威编号与业务模块。

验收：同一建单请求重试只有一条记录；可从天璇按编号回读。

前置：[C02 #1866](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1866)、[D14 #1867](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867)。后继：[D10 #1857](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1857)、[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。

### I02

**读取工单原生详情** · [I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)

展示标题、负责人、工单状态与内容版本。

验收：原生视图与天璇回读一致；缺权限或记录不存在有明确反馈。

前置：[I01 #1859](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859)。后继：[G12 #1825](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1825)、[H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835)、[I03 #1750](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1750)、[I04 #1831](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1831)、[I05 #1788](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1788)、[I06 #1850](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850)、[I07 #1789](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1789)、[I09 #1752](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1752)、[I10 #1753](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1753)、[I11 #1754](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1754)、[I14 #1832](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1832)、[I17 #1758](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1758)、[I19 #1724](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1724)、[U11 #1811](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1811)。

### I03

**维护父子工单** · [I03 #1750](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1750)

从原生详情接入已有父子关系接口。

验收：增挂、解除及拒绝循环均可回读，原工单内容保留。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I04

**维护工单依赖** · [I04 #1831](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1831)

登记依赖与未通过上游的阻塞原因。

验收：上游运行结束但未验收时仍阻塞，上游验收后可推进。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)、[S05 #1812](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812)、[S08 #1792](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1792)。

### I05

**记录工单评论与引用** · [I05 #1788](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1788)

复用评论线程与作者标识，支持回复定位。

验收：两位用户连续回复后顺序与作者正确，重开能回到原评论。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[I16 #1757](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757)。

### I06

**维护负责人和状态** · [I06 #1850](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850)

接入负责人、状态与既有状态迁移规则。

验收：调整后另一视图回读一致，无权限操作保留原状态。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[A02 #1847](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1847)、[H02 #1818](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1818)、[I15 #1756](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1756)。

### I07

**维护迭代与里程碑** · [I07 #1789](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1789)

将迭代、里程碑接到现有计划字段。

验收：移动一个工单后两处统计归属一致，其余工单不变。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[I08 #1751](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1751)。

### I08

**展示模块路线图** · [I08 #1751](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1751)

按已有路线图接口展示模块任务与里程碑。

验收：带父子单的样例可逐层定位到天璇原单。

前置：[I07 #1789](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1789)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I09

**维护自定义字段与阶段** · [I09 #1752](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1752)

通过已有字段定义渲染并保存一个自定义字段及阶段值。

验收：不同项目字段隔离；未知旧字段往返读写仍保留。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I10

**登记预计和实际工时** · [I10 #1753](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1753)

复用天璇工时记录与累计值。

验收：连续登记两条记录及一次重试，累计分钟数正确。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I11

**原生检索并筛选工单** · [I11 #1754](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1754)

按模块、负责人、状态和关键字查询天璇列表。

验收：两个模块同名工单筛选正确；无结果时可清除筛选。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I12

**打开历史工单原件** · [I12 #1790](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1790)

按来源与原始标识打开已有历史工单。

验收：能打开一条真实旧单；链接失效给出来源和标识，操作不改变旧单状态。

前置：[B02 #1870](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[G16 #1782](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1782)、[I13 #1755](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755)。

### I13

**接回天枢在途工单入口** · [I13 #1755](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755)

把原会话、在途记录映射为可访问的原单引用。

验收：重开旧记录保持来源和状态；打开详情不会触发新执行或复制工单。

前置：[C04 #1784](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1784)、[I12 #1790](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1790)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I14

**呈现附件和产物引用** · [I14 #1832](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1832)

从天璇工单打开关联文件及具体版本。

验收：两个修订同时存在时按所选版本打开，失效引用可识别。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[H04 #1819](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1819)、[I18 #1759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1759)。

### I15

**关闭和重开天璇工单** · [I15 #1756](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1756)

从原生详情沿现有验收规则执行关闭或重开。

验收：缺验收证据不能报完成；符合条件时关单可回读，重开保留历史。

前置：[I06 #1850](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I16

**让聊天办理当前工单操作** · [I16 #1757](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757)

在明确授权后把当前工单的一次编辑映射到既有工具。

验收：咨询仅输出草案，授权执行只更新所指工单，UI 与天璇回读一致。

前置：[A03 #1855](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855)、[I05 #1788](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1788)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I17

**接入标签和工单分类** · [I17 #1758](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1758)

在原生详情维护已有标签与工单类型。

验收：按标签回查可找到原单；同名标签在不同项目有正确归属。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I18

**为工单附加和打开文件** · [I18 #1759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1759)

将用户选择的一个文件绑定当前工单及附件版本。

验收：上传后可下载同一摘要，重复操作不创建重复附件。

前置：[I14 #1832](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1832)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### I19

**核对完整 Issue 能力差额** · [I19 #1724](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1724)

对原有 Issue 使用面逐项映射到天璇入口、任务 ID 与异常情形。

验收：每项有已验入口或可单独开聊的缺口卡；仍有缺口时该能力保持开放。

前置：[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

### U10

**把文档段落作为引用** · [U10 #1760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1760)

从原生文档视图传入版本与段落锚点。

验收：段落移动后已发送引用仍能定位旧修订。

前置：[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)、[D02 #1865](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1865)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K02 #1716](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1716)、[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)。

### U11

**把工单详情作为引用** · [U11 #1811](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1811)

将天枢详情的当前工单上下文传给统一面板。

验收：从 A、B 两张工单打开时各自会话正确，默认只咨询。

前置：[C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864)、[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[U13 #1791](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791)。

### U13

**迁移 AI Chat 和天枢的旧入口** · [U13 #1791](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791)

旧入口、持久布局和深链重定向统一工作台，保留原会话定位。

验收：加载上一版布局与工单深链，找到原会话，顶栏只出现一个 AI 入口。

前置：[U03 #1807](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1807)、[U04 #1808](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1808)、[U05 #1840](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1840)、[U11 #1811](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1811)。后继：[U14 #1761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)。

### U14

**迁移 3D 紧凑面板入口** · [U14 #1761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)

将原 3D 快捷入口和资产关联指向统一面板。

验收：从已关联模型打开正确工单，原预览视口和未发草稿保留。

前置：[C07 #1785](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785)、[U07 #1828](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828)、[U13 #1791](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K02 #1716](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1716)、[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)。

### K02

**从设计修订抵达天璇工单** · [K02 #1716](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1716)

验收偃师设计、原生工单、历史引用与咨询连续性。

验收：确认一次产生可追溯独立工单，旧单只作来源；完整能力清单逐项有证据。

前置：[K01 #1717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)、[Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)、[U10 #1760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1760)、[U14 #1761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)。后继：[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)。

## M3　逐任务授权与本机司南

### A01

**定义任务目标阶段与到达条件** · [A01 #1856](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1856)

保存任务、设计修订、目标阶段、可验证标准与负责用户。

验收：同设计的两项任务可指定不同目标，一个目标缺标准时退回。

前置：[D10 #1857](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1857)。后继：[A02 #1847](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1847)、[A03 #1855](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855)、[H01 #1843](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1843)。

### A02

**让对应用户逐项确认启动** · [A02 #1847](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1847)

原生显示各项任务阶段与到达标准并记录确认身份。

验收：同屏选两项只确认其中一项，另一项继续待确认。

前置：[A01 #1856](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1856)、[I06 #1850](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850)。后继：[A05 #1762](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762)、[S03 #1845](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845)。

### A03

**在执行入口校验阶段授权** · [A03 #1855](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855)

接入司南前匹配任务、授权人、修订和阶段上限。

验收：有效授权到达本机，缺失、撤销或旧修订不会触发工具。

前置：[A01 #1856](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1856)。后继：[A04 #1841](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841)、[E01 #1834](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1834)、[I16 #1757](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757)、[S01 #1851](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1851)、[U16 #1793](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1793)。

### A04

**在目标阶段精确停止** · [A04 #1841](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841)

到达标准满足后记录产物和结果并停止自动推进。

验收：授权到预览时只生成预览，后续交付步骤调用数为零。

前置：[A03 #1855](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855)。后继：[A05 #1762](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762)、[R01 #1836](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1836)、[S05 #1812](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812)、[V08 #1772](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1772)。

### A05

**显式续授下一阶段** · [A05 #1762](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762)

记录新目标、判断人和续授回执。

验收：从已到阶段继续不重跑既有步骤；未续授保持可查看。

前置：[A02 #1847](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1847)、[A04 #1841](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)。

### S01

**把工单能力要求交给司南** · [S01 #1851](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1851)

把模块任务所需能力投影到已有司南路由。

验收：程序和资产任务得到各自适配结果；无匹配能力时给出缺口。

前置：[A03 #1855](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855)。后继：[S02 #1848](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1848)。

### S02

**匹配当前本机的模型与 Agent** · [S02 #1848](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1848)

读取可用本机 CLI 或模型，解释所选 Agent 与能力映射。

验收：样例暴露两种能力，匹配准确；缺凭据显示实际缺口。

前置：[S01 #1851](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1851)。后继：[S03 #1845](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845)。

### S03

**启动唯一一次本机工作者** · [S03 #1845](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845)

把已确认任务绑定本机句柄和稳定调用标识。

验收：重复点击、重连重复发送只产生一个实际工作者。

前置：[A02 #1847](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1847)、[S02 #1848](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1848)。后继：[R01 #1836](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1836)、[S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)、[S08 #1792](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1792)。

### S04

**把执行进度写回天璇** · [S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)

把工具步骤、阶段、产物引用和真实状态接入工单。

验收：按回执顺序可追踪一条真任务，旧进度事件不会覆盖新状态。

前置：[S03 #1845](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845)。后继：[S05 #1812](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812)、[S06 #1833](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1833)、[S07 #1763](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1763)、[S09 #1813](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1813)、[S10 #1814](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1814)、[V08 #1772](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1772)。

### S05

**根据依赖接续下一步** · [S05 #1812](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812)

在依赖实际验收、授权阶段未到时响应事件启动下一步。

验收：同一完成回执重复到达只推进一次；验收未过仍阻塞。

前置：[A04 #1841](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841)、[I04 #1831](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1831)、[S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)。后继：[H06 #1768](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1768)、[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)。

### S06

**区分可重试故障与待处理阻塞** · [S06 #1833](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1833)

沿现有排障路径记录动作、原因、已知副作用和恢复条件。

验收：模拟一次暂时失败能继续；回执未知时先查原调用。

前置：[S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)。后继：[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[R06 #1822](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1822)。

### S07

**显示运行任务和阶段进度** · [S07 #1763](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1763)

原生视图接回天枢已有步骤、运行状态、阻塞和产物。

验收：从模块和工单两处打开同一任务看到相同运行号与最新回执。

前置：[S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)、[U05 #1840](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1840)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)。

### S08

**隔离独立任务并发占用** · [S08 #1792](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1792)

按可分离写入范围使用本机槽位，冲突范围排队。

验收：两个独立任务可同时跑；两任务写同一资产时可见等待者。

前置：[I04 #1831](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1831)、[S03 #1845](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845)。后继：[H06 #1768](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1768)、[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[R09 #1778](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1778)。

### S09

**按真实终态核收结果** · [S09 #1813](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1813)

等实际工作者退出、必要输出落库后再把结果交给后继。

验收：进程已退但输出写入失败时仍待核对，完整回执才开放验收。

前置：[S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)。后继：[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)、[R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)。

### S10

**把暂停与取消操作接回当前工单** · [S10 #1814](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1814)

在任务面板按运行号暂停或取消，保留已完成结果。

验收：停止 A 不影响 B；恢复 A 前核对原授权和副作用，取消项重开不自启。

前置：[S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)。后继：[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)。

### U16

**从任意原生页面带入当前内容进行工作** · [U16 #1793](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1793)

在共用页面协议公开可读内容、可用编辑动作及所需授权。

验收：新注册的示例面板能引用一个字段、预览修改，并在授权后只更改该字段。

前置：[A03 #1855](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855)、[U12 #1809](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1809)、[U15 #1810](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1810)。后继：[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)、[V09 #1773](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1773)。

### K03

**从逐项授权抵达本机目标阶段** · [K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)

按一份设计给两项任务指定不同终点，检查自动调度与回写。

验收：两项均按各自阶段结束，未授权任务无工作者，终态回读一致。

前置：[A05 #1762](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762)、[K02 #1716](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1716)、[S05 #1812](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812)、[S06 #1833](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1833)、[S07 #1763](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1763)、[S08 #1792](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1792)、[S09 #1813](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1813)、[S10 #1814](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1814)、[U16 #1793](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1793)。后继：[K04 #1714](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1714)、[K05 #1713](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1713)。

## M4　人工修改、创意判断与验证

### E01

**记录本轮 AI 工作的起始修订** · [E01 #1834](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1834)

开始工作时固定目标路径、业务模块和原始内容摘要。

验收：任务打开后人修改原件，系统仍可识别起始版与最新版。

前置：[A03 #1855](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855)。后继：[E02 #1815](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1815)、[E03 #1816](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1816)、[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。

### E02

**识别文档的人工作者修订** · [E02 #1815](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1815)

订阅保存事件并登记人改段落、版本和作者。

验收：手改一个段落后，下一轮输入准确引用该段与最新版本。

前置：[E01 #1834](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1834)。后继：[E06 #1795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1795)、[E07 #1796](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1796)、[E10 #1765](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1765)。

### E03

**识别人工保存的脚本修订** · [E03 #1816](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1816)

连接 Godot 脚本保存与外部修改回读。

验收：手改一行后下一轮读到新内容；光标移动不触发新修订。

前置：[E01 #1834](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1834)、[U08 #1829](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1829)。后继：[E06 #1795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1795)、[E07 #1796](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1796)、[E10 #1765](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1765)、[V03 #1799](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1799)。

### E04

**识别场景或资源的人工保存** · [E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)

记录序列化场景或资源的身份、修订及操作者。

验收：保存材质或节点属性后重开有新修订，未修改依赖仍指原版。

前置：[E01 #1834](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1834)、[U07 #1828](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828)、[U09 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830)。后继：[E05 #1794](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1794)、[E06 #1795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1795)、[E09 #1797](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1797)、[E10 #1765](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1765)、[V04 #1800](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1800)。

### E05

**识别动画轨道的人工编辑** · [E05 #1794](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1794)

将保存的人工关键帧改动定位到轨道与时间片。

验收：手调一个关键帧后可定位该轨道，其他轨道摘要保持一致。

前置：[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)。后继：[E11 #1766](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1766)、[V06 #1771](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1771)。

### E06

**将人的最新修订交给继续工作的 AI** · [E06 #1795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1795)

接续前带入最新原件、从起始版到当前版的改动和保留意见。

验收：在文档、脚本、资源样例中接续输入均含人的最新改动。

前置：[E02 #1815](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1815)、[E03 #1816](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1816)、[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)。后继：[E11 #1766](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1766)、[E12 #1767](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1767)、[Q14 #1727](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1727)。

### E07

**合并互不重叠的文本修改** · [E07 #1796](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1796)

将 AI 候选相对基线的独立段或行应用到人改后的版本。

验收：人改第一段、AI 改末段，最终两者均保留且可看差异。

前置：[E02 #1815](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1815)、[E03 #1816](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1816)。后继：[E08 #1764](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1764)、[E12 #1767](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1767)。

### E08

**由人解决文本重叠冲突** · [E08 #1764](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1764)

把基线、人的当前版和 AI 候选放入原生差异界面。

验收：可保留人的版本、选 AI 片段或直接写第三版，确认后产生新修订。

前置：[E07 #1796](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1796)、[H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)、[Q15 #1728](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1728)。

### E09

**保存二进制或不可合并资产候选** · [E09 #1797](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1797)

遇到人已改过的纹理、模型等资源时保留独立候选。

验收：人工原件摘要不变，两个资产均可预览并显式选定。

前置：[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)、[H04 #1819](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1819)。后继：[V05 #1770](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1770)。

### E10

**在窗口内直接修订创意原件** · [E10 #1765](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1765)

从判断项跳到对应原生编辑器，保存后返回该判断项。

验收：对选定样例手改、保存、返回，待判断修订随之更新。

前置：[E02 #1815](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1815)、[E03 #1816](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1816)、[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)、[H04 #1819](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1819)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)。

### E11

**保留局部动画修改并继续生成** · [E11 #1766](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1766)

将人指定保留的轨道或关键帧作为本次调整边界。

验收：固定落地姿势、压缩前半段；回读关键帧一致且前段时长已变。

前置：[E05 #1794](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1794)、[E06 #1795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1795)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)。

### E12

**让 AI 在人的脚本修改上继续工作** · [E12 #1767](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1767)

把续写候选应用到用户最后保存的脚本并展示差异。

验收：人更改函数参数后，AI 更新一个调用点，原参数修改保留且定向检查通过。

前置：[E06 #1795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1795)、[E07 #1796](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1796)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q15 #1728](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1728)。

### H01

**把创意任务默认交给发起人** · [H01 #1843](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1843)

创建创意判断项时固定发起人、责任人和目标产物修订。

验收：他人代执行不改变判断人，新产物有独立待判断项。

前置：[A01 #1856](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1856)。后继：[H02 #1818](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1818)、[H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835)。

### H02

**转交创意判断责任** · [H02 #1818](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1818)

将待判断项、原始设计、修订和既有意见交给目标用户。

验收：A 转给 B 后 B 能处理，A 的旧页面不能再作决定，历史可追踪。

前置：[H01 #1843](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1843)、[I06 #1850](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850)。后继：[H05 #1798](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1798)。

### H03

**显示本人的待判断事项** · [H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835)

按登录人列出具体产物、待解决的问题和到达入口。

验收：两用户待办互相隔离，点击直接开对应修订。

前置：[H01 #1843](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1843)、[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)、[U05 #1840](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1840)。后继：[E08 #1764](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1764)、[H04 #1819](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1819)、[R08 #1777](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1777)。

### H04

**并排比较创意候选** · [H04 #1819](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1819)

展示候选差异、关联设计及修订号，并能打开原件。

验收：同一任务两版成果可区分；打开 A 不会操作 B。

前置：[H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835)、[I14 #1832](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1832)。后继：[E09 #1797](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1797)、[E10 #1765](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1765)、[H05 #1798](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1798)。

### H05

**把采纳或退回绑定到版本** · [H05 #1798](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1798)

由当前判断人选择、退回或提交修改意见并保留签认。

验收：未选方案保留；A 的确认不能批准随后生成的 B；AI 身份不可代签。

前置：[H02 #1818](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1818)、[H04 #1819](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1819)。后继：[H06 #1768](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1768)、[Q02 #1738](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1738)。

### H06

**阻塞待判断支路并继续其他支路** · [H06 #1768](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1768)

将等待和放行限定到确实依赖该决定的任务。

验收：动画待人选稿时程序继续；选定后只唤醒对应后继一次。

前置：[H05 #1798](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1798)、[S05 #1812](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812)、[S08 #1792](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1792)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)。

### V01

**为快速验证建立修订回执** · [V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)

记录验证对象、内容修订、工具、结论与结果位置。

验收：旧版通过后再编辑，新版显示待验证，旧回执仍可查看。

前置：[E01 #1834](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1834)。后继：[V02 #1769](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1769)、[V03 #1799](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1799)、[V04 #1800](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1800)、[V05 #1770](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1770)、[V06 #1771](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1771)、[V07 #1801](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1801)、[V08 #1772](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1772)、[V09 #1773](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1773)。

### V02

**在当前文档查看段落差异** · [V02 #1769](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1769)

并排或逐段查看本次修订并定位到变化段落。

验收：只改一个段落时窗口高亮该段，点回可直接编辑。

前置：[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)、[Q14 #1727](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1727)。

### V03

**在脚本窗口运行定向检查** · [V03 #1799](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1799)

按当前脚本执行已有适用检查并定位错误。

验收：正确及故意错误样例各一次，结果属于所验修订并可跳到行。

前置：[E03 #1816](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1816)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[Q15 #1728](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1728)、[V10 #1774](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1774)。

### V04

**启动当前场景的局部预览** · [V04 #1800](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1800)

从工作台复用场景运行入口和编辑器内嵌预览。

验收：不切换项目即可验证本场景；退出预览回到原编辑状态。

前置：[E04 #1817](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1817)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[V10 #1774](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1774)。

### V05

**在原视口对照资产版本** · [V05 #1770](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1770)

在当前视口切换同一资产的候选与人改版。

验收：相同视角可对照 A/B，退出后原资产引用不变。

前置：[E09 #1797](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1797)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)。

### V06

**在动画时间线回放修改区间** · [V06 #1771](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1771)

原生时间线重播改动前后的区间并显示所用修订。

验收：回放样例能观察前段节奏变化，落地关键帧与原件一致。

前置：[E05 #1794](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1794)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)。

### V07

**只使受影响的验证过期** · [V07 #1801](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1801)

登记验证输入及依赖，收到保存事件时更新受影响项。

验收：改动画时长使动作检查过期，造型审批仍保持原状态。

前置：[C03 #1806](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1806)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[V10 #1774](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1774)。

### V08

**将快速验证回执挂到任务阶段** · [V08 #1772](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1772)

提交目标阶段引用的验证回执并核查对象修订。

验收：旧版绿灯无法使新阶段通过，同修订有效结果可从工单打开。

前置：[A04 #1841](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841)、[S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)。

### V09

**把非文档页面的操作结果就地验证** · [V09 #1773](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1773)

给通用页面动作提供“验证当前修改”入口，调用模块已登记检查。

验收：在业务页手改字段后就地回读，AI 所见数值与页面当前修订一致。

前置：[U16 #1793](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1793)、[V01 #1820](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[K04 #1714](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1714)。

### V10

**登记依赖变更后的定向复验动作** · [V10 #1774](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1774)

从失效回执只触发受影响检查并把结果挂到新修订。

验收：样例修改时长后只重跑指定场景检查，未变资产保留原判断。

前置：[V03 #1799](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1799)、[V04 #1800](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1800)、[V07 #1801](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1801)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)。

### K04

**人改原件后仍可继续生产** · [K04 #1714](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1714)

按文档、脚本及资产三条链验收，核收创意判断人与最新修订。

验收：人改可保留、冲突可处置、同窗验证绑定实际版本，判断有真人回执。

前置：[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[Q09 #1722](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1722)、[V09 #1773](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1773)。后继：[K07 #1711](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1711)。

## M5　退出、恢复与接续

### R01

**持久化任务检查点** · [R01 #1836](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1836)

按任务保存授权、已完成步骤、产物修订、调用标识和待判断指针。

验收：进程重建后从落盘记录读出同一目标，截断写入可回读上一完整记录。

前置：[A04 #1841](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841)、[S03 #1845](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845)。后继：[R02 #1802](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1802)、[R05 #1821](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1821)、[R06 #1822](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1822)。

### R02

**关闭时停止接收新步骤** · [R02 #1802](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1802)

在退出事件进入静止状态，阻止新派发并落下最后检查点。

验收：关闭和下一步完成同时发生时没有新任务越过关闭边界。

前置：[R01 #1836](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1836)。后继：[R03 #1775](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1775)、[R04 #1776](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1776)。

### R03

**在 Windows 停止本任务进程树** · [R03 #1775](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1775)

关闭编辑器时停止本任务登记的父子进程并归还占用。

验收：退出后本任务子进程数为零，另一任务或外部终端仍正常。

前置：[R02 #1802](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1802)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。

### R04

**在 macOS 停止本任务进程树** · [R04 #1776](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1776)

将退出路径接到本任务进程组并核实实际终态。

验收：退出后登记的子进程均停止，其他用户进程不受影响。

前置：[R02 #1802](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1802)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。

### R05

**重开后读取并分类待恢复任务** · [R05 #1821](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1821)

按用户、项目和授权读取检查点，区分已完成、可续、待人判断。

验收：混合四种状态的样例分类正确，换用户不领取别人的任务。

前置：[R01 #1836](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1836)。后继：[R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)、[R09 #1778](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1778)。

### R06

**对账结果未知的外部写入** · [R06 #1822](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1822)

以原调用标识查询天璇写入或多宝提交回执再决定是否补发。

验收：模拟已写但回执丢失和从未写入，最终只有一次业务副作用。

前置：[G11 #1838](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1838)、[R01 #1836](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1836)、[S06 #1833](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1833)。后继：[Q12 #1735](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1735)、[R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)。

### R07

**重开后自动恢复已授权任务** · [R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)

从最后确认的边界自动继续，完整保留原目标阶段。

验收：重开后无需二次授权，已完成步骤没有重跑，达到目标后停止。

前置：[R05 #1821](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1821)、[R06 #1822](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1822)、[S05 #1812](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812)、[S09 #1813](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1813)、[S10 #1814](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1814)。后继：[R08 #1777](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1777)。

### R08

**启动时优先展示待本人判断事项** · [R08 #1777](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1777)

优先打开个人判断队列，同时允许独立恢复任务继续。

验收：存在判断项与可运行任务时，首屏打开前者且后者有真实进展。

前置：[H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835)、[R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。

### R09

**崩溃后收回过期任务占用** · [R09 #1778](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1778)

重开时核对真实进程、原身份与运行号，对无主占用恢复。

验收：模拟崩溃后双开编辑器，只一个实例续领，活着的工作者不被抢占。

前置：[R05 #1821](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1821)、[S08 #1792](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1792)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。

### K05

**跨编辑器重启恢复业务** · [K05 #1713](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1713)

汇总两个原生宿主的退出与恢复及未知回执实测。

验收：两个平台分别有真实终态，重新打开优先显示待判断项，其余任务自动续跑。

前置：[K03 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[Q04 #1731](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1731)、[Q05 #1732](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1732)、[Q12 #1735](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1735)。后继：[K07 #1711](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1711)。

## M6　多宝历史与交付

### G01

**盘点迁移源和开放 PR** · [G01 #1837](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1837)

在只读快照上列出对象规模、引用、开放 PR、LFS 及子模块使用情况。

验收：有时间戳、源修订、引用清单和开放 PR 去向；敏感凭据不入清单。

前置：[B04 #1853](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1853)。后继：[G06 #1824](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1824)、[G16 #1782](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1782)。

### G02

**定义 Git 到多宝的历史映射** · [G02 #1852](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1852)

为提交、父链与多宝标识定义可回查映射，处理合并提交。

验收：双亲合并样例顺序、作者、时间、树和原提交 ID 均可核对。

前置：[B04 #1853](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1853)。后继：[G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)。

### G03

**在隔离仓导入提交历史** · [G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)

用含合并的最小仓验证现有导入器，补齐单一入口。

验收：重跑相同副本无重复；源提交均可反向定位。

前置：[G02 #1852](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1852)。后继：[G04 #1846](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1846)、[G05 #1823](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1823)、[G06 #1824](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1824)、[G08 #1779](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1779)、[G09 #1780](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1780)。

### G04

**导入并核对全部分支引用** · [G04 #1846](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1846)

接入分支名和 tip 对照表，处理非主分支。

验收：同名路径片段及非默认分支的 tips 与原清单逐项相符。

前置：[G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)。后继：[G07 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)、[G10 #1844](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1844)。

### G05

**导入轻量和附注标签** · [G05 #1823](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1823)

保留两类标签的指向、附注对象及原始标识。

验收：两类标签解析正确；已签名的原始对象可按源标识核对。

前置：[G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)。后继：[G07 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)。

### G06

**核对大文件及子模块引用** · [G06 #1824](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1824)

依据真实清单核查 LFS 对象与子模块版本；无实例则记录扫描范围。

验收：样例的指针可回读到实物或固定修订；真实缺失对象逐项列出。

前置：[G01 #1837](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1837)、[G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)。后继：[G07 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)。

### G07

**生成逐引用和对象完整性报告** · [G07 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)

比较计划范围内所有分支、标签、可达提交、树和内容摘要。

验收：删去一个引用或改一份内容均能报出具体差异，正确副本全匹配。

前置：[G04 #1846](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1846)、[G05 #1823](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1823)、[G06 #1824](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1824)。后继：[G17 #1741](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1741)、[G18 #1783](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1783)。

### G08

**从中断位置继续导入** · [G08 #1779](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1779)

为导入批次记录进度并复用已验证对象。

验收：半途终止后续传，结果等价一次完整导入，无重复映射。

前置：[G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)。后继：[G19 #1742](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1742)。

### G09

**在 Godot 浏览多宝历史** · [G09 #1780](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1780)

按提交、文件和版本回看历史，并链接到原始标识。

验收：选中两次修订能区分文件内容并返回关联来源。

前置：[G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。

### G10

**在 Godot 创建和切换多宝分支** · [G10 #1844](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1844)

接入现有分支操作及当前工作副本状态。

验收：从明确基线建分支可回读 tip；未保存编辑在切换前可保全。

前置：[G04 #1846](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1846)、[U02 #1869](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)。后继：[G11 #1838](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1838)。

### G11

**提交用户选择的改动** · [G11 #1838](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1838)

从差异视图选取文件并经多宝提交。

验收：只选择 A 时 B 保留在工作区，重试不重复提交。

前置：[G10 #1844](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1844)。后继：[G12 #1825](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1825)、[G13 #1826](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1826)、[R06 #1822](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1822)。

### G12

**建立工单到多宝提交的关联** · [G12 #1825](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1825)

把工单、分支和提交关联并做双向定位。

验收：从工单找到确切提交，从提交找到原工单；标签移动不改变证据。

前置：[G11 #1838](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1838)、[I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。后继：[G15 #1805](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1805)。

### G13

**发起精确候选的合入请求** · [G13 #1826](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1826)

用来源、目标分支和候选标识发起合入并展示检查状态。

验收：后续新增提交会使旧候选检查失效，目标分支可回读。

前置：[G11 #1838](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1838)。后继：[G14 #1781](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1781)、[G15 #1805](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1805)。

### G14

**处理并行分支合入冲突** · [G14 #1781](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1781)

在冲突候选显示文件差异，解决后重建候选。

验收：两分支改同一行时需处理；解决后双方历史和新检查对象均可追踪。

前置：[G13 #1826](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1826)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。

### G15

**核验合入结果并回写天璇** · [G15 #1805](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1805)

复用已准入审查、检查与合入路径，回读真实目标分支。

验收：被拒绝的请求保持未交付，通过时目标含确切提交且工单能定位。

前置：[G12 #1825](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1825)、[G13 #1826](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1826)。后继：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)、[G18 #1783](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1783)、[Q12 #1735](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1735)。

### G16

**制定存量 PR 的收尾清单** · [G16 #1782](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1782)

按建议逐条指定原平台审查、责任人、后续同步与归档条件。

验收：清单覆盖快照时所有开放 PR，每条有去向；记录需迁移负责方确认的例外。

前置：[G01 #1837](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1837)、[I12 #1790](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1790)。后继：[G17 #1741](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1741)。

### G17

**用一个已合 PR 验证增量同步** · [G17 #1741](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1741)

按原仓真实合入提交增量同步并挂回原始链接。

验收：同一合入重复同步只有一份记录，旧评审从工作台可打开。

前置：[G07 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)、[G16 #1782](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1782)。后继：[G20 #1736](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1736)。

### G18

**演练回退多宝写入入口** · [G18 #1783](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1783)

在副本保存原路由与两侧水位，回退后对账切换期间的新提交。

验收：演练可回原入口并找回新增提交，分支历史无缺口。

前置：[G07 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)、[G15 #1805](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1805)。后继：[G19 #1742](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1742)。

### G19

**用完整仓库副本进行迁移演练** · [G19 #1742](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1742)

对完整固定快照执行导入并生成对象数、字节及逐引用核对报告。

验收：所有在范围引用命中，异常清零或显式阻塞；保留真实耗时与版本。

前置：[G08 #1779](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1779)、[G18 #1783](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1783)。后继：[G20 #1736](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1736)。

### G20

**导入正式代码库基线** · [G20 #1736](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1736)

后续取得目标仓、容量与写入授权后向目标仓上传固定基线。

验收：隔离引用回读与已验清单一致；留存恢复锚点、运行号及写入回执。

前置：[G17 #1741](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1741)、[G19 #1742](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1742)。后继：[G21 #1730](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1730)。

### G21

**追平切换前最后增量** · [G21 #1730](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1730)

在约定交接窗口固定最终源水位并只导入差量。

验收：源和目标的最终分支、标签和可达对象相符，能列出基线后全部变化。

前置：[G20 #1736](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1736)。后继：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)。

### G22

**切换新分支和合入的权威入口** · [G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)

经目标负责人交接后让新分支、提交和合入走多宝。

验收：正常入口建分支、提交、审查并合入测试候选；真实目标回读且无双写。

前置：[G21 #1730](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1730)、[Q04 #1731](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1731)、[Q05 #1732](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1732)、[Q10 #1733](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1733)、[Q11 #1734](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1734)、[Q12 #1735](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1735)。后继：[G24 #1725](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1725)、[Q08 #1721](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1721)。

### G23

**核销存量 PR 的最终同步** · [G23 #1720](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1720)

逐项跟踪清单内 PR 的原平台终态，合入项增量同步，关闭项记录来源。

验收：每条都有实际终态及回读；仍开放的条目继续挂账并可追溯。

前置：[G24 #1725](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1725)。后继：[K06 #1712](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1712)。

### G24

**把原平台未合入 PR 逐项结转** · [G24 #1725](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1725)

每个在途 PR 按原链接登记一个后续核销实例。

验收：给定 PR 可打开旧审查并查询同步状态，新增实例复用源 ID 防止重复。

前置：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)。后继：[G23 #1720](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1720)。

### K06

**多宝接管新开发流程** · [K06 #1712](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1712)

核收整库历史、正式切换与存量 PR 逐项核销。

验收：分支和标签对齐，双向追溯成立，各存量 PR 都有最终处置或保持未完成。

前置：[G23 #1720](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1720)、[K00 #1718](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1718)、[Q08 #1721](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1721)。后继：[K07 #1711](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1711)。

## M7　双平台与整体验收

### F01

**冻结双平台原生组合候选** · [F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)

核收所有原生和运行时输入，生成同一候选的源码与包版本清单，供两个平台各自构建。

验收：候选可精确检出，双方构建清单有相同源码修订；任何替换均产生新的候选记录。

前置：[A05 #1762](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762)、[C06 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744)、[D08 #1746](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1746)、[D11 #1747](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1747)、[D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748)、[D13 #1749](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1749)、[E08 #1764](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1764)、[E10 #1765](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1765)、[E11 #1766](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1766)、[E12 #1767](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1767)、[G09 #1780](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1780)、[G14 #1781](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1781)、[G15 #1805](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1805)、[H06 #1768](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1768)、[I03 #1750](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1750)、[I08 #1751](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1751)、[I09 #1752](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1752)、[I10 #1753](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1753)、[I11 #1754](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1754)、[I13 #1755](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755)、[I15 #1756](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1756)、[I16 #1757](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757)、[I17 #1758](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1758)、[I18 #1759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1759)、[R03 #1775](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1775)、[R04 #1776](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1776)、[R08 #1777](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1777)、[R09 #1778](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1778)、[S07 #1763](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1763)、[U06 #1745](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745)、[U10 #1760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1760)、[U14 #1761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)、[V02 #1769](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1769)、[V05 #1770](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1770)、[V06 #1771](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1771)、[V08 #1772](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1772)、[V09 #1773](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1773)、[V10 #1774](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1774)。后继：[Q06 #1739](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1739)、[Q07 #1740](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1740)。

### Q01

**验证全界面均可唤起同一 AI** · [Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)

按 B01 清单逐表面走入口、引用、返回和焦点恢复。

验收：清单每行有真实结果；设置、主屏、弹窗及扩展页有代表性证据。

前置：[C06 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744)、[U06 #1745](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745)、[U08 #1829](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1829)、[U09 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830)、[U10 #1760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1760)、[U14 #1761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)、[U16 #1793](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1793)。后继：[Q10 #1733](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1733)、[Q11 #1734](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1734)。

### Q02

**验证跨职能工作流与权限** · [Q02 #1738](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1738)

用策划、程序、美术的内部测试身份以及一个无访问身份走同一入口。

验收：前三种按授权工作，无访问者读写被拒，用户判断人及交接记录正确。

前置：[H05 #1798](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1798)。后继：[Q09 #1722](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1722)、[Q10 #1733](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1733)、[Q11 #1734](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1734)。

### Q03

**验证动画手改后 AI 接续和回放** · [Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)

以一条动画工单验证人调落地关键帧、AI 调整前半段、视口对照、判断和阶段回写。

验收：真实修订链和回放回执可定位，人的关键帧与授权停止点均保持。

前置：[E08 #1764](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1764)、[E10 #1765](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1765)、[E11 #1766](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1766)、[H06 #1768](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1768)、[S09 #1813](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1813)、[V02 #1769](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1769)、[V05 #1770](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1770)、[V06 #1771](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1771)、[V08 #1772](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1772)、[V10 #1774](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1774)。后继：[Q09 #1722](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1722)。

### Q04

**验证 Windows 关闭与重开整条链** · [Q04 #1731](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1731)

在 Windows 真实编辑器关闭运行中任务，再重开核对待办与恢复。

验收：退出无残余工作者，重开时待办优先、独立支路续跑，重复提交数为零。

前置：[Q06 #1739](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1739)。后继：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)、[K05 #1713](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1713)。

### Q05

**验证 macOS 关闭与重开整条链** · [Q05 #1732](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1732)

在 macOS 真实编辑器关闭运行中任务，再重开核对待办与恢复。

验收：本机进程组已停，重开后同修订续跑，未越过用户指定阶段。

前置：[Q07 #1740](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1740)。后继：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)、[K05 #1713](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1713)。

### Q06

**构建 Windows 原生候选并安装回读** · [Q06 #1739](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1739)

对冻结组合启动 Windows 全量构建，核对产物后由同一任务出具安装和回退回执。

验收：归档候选、二进制摘要、启动和旧布局读取结果；可恢复原安装。

前置：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。后继：[Q04 #1731](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1731)、[Q10 #1733](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1733)。

### Q07

**构建 macOS 原生候选并安装回读** · [Q07 #1740](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1740)

为同一冻结原生组合构建 macOS 编辑器并在隔离路径启动。

验收：归档候选、应用摘要、启动及原布局回读；回退副本可用。

前置：[F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)。后继：[Q05 #1732](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1732)、[Q11 #1734](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1734)。

### Q08

**交付前核对多宝到天璇的追溯链** · [Q08 #1721](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1721)

从天璇工单依次定位已确认设计、人工修改、验证与多宝实际合入结果。

验收：所有记录指向同一交付版本，任一过期回执能被辨认。

前置：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)。后继：[K06 #1712](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1712)。

### Q09

**收集创意负责人真实验收** · [Q09 #1722](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1722)

请样例发起人或受让人实际选择、修改或退回创意成果并归档理由。

验收：有真实账号、明确决定与确切修订；退回时记录修复后需重新验收的项。

前置：[Q02 #1738](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1738)、[Q03 #1726](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726)、[Q14 #1727](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1727)、[Q15 #1728](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1728)。后继：[K04 #1714](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1714)。

### Q10

**在 Windows 跑原生窗口验收** · [Q10 #1733](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1733)

在冻结候选上回归键盘入口、模态焦点、可停靠窗口和局部预览。

验收：原生 Windows 上四条路径录下候选、结果与至少一个内容引用。

前置：[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)、[Q02 #1738](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1738)、[Q06 #1739](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1739)。后继：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)。

### Q11

**在 macOS 跑原生窗口验收** · [Q11 #1734](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1734)

在同一候选上回归 Cmd 快捷键、模态焦点、停靠及内嵌预览。

验收：原生 macOS 上四条路径录下候选、结果与至少一个内容引用。

前置：[Q01 #1737](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1737)、[Q02 #1738](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1738)、[Q07 #1740](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1740)。后继：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)。

### Q12

**核对真实断回执后的多宝提交** · [Q12 #1735](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1735)

在隔离目标仓丢弃一次提交确认，通过同一工单回读并恢复。

验收：目标仓只有一个提交，天璇只有一条关联，能找到持久回执。

前置：[G15 #1805](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1805)、[R06 #1822](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1822)。后继：[G22 #1729](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1729)、[K05 #1713](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1713)。

### Q13

**核验工单和设计协作的最终组合** · [Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)

从模块原生详情用一个已验样例串联设计修订、子单和依赖，核对其余接入证据。

验收：真实样例可复现；属性及历史来源和固定修订一致，每种接入有候选回执。

前置：[D08 #1746](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1746)、[D11 #1747](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1747)、[D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748)、[D13 #1749](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1749)、[I03 #1750](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1750)、[I04 #1831](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1831)、[I08 #1751](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1751)、[I09 #1752](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1752)、[I10 #1753](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1753)、[I11 #1754](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1754)、[I13 #1755](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755)、[I15 #1756](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1756)、[I16 #1757](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757)、[I17 #1758](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1758)、[I18 #1759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1759)、[I19 #1724](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1724)。后继：[K02 #1716](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1716)。

### Q14

**验证人工直接设计文档后 AI 续写** · [Q14 #1727](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1727)

人先写设计、AI 局部扩展、人再次修改并打开同窗差异。

验收：三次修订可追溯，人的段落按预期保留，差异精确定位变更。

前置：[D05 #1786](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1786)、[E06 #1795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1795)、[V02 #1769](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1769)。后继：[Q09 #1722](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1722)。

### Q15

**验证脚本手改与冲突接续** · [Q15 #1728](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1728)

本机复现一次手改后 AI 续作及一次同一行冲突。

验收：两例各有原件和候选摘要，选定结果通过对应检查。

前置：[E08 #1764](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1764)、[E12 #1767](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1767)、[V03 #1799](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1799)。后继：[Q09 #1722](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1722)。

### K07

**整套工作台组合验收** · [K07 #1711](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1711)

逐项核对全部里程碑、真实候选及已验工作单并归档。

验收：全量闭包有证据与目标分支回读；任一未验修订、未关闭尾项继续开放。

前置：[K04 #1714](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1714)、[K05 #1713](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1713)、[K06 #1712](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1712)。后继：复核全部 164 项后关闭总单。

# 夸父阻塞对账 · 2026-11-23

来源及持续授权：[总单 #426](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/426)。用户要求检查并解决当前工作区所有夸父阻塞。初始回读29张开放单（总单和28张跟踪单）以及269条本机事故。代码基线为 `b5ad3563f541875e493182f2576e3cfae0682826`；本次实现位于独立工作树，既有工作区改动保持原样。

用户本次补充决定：#807/#1530/#1445/#1559 继续保留原暂停范围；#2099/#662/#1540 暂不处理。其他缺少原宿主回执的事项保留具体恢复条件。

## 本次可完成的修复与恢复

- #2105：原失败为并发推送删除临时对象时，本地clone仍复制该目录。改用Git传输；新增回归在旧实现失败，修复后55项测试及98子测试通过，含12路提交、重叠冲突与合入队列。未减少并发或放宽CAS。
- #2131：原11个路径的Ruff及拼写失败已修复，同版本钩子、Python语法和AST核对通过。
- #2112：找回两次原失败日志，错误摘要与事故精确匹配；原基线至成功源候选的raw差异摘要亦与事故index_delta一致。同原操作已签发PR #2113、必要CI实际成功且main包含交付。关闭只代表交付事故恢复，不代表共享站版本发布。

以上两项代码修复与本轮证据同属总单的一次清障候选；各跟踪单独立回读关闭。精确候选CI、独立审查、main与工单关闭回执在总单追加；本地测试不代替这些后续事实。

## 保留事项

| 跟踪单 | 剩余条件与责任 |
| --- | --- |
| [#662](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/662) | 官方CodeBuddy2.176.0 ACP initialize成功，session/new -32000明确需要认证；没有真实业务响应或时延样本。 主责：当前官方CodeBuddy宿主账号所有者/原 #659责任者。2026-11-23：暂不处理。 |
| [#807](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/807) | 39个事故均已找到诊断，8失败作业均有后继对应；最后一组依赖原安装编辑器、原失败游戏权限、重启续办与接收，原责任者明确暂停。 主责：Sail-Li 原 #773 安装/游戏生产责任者及用户。2026-11-23：继续保留原暂停范围；不重启生产/压力验收。 |
| [#833](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/833) | 两次历史Actions运行仍queued且0 jobs。原业务已交付，旧队列无执行诊断；保留原运行。 主责：原发布者及仓库Actions维护者。 |
| [#1349](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1349) | 11本地事件有原责任判断，数值渲染和若干CI子项已恢复；原体积效果视觉质量、完整Windows阴影/级联/动画/画质仍未验收，部分历史签发回执未齐。 主责：kaiyunxue 原渲染路径执行者/指定画质验收者。 |
| [#1353](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1353) | 原生参数表单/业务PR1358通过；8笔intake/delivery工件缺具体失败步骤，一笔e8d2677a基线不可取。 主责：kaiyunxue 原发布宿主。 |
| [#1356](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1356) | 原生节点预览验收通过；8c627200a报告候选043ad62c实际修改端口类型，缺原验证命令，无法认定该事故属于预览测试。 主责：kaiyunxue 原验证宿主。 |
| [#1360](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1360) | 多图顺序/持久化和PR1365业务已通过；三笔validation/delivery原Actions工件无失败诊断，236f87ad候选不可取。 主责：kaiyunxue 原发布宿主。 |
| [#1364](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1364) | 六项部署验收已通过；仅原Windows本机临时目录/传输包删除被宿主自动审批blocked by policy拒绝。 主责：Sail-Li 原受拒宿主有权操作者。 |
| [#1374](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1374) | 两次静态格式失败已由#1385同平台同步骤恢复；两笔本地delivery缺原日志，首笔0ebd16f84240在镜像不存在且GitHub422。 主责：kaiyunxue 原发布宿主。 |
| [#1397](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1397) | 三次delivery均能对应报告基线/源候选，PR1398和main已成功；原Actions工件和扩展Git镜像仍不含逐次失败命令/诊断。 主责：kaiyunxue 原发布宿主。 |
| [#1428](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1428) | 保存功能和正式系统面板已验证，后继#2008已合入；6adfa8f7/5996ad27/142a4da4三次早期delivery缺原命令/候选树，不能区分失败步骤。新增7212fa67缺采集JSON已由#1990接续并后续交付。 主责：kaiyunxue 三次早期发布宿主；Sail-Li 后继验收已记录。 |
| [#1445](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1445) | 40个本地事故需沿分簇记录；剩余stage.rename WinError5原句柄、cp936吞stderr原诊断、Linux300秒运输占时和两名held生产者终态。250 burst也仍延期；后继运行不能解释原未知执行。 主责：Sail-Li 原 #1444/#1499 协调责任者及原 Windows/Linux 宿主。2026-11-23：继续保留原暂停范围；不重启生产/压力验收。 |
| [#1530](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1530) | 正式运行包450文件校验通过；250压力明确延期，原 run44291364937 未同条件恢复，25f58ad67 原本地事件只有初判。 主责：原 #1529 安装/部署责任者与压力试验决策者。2026-11-23：继续保留原暂停范围；不重启生产/压力验收。 |
| [#1540](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1540) | 登录页、WKWebView、合成 Key拒绝/本机有效Key的Cookie链均通过；受影响用户个人Key在正式服务端被拒的原因和恢复未知。 主责：既有生产管理环境有权管理员与原 #1454 责任者。2026-11-23：暂不处理。 |
| [#1555](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1555) | 192 MiB 容器同签发头重跑成功，但首次137底层诊断未留存；后续 Git HTTPS reset 被原发布者明确保留，Git Data API交付不是HTTPS恢复。 主责：Sail-Li 原 Windows 发布宿主。 |
| [#1559](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1559) | 原512MiB容器退出137，未留OOM/终止证据；本次用户再次确认保留250压力暂停范围。 主责：原压力验收责任者。 |
| [#1586](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1586) | 13 个本地事件中 5 有原诊断，8 个仅初判；10 个失败作业有 4 个后继同步骤成功。剩余事故与实际消费者尚未覆盖。 主责：Sail-Li 原 #1581 执行/发布宿主。 |
| [#1627](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1627) | 56263f6a 租户纠正已恢复；另 6 个 validation/delivery 事件缺原失败日志。#1663/#1667 业务交付不补足原操作。 主责：kaiyunxue 原发布宿主。 |
| [#1628](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1628) | Windows SCM 配置服务身份被拒与 Docker 挂载/TLS顺序两事件；Mac 角色测试和 HTTPS 健康已通过，尚缺原 Windows 安装后的跨角色拒绝与服务身份验收。 主责：Sail-Li 原部署管理员/Windows 服务安装责任者。 |
| [#1653](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1653) | 原 Windows 发布环境在 A8 交付后仍复现 HTTPS curl 28/reset；Mac 三次 fetch/ls-remote 成功不覆盖该网络环境。 主责：Sail-Li 原 Windows 发布宿主。 |
| [#1680](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1680) | 9 个本地事故中 a8b0c3aa 有 Apple Git 自动整合版本限制诊断；其余 8 个缺原失败步骤与同操作复验。#1694 合入和成功 CI 证明后继候选，不证明各个历史事故。 主责：kaiyunxue 原发布宿主。 |
| [#1697](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1697) | 早期协调工作者真实终态及事件 9cd69a80 的原始恢复仍缺；#1704 交付与 Mac 故障恢复通过只能覆盖已映射子项。 主责：Sail-Li 原协调宿主/原 #1550 主责。 |
| [#2063](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2063) | 原Windows S05/S06清理曾被自动审批拒绝；两份保留记录和归档已回读。其余两笔已恢复，剩原宿主有权清理或保留决定。 主责：原Windows宿主。 |
| [#2099](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2099) | 用户本次决定暂不处理正式导入身份及授权。 主责：部署端负责人。2026-11-23：暂不处理。 |
| [#2128](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2128) | 原工作区 WORKTREE_UNSTAGED。原责任者已选择隔离23个文件，本地提交源a0ae2645已进入main；未找到原门禁成功及committed回执，不能只按提交存在关闭。 主责：kimi-work-kaiyunxue。 |

相关业务 #414：仍缺真实图像/网格生成及指定安装版Finder重开验收。#1736由#2099承接，本次暂不处理。业务状态与事故关闭分开。

## 验证边界与临时资源

复用 github-issue-delivery/reconcile-workflow-incidents revision 2，按原运行、步骤、场景与候选核对。后继跳过的模块、不同压力基线、仅提交存在及其他主机网络成功均不作为原事故恢复证据。实际测试和逐项事实见 [JSON证据](kuafu-audit-20261123.json)。

私有原日志、原宿主路径及CLI输出留在Git common-dir内，未发布整个事故目录或凭据。只读原宿主记录，不删除其资源、释放未知工作者或重放未知生产者。原清理审批拒绝保留。此次自建测试环境、工作树、分支在交付及工作者终态核实后清理，必要日志保留；清理结果沿总单追加回读。

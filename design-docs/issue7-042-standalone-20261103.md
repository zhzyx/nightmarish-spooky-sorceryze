# 共工 0.4.2 全量同步与 Olympus 独立运行组合候选

工单：[Issue #7](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/7)。稳定需求 ID：`upstream-workflow-upgrade-20261102`。

用户明确要求“同步共工框架的调整，并合并到git仓库”，延续本聊天的独立运行修复。本轮执行责任为当前 Codex 主任务；只更新分发接入，不修改共工、冻结纲领或历史批准。

## 来源与变化

共工当前正式校验通过，模块司南从0.4.1升至0.4.2，源文件由148增至149。新增局部阻塞、待用户判断的关注标记、失败文档隔离与partial结果；没有新增定时调度、自动宿主派发或运行权限。原始审查与外部work证据已保存在忽略目录内的独立源快照，全部文件按内容核对；本仓库不提交整套共工或本机绝对路径。

从当前 Olympus 同步工具开始，移植前轮独立运行修复并保留已合入的名称映射、skill/模块版本兼容；在新目录完整重建149源/137分发。新版上游六项原则结论使用`pass: 理由`；同步器兼容严格`pass`或带非空理由的`pass: `，不放宽批准、证据摘要或基线要求。

启动通过本地 runtime-lock 校验完整文件集合，lock纳入三个Agent候选摘要；正式运行继续核验准入和宿主权限。更新时仍执行真实源的全量核对。不把离线校验当作检查上游最新发布或远程撤销。Hermes扩展逐字保留，生产文件事件在仓库根单独管理。

## 具体交付与验收

- 新候选：仓库相对目录 `.godot-integration-local/issue7-042-standalone/candidate`，尚未启用。
- [适配补丁](patches/issue7-042-standalone-20261103.patch)，针对当前9cbe33c8基线；先在隔离工具副本应用，再完整build，不能直接改活动批准包。
- [来源摘要与测试结果](../data-collection/issue7-042-standalone-verification-20261103.json)：完整build、Python/Node语法及质量归属通过；独立运行10项、Ariadne12项、交付14项测试通过。
- 测试仅用隔离临时合成批准，不写成生产批准；真实供应商/Godot全场景不在本轮测试声明中。

| 对象 | 新组合候选精确摘要 |
| --- | --- |
| Athena | `a415dbe49dd9a6b81ff1a37e6250e51ca5770649b099d9f36716f8ed4041d872` |
| Themis | `b13be5429e999f0c143b37ff94acde7f7365dd19328b5a6037ebbbb7b56422a3` |
| Hermes | `f61033eb4a8121a1157fb397fe7f1dff1830ecaa8bc28c4134726deeda60b779` |

原148源批准和前轮140源独立运行候选均不适用于以上新摘要。待独立审查及新精确批准后，备份并替换活动包，更新工程镜像索引、文档和真实Hermes事件，执行正式框架/Issue门禁及提交后git-check。准入只限本地定义发布，宿主模型和工具权限仍须分别成立。

## Git 合入现状

当前已发布分支的HEAD为9cbe33c8，PR #10仍开放。读取时远程检查包含静态失败、Linux Mono和Android Editor失败及未完成任务；不强行合并或把既有红灯称为通过。新的合并结果需要匹配精确提交的检查。

本页记录本次新同步任务及本地证据；此前被拒绝的旧进度评论不通过其他通道重新发布。

## 实际批准与切换

用户通过 `call_d952ec18fec94b1a96adfc0304b594c4` 回复“批准这三个候选并继续切换与合并”。三个完整摘要均已复核匹配；[独立审查](../data-collection/issue7-042-standalone-review-20261103.json)通过。真实决定和审查原件随精确准入记录放入 Olympus/reviews/local-admission，未复用旧批准。

已备份旧包及本机绑定至忽略目录 `.godot-integration-local/issue7-042-standalone/backup-before-switch`，完成活动包替换；Hermes扩展和根事件目录在切换前后逐字一致。显式把上游环境变量设为不存在路径后，活动框架正式验证仍通过；显式更新check则对锁定149文件源通过。工程镜像索引更新并校验137个非豁免文件，Python20/JS11/JSON51语法通过。运行仍受当前宿主权限与实际事件回执约束。

Git 合并必须等待对应CI通过；当前不能将本地切换等同于默认分支已经合入。

## 合并前既有编译阻塞修复

实际读取 [Linux编译失败](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/41491433061/job/125435518075)，确认 `editor/docks/ai_chat_dock.cpp` 10处及 `ai_chat_olympus.cpp` 1处局部声明遮蔽成员，触发`-Werror=shadow`。关联既有CI工单 #11；作为本次合并必要修复，仅改局部变量名及对应使用，不改编译检查或CLI脚本。

`codex-subagent:review_standalone` 独立只读审查确认：词法归一化后两文件与修复前HEAD完全一致，字符串、序列化键、成员访问和行为不变，所有引用改名完整。clang-format --dry-run --Werror通过；实际编译结果仍等待对应CI。不影响已批准框架文件或候选摘要。

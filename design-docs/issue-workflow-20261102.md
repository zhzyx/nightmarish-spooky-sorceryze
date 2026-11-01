# 工单 Issue 化与工程文档、采集目录

- 需求 ID：`issue-workflow-20261102`
- Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1
- 类别：`type:development`
- 来源：用户要求工单使用 Git Issue、任务类别使用标签，并创建 Markdown 需求和谛听采集目录。

## 目标和方案

以当前仓库的 GitHub Issue 作为工单的唯一执行状态来源；全局标识为仓库名与 Issue 编号。每张工单恰好一个 `type:*` 类别标签，进度、优先级及业务标签可另行并存，不以类别标签推导完成。

需求正文保存于 `design-docs/`。Issue 引用文档，文档回链真实 Issue URL。暂未发布的本地文档仍是草稿，不当作已存在的工单。`.github/ISSUE_TEMPLATE/` 按类别提供表单，默认携带对应标签。

`data-collection/` 为谛听的收集交接目录。实际事件继续由 Hermes 文件工具写入 `olympus-hermes-data/`；采集工具校验后建立不可覆盖的来源索引，保留原始身份和摘要。不得将 Hermes 记录改名为谛听自产事件。目录存在或索引生成不代表谛听服务已经读取。

## 边界

作为 Olympus 定制组件实现，不直接改写共工同步框架。现有 Ariadne 没有 GitHub 来源适配，当前不将此组件虚报为其已登记来源或已启用调度。已通过本机 GitHub CLI 验证写入权限，8 个类别标签及 Issue #1 已创建；模板仍须发布并核对默认分支。

## 验收标准

- [x] 八类 Issue 表单和标签定义一致，远程标签已创建后表单才可完整使用。
- [x] 需求文档以 `.md` 管理，并与实际 Issue 互相引用。
- [x] 采集目录含真实事件来源索引，保留来源身份和摘要。
- [x] 本地适配器测试及 Hermes 文件/Git 检查通过。
- [x] 远程配置发布及首张 Issue 创建有实际回执。

勾选须依据实际结果；未完成项保持未完成，验证记录另见组件说明及真实事件。

## 本地验证

2026-11-02：适配器 9 项测试通过，含表单/标签一致性、路径边界、无网络预览、重复 Issue 检查、现有标签保留及失败采集阻断。定制注册表校验通过。远程标签、模板发布及 Issue 回链仍待 GitHub 连接，不能勾选相应远程验收项。

## 远程接入进展

2026-11-02：使用已有 GitHub CLI 登录，确认仓库写权限。8 个 type 标签已存在，实际工单为 [Issue #1](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1)。远程 main 已更换为 Godot 独立快照；通过隔离工作树保留两边历史和 Godot 原文件合并，未使用强推。

## 发布验收

2026-11-02：GitHub 回读确认默认分支提交 `66e21559cfc9d2d079081cae6a1912fb300fba90` 包含全部模板，8 个类别标签已存在，Issue #1 已关联 `type:development`。以上本次交付条件均已完成。早期“待连接/待发布”记录是历史阶段状态。谛听服务消费与 Agent 启用仍未确认，不属于本次发布回执。

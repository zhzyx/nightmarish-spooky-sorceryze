# 文档来源汇聚索引

本模块登记仓库内现有资料的职责与位置。长期规则提炼到对应模块；需求、设计和验收正文保留原位置，避免批量复制造成多个权威版本。

## 长期规范原文

| 主题 | 权威来源 | 已归入模块 |
| --- | --- | --- |
| 工作区执行、权限、交付与清理 | [原工作区约束](../workflow/repository/README.md) | `workflow/repository` |
| 项目贡献、开发、验证与 PR | [项目贡献指南](../../CONTRIBUTING.md) | `build`、`testing`、`code-style` |
| 仓库工单协作与状态规则 | [仓库协作入口](../../.github/CONTRIBUTING.md) | `workflow` |
| C++ 项目级编码规范 | [项目 C++ 编码规范](../../CPP_CODING_STANDARD.md) | `code-style/cpp` |
| AI 编辑器语义操作协议 | [AI 编辑器操作接入](../../tools/EDITOR_CONTROL.md) | `editor-control/ui-commands` |
| Engine Next 构建边界 | [Engine Next 构建契约](../../design-docs/engine-next-build-contract-20261112.md) | `build/engine-next` |
| Gameplay 核心、会话、复制、相关性与预测 | [Gameplay Framework 设计](../../design-docs/gameplay-framework-20261106.md) | `gameplay` |
| 引擎适配与迁移边界 | [引擎适配与迁移规范](../../framework/specs/engine-adapter.md) | `engine-core` |
| 仅咨询命令输入 | [仅咨询会话的受信文字输入](../../design-docs/consultation-command-input-20261109.md) | `editor-control/consultation-input` |

## 需求、设计与历史证据

- `design-docs/`：需求正文、方案、验收条件和历史执行记录；文档管理规则见其中的 `README.md`。
- `data-collection/`、`gonggong-diting-data/`：实际事件、来源与验证证据，权威状态仍需回读对应 Issue／PR／CI。
- `archive/`：历史发布及批准记录，只作证据，不自动启用或继续已停止草稿。
- 交接记录、构建日志和候选回执作为证据使用，不直接上升为长期规范。

## 不批量汇聚的内容

第三方许可证、上游平台说明、引擎模块说明、依赖环境内的 Markdown 和自动生成文档继续留在原目录。它们不是本项目统一工作规范，移动后还可能破坏许可、链接或上游同步。

## 后续归集原则

1. 可复用且长期有效的规则进入最具体模块，并在这里登记权威来源。
2. 单次需求、候选比较、命令日志和验收记录只建立索引，不复制为永久规则。
3. 同一规则已有权威原文时保留单一正文；模块页只做路由或执行摘要。
4. 原始文档移动前必须检查反向链接和独立工作副本可用性，不做机械批量移动。
5. 新增、拆分、合并和废弃模块时，遵循 [文档与路由迭代规则](../workflow/documentation/README.md)，过碎或重叠的模块必须合并。

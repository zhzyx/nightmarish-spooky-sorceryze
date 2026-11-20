# 授权、审查与交付规则语义修复

Issue：[1686](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1686)；稳定 ID：`semantic-policy-20261120`；授权：`codex:user-request:semantic-policy-20261120`；责任者：Sail-Li。

用户要求完整审查相关语义并保持精简。#1683 已修复 CI 选择与审查复用实现；本单修复仍会诱发额外步骤的规则表述。基线 `08d372816481013ac4d010240ffc2ee8dc2334c8`。一个不可分割的规则一致性修复，不拆子单。

## 范围与规则归属

| 当前入口 | 审查内容与归属 |
| --- | --- |
| `AGENTS.md`、`Markdown/workflow/README.md`、`Markdown/workflow/documentation/README.md` | 按任务读取；具体规则不扩大权限；只在现有正文修改 |
| `Markdown/workflow/repository/README.md` | 工作区权限、有效框架与数据约束；其余流程只导航 |
| `customizations/platforms/process-management/repository/execution-policy.md` | 术语、连续执行、停止条件、验证复用、并发、等待与清理 |
| `customizations/components/issue-workorders/README.md`、`customizations/platforms/development/git/git-workflow.md`、`.github/CONTRIBUTING.md` | 工单、正式门禁与历史示例边界 |
| `customizations/components/issue-workorders/yanluo.md` | 交付审查/CI、本人 PR 与可选宿主授权、验收职责 |
| `customizations/platforms/work-management/github/issue-lifecycle.md` | 整体验收、子项、尾项结转与远端状态 |
| `customizations/components/issue-workorders/kuafu-routing.md` | 真阻塞当次接单，正常等待保持原运行 |
| `customizations/components/codex-dispatch/README.md`、`HOST_PROTOCOL.md` 及 `customizations/components/repository-dispatch/README.md` | 宿主选路、权限、启动/终态/交接，不当作每任务部署前置条件 |
| `Markdown/testing/README.md`、`ci-modules.md`、`customizations/module-boundaries.md` | 模块 CI 唯一来源、嵌入资源与构建输入 |
| `framework/specs/delivery.md`、有效框架及阎罗定义/批准 | 只读核对上位约束，不修改、不重新准入 |

纠正重点：共工操作授权与 GitHub ACL、普通校验与新定义准入、独立审查与 GitHub approval、Git 签发与宿主私有 grant、实际阻塞与正常等待、交付与整单完成。历史参数标为示例。不改程序、冻结框架、已批准定义、权限或 CI 规则；不接管 #1679 / PR #1682；不增加常驻服务。本次静态审查不等于跨模型实测。

## 验收与验证

1. 完整审阅上述规则链，原有效约束在保留正文或导航中可达，记录纠正项与未改原因。
2. 被改规范正文总字符数下降；设计与回执另计，不新建平行规约。
3. 独立只读工作者解释至少 16 个易误读场景，保留输入、答案与实际终态，不声称覆盖所有模型。
4. 检查相对链接、锚点、围栏、空白及入口可达；正式门禁、精确候选 CI、main 回读及整体验收后关单。

公开证据：`data-collection/semantic-policy-1686-validation.json`。私有回执收尾移出临时工作树；保留其他任务资源。范围内语义缺陷直接修复；真实执行阻塞按夸父入口处理。

已召回 `github-issue-delivery/reconcile-workflow-incidents` 修订 2：若本单 CI 失败触发事故，按实际运行/作业核对恢复；不以别单或其他步骤的成功替代。

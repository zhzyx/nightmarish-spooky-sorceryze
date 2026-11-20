# 工作流模块

本模块承载项目协作、交付流程及文档路由维护。少量规则直接保留在本文件，只有形成独立任务边界时才拆分子模块。

## 工单与分支流程

- 验收、交付与关闭按[Issue 生命周期](../../customizations/components/issue-workorders/issue-lifecycle.md)核对；关闭工单与合入 `main` 是两个动作。
- 本任务分支及 worktree 按[临时资源清理](../../customizations/platforms/process-management/repository/execution-policy.md#任务临时资源清理)在交付与工作者终态核实后处理，不删除他人资源。

## 子模块路由

| 任务类型 | 子模块入口 |
| --- | --- |
| 仓库执行、权限、框架、交付、阻塞与临时资源清理 | `repository/README.md` |
| 新增规范、模块拆分与合并、文档路由迭代、Git 提交并推送后的需求沉淀（不含 Bug 修复） | `documentation/README.md` |

工作流主题优先并入本文件或现有子模块；确需新增、拆分或合并时，遵循文档与路由维护规则。

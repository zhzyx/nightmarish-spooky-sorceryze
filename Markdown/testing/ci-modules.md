# 模块化 CI 与状态检查

## 普通变更的选择规则

`tools/ci/modules.json` 是唯一模块注册表，登记模块名称、路径、运行器、构建／测试命令、公共检查和状态检查。`tools/ci/select_modules.py` 对 PR 的 base/head、普通 push 的 before/after 执行真实 Git diff，并按**最长路径前缀**确定唯一归属；因此 `modules/gameplay/` 属于 Gameplay，而 `modules/` 的其他内容属于 Engine Core。

- 单模块变更只选择该模块；多模块变更分别选择各模块，不升级为全量。
- 新路径没有归属、同一前缀重复登记、未知依赖、通用模块没有真实测试命令时，选择器失败关闭。
- 文档和仓库元数据只运行公共静态检查；不以未登记或共享文件为理由启动全仓测试。
- 选择结果和逐路径归属作为 `module-selection-<run>-<attempt>` artifact 保存，汇总检查只接受所选任务的真实 `success`。
- 本地与 CI 使用同一注册表和选择器；pre-commit／prek 的 `ci-module-selection` 钩子运行相同契约测试。

本地复现：

```bash
python tools/ci/select_modules.py --base <base-sha> --head <head-sha>
python tools/ci/select_modules.py --file tools/ainative/executor.py
python tools/ci/select_modules.py --full --head HEAD
python -m unittest discover -s tools/ci -p "test_*.py" -v
```

## 完整回归

手动运行 `Modular CI`，并显式设置 `full_regression=true`，才会选择全部模块和公共静态检查。各模块工作流仍保留自己的 `workflow_dispatch`，用于只验证一个模块；这些入口不会冒充全仓完整回归。

## 状态检查

分支保护的公共必需检查应为：

| 必需检查 | 来源 |
| --- | --- |
| `CI / Select changed modules` | `Modular CI / select` |
| `CI / Modular tests` | `Modular CI / summary` |
| `📊 Static checks` | `GHA / static-checks` |
| `issue-association` | `GongGong Issue association` |

下列模块检查在被选择时必须真实成功；未选择时允许不运行，不将 `skipped` 记为通过。公共汇总检查会拒绝所选任务的 `skipped`、`failure` 或 `cancelled`。

| 模块 | 模块状态检查 |
| --- | --- |
| CI | `Module / ci` |
| Engine Core | `Module / engine-core` |
| 编辑器 | `Module / editor`；`Editor (target=editor)` |
| 马良 | `Module / maliang`；`Original Windows CLI and real Blender geometry`；马良 Windows package/run |
| Engine Next | 三平台 `No Godot source or link dependencies (...)`；三平台 `Visual runtime build and FrameGraph (...)` |
| Gameplay | 三平台 `Gameplay standalone tests (...)` |
| Web | 两种线程配置的 Web Template 构建与 JavaScript 语法检查 |
| 天璇 | `Module and web tests`；`Docker images` |
| 合契 | 两平台 `Integration planner (...)` |
| 构建路由 | 两平台 `Build scope routing (...)`；两平台 `Native cache boundaries (...)` |
| 共工接入 | `Module / gonggong` |
| 文档、仓库元数据 | 无独立业务测试；公共静态检查必需 |

旧工作流的 PR／push 路径触发已移除，不应再把 `Engine Next build contract`、`Maliang offline Windows editor`、`Tianxuan tests` 等旧工作流的全部内部检查逐项设为永久必需，否则未变更模块会产生永久等待。服务器实际保护状态以 GitHub 分支保护回读为准，文档本身不声称启用了权限控制。

## PR 审核

审查人需核对选择 artifact 中的 base、head、逐路径归属和模块集合，确认其与 PR 文件列表一致；再检查所有被选择模块的结果。不得接受“未运行所以成功”的汇总，也不得通过删减模块测试、放宽断言或修改注册表逃避应有检查。

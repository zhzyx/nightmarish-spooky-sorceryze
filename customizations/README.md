# Olympus 定制层

Olympus 是共工框架的定制发行工作区。共工提供稳定共同能力；专属任务、流程、工具与集成属于 Olympus。定制能力可以用于自己的任务；是否进入共工，由共工侧确认和治理决定，不自动升级为共同规则。

## 所有权与目录

| 层 | 位置 | 变更来源 |
| --- | --- | --- |
| 共同框架 | `Olympus/` 中的上游内容 | 共工正式来源及已登记模块，按名称映射同步和核验 |
| 分发适配 | `Olympus/sync/`、名称映射、生成的指纹与接入钩子 | 只处理分发和一致性，不放业务定制 |
| 定制能力 | `customizations/components/<id>/` | Olympus 专属任务；在 registry.json 登记边界与依赖 |
| 定制需求与验证 | `customizations/tasks/`、`customizations/evidence/`（按需创建） | 实际任务、测试和效果证据 |
| 待共工确认的候选 | `customizations/feedback/` | 本地提案，不能作为共工批准或已合入证明 |
| 运行及需求数据 | `olympus-hermes-data/` | 需求产出，独立保存并纳入 Git |

兼容现状：`Olympus/extensions/hermes-files/` 是已经独立豁免的定制模块。现以 registry.json 显式登记为 `legacy_preserved`，保留调用路径和完整内容；它不是共工共同框架。其他新定制代码一律进入 components，不扩散旧路径。未来迁移须保留兼容调用、验证和数据恢复方案。Ariadne 来自共工已登记能力，仍归共同框架。

## 定制任务与同步

每项任务先确认属于共同框架、分发适配还是定制需求。应用独有的流程、引擎接入、领域规则和工具默认在定制层实现，通过公开接口调用框架；依赖记录适用框架版本、接口、验证和回退。修改定制模块不自动允许修改纲领、源框架或其权限边界。

同步仅替换通过全量核验的框架目录；保持 customizations、赫尔墨斯数据和已登记兼容模块不变。工作区其他项目内容也不得被框架同步清理。同步前后核对定制模块/数据的内容摘要；随后运行实际受影响的定制兼容性验证。框架一致不等于定制兼容，二者分开记录；不兼容时保留旧数据及可恢复版本，不静默改写定制需求。

注册表条目必须说明 id、version、path、ownership、framework_dependency、validation、rollback。定制实现默认不可调用未获授权的生产功能；独立定制验证无需凭空依赖上游在线，涉及框架执行的任务仍遵守框架准入。

## 反哺共工

1. 定制开发期间记录实际需求、适用范围、解决方式、效果、反例和限制；无测试或无观测不能写成成功。
2. `tools/customization_feedback.py propose` 生成不可覆盖的候选，绑定组件版本与逐文件摘要、框架基线、收益、兼容风险、证据引用、通用化范围及回退。候选状态始终为 `pending_gonggong_confirmation`。
3. `export` 导出绑定版本的源码与证据，放入共工工作区的独立反馈收件目录供其查阅。仅为交付待确认材料，不修改任何共工框架、清单、批准或版本指针。不夹带整个需求数据库；只包含明确引用的证据文件。
4. 共工可要求补证、拒绝、延期或确认进入自身变更流程。确认须绑定候选 ID/指纹、实际决定人和证据；确认考虑不等于已合入，测试通过也不等于获准。
5. 仅当共工发布了有效的正式变更，Olympus 才按框架同步接收。记录采纳版本、对照接口与验证，再迁移或停用重复定制；保留历史提案、决定与数据，不删除待迁移实现。

工具刻意没有自动批准、自动改写共工或自动启用的操作。候选文件保留原始状态；后续决定应另存记录并引用候选，不改写旧提案。提交后组件发生变化，旧候选仍绑定旧快照；新版本重新提案，不能静默用新文件替代。

```powershell
python tools/customization_feedback.py validate --repo .
python tools/customization_feedback.py propose --repo . --component hermes-file-data --id hermes-file-data-v1 --input proposal-details.json
python tools/customization_feedback.py export --repo . --id hermes-file-data-v1 --out PATH/TO/NEW-CANDIDATE.zip
```

proposal-details.json 必填 problem、local_scope、generalization、benefit、risks、rollback、evidence（仓库相对文件路径数组，可为空但不得宣称已有证据）。完整分层约定见根 AGENTS.md；反馈仅使用共工收件路径，不替换共工正式来源。

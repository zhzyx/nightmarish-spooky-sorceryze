# 天璇产品 Agent 候选 · 审查请求

本目录新增三个产品级 Agent 候选，均未准入、未启用。

## 候选

| ID | 名称 | 定义 | Skill |
| --- | --- | --- | --- |
| `wenqu` | 文曲 | `wenqu/AGENT.md` + `wenqu/agent.json` | `wenqu/skills/doc-authoring/SKILL.md` |
| `duobao` | 多宝 | `duobao/AGENT.md` + `duobao/agent.json` | `duobao/skills/repo-review/SKILL.md` |
| `sinan-workorders` | 司南·工单 | `sinan-workorders/AGENT.md` + `sinan-workorders/agent.json` | `sinan-workorders/skills/work-order-management/SKILL.md` |

## 审查入口

按 `framework/skills/gonggong-check/SKILL.md`：

1. 读取 `framework/AGENTS.md`、`framework/FOUNDATION.md`、`framework/foundation.lock.json`、`framework/upstream/yuanheng/core.md` 与 `framework/upstream/yuanheng/agents/yuanheng.md`。
2. 按 `framework/specs/governance-review.md` 核对边界、元衡原则与指令精简度。
3. 用 `framework/templates/review-pass.json` 记录 review pass，绑定精确候选摘要与范围。
4. 取得真实授权后才可启用；自评不是批准。

## 本次未覆盖

- 未修改 `framework/AGENTS.md`、`framework/framework-manifest.json` 或核心 Agent 列表。
- 未产生生产工具权限、模型凭据或远端写入。
- `reporting.json` 为候选模板，`runtime_connected: false`；实际绑定由宿主在启用时完成。

## 证据

- 定义文件与 JSON 在本目录。
- 领域核心测试：`customizations/components/tianxuan/server/test_tianxuan_core.py`。
- 审查结果待补充；在获得 review pass 之前，这些 Agent 只能作为候选存在。

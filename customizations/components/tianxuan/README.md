# 天璇（Tianxuan）

共工框架下的 AI-native 在线管理模块：**文曲**（文档）、**司南**（工单扩展）、**多宝**（代码仓库）。

- 需求 Issue：[#1085](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1085)
- 设计基线：[design-docs/tianxuan-platform-20261114.md](../../../design-docs/tianxuan-platform-20261114.md)
- 素材清单：[design-docs/tianxuan-assets-20261114.md](../../../design-docs/tianxuan-assets-20261114.md)
- 状态：`candidate_pending_implementation_and_admission`，`runtime_connected: false`

## 结构

| 路径 | 职责 |
| --- | --- |
| `server/` | 领域核心与后续 FastAPI/PostgreSQL 适配器 |
| `wenqu/` | 文曲：Markdown 文档、版本、归类、检索 |
| `sinan-workorders/` | 司南：工单模型、状态机、事件推进（复用现有司南） |
| `duobao/` | 多宝：仓库、分支、PR、评审（复用开源 Git） |

## 当前切片

`server/tianxuan_core.py` 是标准库 + SQLite 的可独立验证领域核心，覆盖：

- 注册/登录（租户、用户、默认空间）
- 文曲 Markdown 文档创建/更新、版本、乐观并发、自动归类、AI 机器视图
- 偃师需求文档（frontmatter + 目标/范围/验收）
- 司南工单创建、父子关系、状态机、需求计划拆单、进度同步
- 事件流（谛听语义）与 AI 工具入口

FastAPI + PostgreSQL 适配器与 Next.js 前端在后续切片接入，不改变本层语义。

```sh
python -m unittest discover -s customizations/components/tianxuan/server -p "test_*.py" -v
```

## 边界

- 不替代司南的协调与派发责任；工单派发仍走现有司南能力。
- 不重写 Git；多宝复用开源 Git 服务并做 AI 编排与并发合入优化。
- 新增 Agent/Skill（文曲、多宝、司南工单扩展）必须先经 `skills/gonggong-check` 审查并取得精确候选准入。
- 文档以 Markdown 为唯一权威，AI 阅读优先；人类视图是第二等公民。
- 验收沿用现有 Agent（司南协调、偃师设计、夸父质量、谛听证据）。

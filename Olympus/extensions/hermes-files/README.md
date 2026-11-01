# 赫尔墨斯文件数据源（奥林匹斯独立豁免）

版本 1.0.0。本模块依据用户明确授权独立运作，豁免共工同步覆盖。共工仍是其他框架内容的唯一上游。豁免仅限 `extensions/hermes-files/` 的文件记录工具、格式与说明，以及目标 Git 仓库内独立的 `olympus-hermes-data/` 数据目录；不扩展为对其他治理、Agent、skill 的修改权。

## 接入时机

先将本模块合入确定的目标 Git 仓库，再执行初始化。本次交付只有规则、格式和工具，没有创建生产数据目录、Git 仓库或虚构生产记录。每个目标仓库单独初始化；数据目录位于仓库根，不能放入会被共工重建的框架包。同步工具必须逐字节携带现有豁免模块，遇到共工占用同名路径时阻断并报告，不能覆盖。本模块和文件数据的使用不依赖数据库、共工在线或框架源位置。

```powershell
python PATH/TO/extensions/hermes-files/hermes_files.py init --repo PATH/TO/TARGET-REPO
python PATH/TO/extensions/hermes-files/hermes_files.py record --repo PATH/TO/TARGET-REPO --input PATH/TO/ACTUAL-EVENT.json
python PATH/TO/extensions/hermes-files/hermes_files.py validate --repo PATH/TO/TARGET-REPO
python PATH/TO/extensions/hermes-files/hermes_files.py analyze --repo PATH/TO/TARGET-REPO --tenant TENANT
python PATH/TO/extensions/hermes-files/hermes_files.py git-check --repo PATH/TO/TARGET-REPO
python PATH/TO/extensions/hermes-files/hermes_files.py git-check --repo PATH/TO/TARGET-REPO --require-committed
```

`--repo` 必须是现存 Git 工作树的根。`init` 只生成数据目录内容，不执行 git init/add/commit/push。没有目标仓库时拒绝创建。首次初始化后，不重复覆盖已有数据。

## 目录及记录

```text
olympus-hermes-data/
  dataset.json
  README.md
  .gitattributes
  events/<tenant_id>/<request_id>/<event_id>.json
```

UTF-8 JSON，每个事件独占一个不可覆盖的文件，减少 Git 合并冲突。dataset.json 保存独立 dataset_id、格式版本和来源框架；事件保存租户、需求、Agent 原始快照、时间、来源、原始内容和 SHA256。数据 ID 不复用框架包版本。Git diff 可审查原文，禁止将目录加入 .gitignore。产生记录即属于该需求交付物；提交需求代码、文档或其他产出时必须一并合入对应数据文件和初次数据元信息。

事件字段参见 `event.schema.json`；填写 `event.template.json` 中的真实值后，删除 template_only 标记，再提交给 record。未填写模板会被拒绝，不能充当生产记录。request、step、message、direction_error、correction、quality_issue、rework、handoff、coverage、request_end、analysis 等用 kind 区分。payload 允许实际来源字段，不能把没有测得的时间、token、成本填成 0；缺失值用 null 并给出 reason。工具只统计事实事件数，不将事件条数解释为 token 用量或生产质量。需要业务指标时，读取实际 payload 并标注覆盖范围。

事件创建后不得覆盖；纠错用新的 event_id 和 supersedes 指向同租户、同需求的旧事件。保留旧记录、证据引用、原始 Agent 身份、版本和定义指纹，不把赫尔墨斯事件反写成谛听事件。证据引用必须存在且属于同租户。重复事件 ID、摘要不符、悬空引用、循环、更正分叉和非法路径都拒绝；并发更正冲突必须在 Git 合并时解决，不能静默择一。相同来源的记录可幂等重试；相同身份不同内容视为冲突。

## Git 合入与分析

`git-check` 检查数据有效、未被忽略并已纳入索引；`--require-committed` 进一步验证工作区各数据文件与 HEAD 完全一致。还会拒绝删除已提交的数据文件。Git 提交和远程合并继续由目标仓库既有流程执行，本工具不冒充已提交或已合并。尚未提交的合法记录可本地分析，但返回 Git 状态及证据快照，不能称为已交付数据。

赫尔墨斯和共工使用同一个 `analyze` 命令读取文件，结果保留完整记录、有效版本、证据链及 dataset_id/快照摘要。输出默认到 stdout，分析报告如需持久化应作为对应需求的新分析产出另存；不得回写、改名或重复导入为共工自产事件。读取不需要 SQLite。租户参数只是过滤，目标仓库权限仍由宿主执行；只写入该仓库授权留存的数据，不写密钥或连接凭证。

文件模式可替代本地数据库落库，状态为 `recorded_file`；经 Git 检查分别确认 `tracked`、`committed`。这些状态不冒充原数据库 reporter 的 `sent` 回执，也不自动证明已被所有运行事件接入。宿主应在需求开始、执行步骤、消息、纠偏、质量/返工、交接、结束时调用记录工具。生产验收要核对实际事件覆盖；无记录或未知覆盖须如实展示。

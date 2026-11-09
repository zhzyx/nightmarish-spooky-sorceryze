# 从实际任务学习方法

工单开始时，执行者从当前租户的能力域中选择与任务消费者、宿主和依赖关系相符的域。对召回的方法逐条核对适用条件和反例，将适用的试验写入当前工单计划。执行者沿当前授权开展验证。元衡准入、生产身份、独立审查和验收沿原有入口判断。

纠偏、失败、交接复盘或实际复用结果出现时，执行者提取一条下次可以验证的具体动作，记录原工单、原始现象、为什么采取该动作、适用条件、已知反例和能推翻结论的试验。复盘得不出可检验的动作时保存原始回执即可。相同问题复用同域已有 lesson，依赖条件或结果变化时追加修订。跨租户或跨域推广须在目标授权内重新提议、试验。

## Git 文件宿主操作

独立安装的框架可直接运行此入口的 `--help`。当 Git 文件宿主与框架分开安装时，在子命令前传入 `--host-root <可信宿主安装根>` 加载宿主提供的适配器，`--repo` 只选择当前任务的数据仓库。

从仓库根运行下列入口，其他目录通过全局参数 `--repo` 指向项目根。`origin` 和所有证据文件的路径均以该根为基准。宿主绑定操作者有权读写的租户、工作区和来源，工具使用该库已安装的谛听 Git 文件适配器。其他存储宿主可按同一状态机从谛听记录投影。

```powershell
py -X utf8 framework/tools/method_learning.py --tenant gonggong-workspace scopes
py -X utf8 framework/tools/method_learning.py --tenant gonggong-workspace recall editor-dependency-handoff
py -X utf8 framework/tools/method_learning.py --tenant gonggong-workspace status godot-build-placement
py -X utf8 framework/tools/method_learning.py --tenant gonggong-workspace append input.json
```

`recall` 返回可复用的方法、反例、证据和当前修订摘要。证据文件字节发生变化或文件缺失时对应经验进入 unavailable。`status` 是复盘、试验、修订时使用的完整状态，含候选与停用项。持久记录位于项目根 `gonggong-diting-data/events/<tenant>/learning-<scope>/`，按发生事件访问，无后台进程。单条事件的 `recorded_file` 回执仅代表本地落库；按任务宿主完成发布。

### 复盘输入

逐次生成一个 UTF-8 JSON 对象。仓库已有首条实录，可在上述事件目录中查看各字段实值。

| 字段 | 填写方式 |
| --- | --- |
| origin | 本租户这次复盘或复用任务的实际谛听来源事件路径，保留其工单来源和 Agent 快照 |
| occurred_at | 本次操作发生时间，ISO 8601 含时区；重试使用原值 |
| scope, lesson | 小写英文、数字、下划线或连字符，首字符为字母或数字。scope 使用稳定的任务能力域，lesson 命名同一条方法 |
| revision, previous | 初次用 1 和 null，后续用当前 revision 加 1 和 status 中的 head。冲突后回读再决定 |
| evidence | 非空数组，每项含项目相对 path 和文件原始字节 sha256。使用可复核的、可持久读取的原始工单或验证回执 |
| action, details | 按下表填写，details 每个值均为非空文本 |

| action | details | 生效条件 |
| --- | --- | --- |
| propose | method、when、counterexample、trial_plan | 复盘责任者提出可复用动作并设计试验，进入候选 |
| verify | test、expected、observed | 责任者按候选中事先记录的计划运行试验；附实际回执，用相同格式分别填写预期与观测。相等时启用；不相等时用 counterexample 记录失败 |
| applied | task、observed | 下一张同域工单真实使用后的结果和证据，关联该任务的 origin |
| counterexample | observed | 试验失败或复用遇到反例，立即停止召回 |
| withdraw | reason | 结论过期或撤回，立即停止召回 |
| revise | 与 propose 相同 | 对候选、已验证或停用方法提出新版本；保留全部旧事件，新版重新试验后再启用 |

证据核验包含文件摘要；执行者负责解释回执是否真实回答了预先提出的问题。宿主只发布当前授权范围内可共享的证据。数据格式兼容谛听 analysis 事件，前驱与实际工作事件均在 evidence_refs 中，竞争写入同一修订时一个文件只接收一种内容。

### 两项历史复盘

**编辑器依赖交接。** #676 的审查试验包含分支、文件字节和链接在交接前变化的情形。#677 的依赖调度区分运输完成、实际验收与下游放行，验证了正常、冷启动和候选过期场景。首次召回时核对本任务的上游生产者、接收者、实际候选及验收回执；候选变化则保留旧回执、停止放行，重新取证。持续使用的证据存于 `editor-dependency-handoff`。

**构建位置。** #687 的 `godot-build-placement` 候选从实际消费者和构建依赖出发。天枢界面脚本曾生成原生头文件；迁到版本化资源包需要同一二进制上的替换、回退与 ABI 拒绝回执。马良的内嵌 Python 是按后缀排除原生输入的反例。新工作树构建、共享缓存或运行时资源试验有了可回读证据后，用 verify 或 counterexample 记录其实际范围。单一平台的试验只支持该平台及受测消费者。


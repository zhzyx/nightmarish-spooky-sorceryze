# 阎罗宿主接入与职责交接

所有路径以仓库根为基准。此目录是隔离待审候选，尚未注册到当前框架，不能生产执行。`closure.py` 是可测试的编排接口，Host 实现与宿主真实授权仍须接通；没有后台服务或全局接管。

## 权责

| 职责 | 交接后责任方 |
| --- | --- |
| 开发、业务测试、验收结论 | 原业务主责与验收者 |
| 多方贡献收集、差异比较、冲突解决、形成候选 | 合契 |
| 提交前门禁、精确候选核查、提交/合入 main、发布回读 | 阎罗 |
| 目标 Issue 的完成标签、关闭及回读 | 阎罗 |
| 优先级、派发、依赖、父项重新判断及跨工单视图 | 司南 |
| 定义准入、治理授权、必要独立审查 | 元衡体系的有权主体及独立审查者 |

迁移生效前由原责任方保持在途操作；生效事件记录 event_id、旧责任人、新责任人、Issue、候选、文件范围、已完成动作、未知回执和恢复点。一个仓库/main 同时仅一位真实发布执行者。不得抢占其他工作者的工作树或中断其正在执行的发布。待审定义不转移实际权限。

## 自动执行契约

宿主在 `checks.completed`、候选交接、明确恢复或用户请求事件调用 `finalize(Candidate, Host)`；没有事件不调用，不设扫描或定时重试。提交到任务分支只是暂存候选，交付目标为 main。

Host 由受信宿主提供，不能让待审 PR 自己实现、替换或选择执行命令：

1. `authorize` 核对真实执行者、阎罗精确准入、任务委托、写入范围、远端账号及谛听绑定；未注册候选必须拒绝。用户对本职责的授权持续有效，但不将定义授权扩展到无关任务。文件里的 approved 或布尔值不能认证身份。
2. `acquire/release` 在实际宿主跨进程串行化同仓库/main；不能只用模型约定或按事件分锁。释放只针对自己取得的租约。锁丢失时禁止写入。
3. `read` 通过真实连接器回读 Issue 状态/修订、范围、所有贡献、PR/head/base 和精确候选，返回 candidate、published、closed、status、main 及修订标记。published 只来自持久发布回执及远端核对，绝非本地成功标记。响应未知先对账。
4. `verify` 逐项取得 REQUIRED 的真实证据。固定验收清单及完整贡献快照，不以一个子项或一个 PR 完成代表整个 Issue；缺失、失败、跳过、pending 均不能返回 True。绑定 repository、commit/tree、依赖摘要与 scope_digest；候选或基准变化重验受影响部分。独立审查不能由阎罗自批。
5. 提交前复用 `issue_gate.py --repo ... --issue ... --request-id ...` 正式门禁及 `framework/tools/check_delivery.py`、业务验收和 required CI。只暂存自己的明确清单，在隔离任务分支提交，再执行 `framework/extensions/diting-files/diting_files.py git-check --repo ... --require-committed`。不要把仅 intake-only、格式检查或候选模式当作正式通过。自动 main 发布前对任务分支精确 SHA 重新核对全部证据。
6. `publish` 使用受保护分支允许的 PR 合并/合并队列或已授权快进方式。原子校验候选 SHA 与预期父提交；GitHub PR 接口若不能同时锁定 base，使用严格 up-to-date required checks/合并队列保证最新整合树已验证，否则拒绝。禁止 admin 绕过、force push；CI 失败不放宽检查。PR 正文保留 GongGong-Issue/GongGong-Request，验收完成前不用自动关闭关键字。
7. `read_main` 回读远端实际 commit/tree，核验精确候选进入 main。发生 squash 时需验证交付树对应关系，不能仅判断 SHA 祖先。未知发布回执只等待下一个真实事件对账，不能重复盲目发布。
8. `record` 以稳定 event_id + candidate + phase 幂等追加共享谛听事件及 data-collection 回执，保存真实执行者、Issue 修订、检查与发布引用；相同键不同内容拒绝。公开证据需按已有 Git 交付规则另行提交，提交后追加回执不能伪称已在前一提交中；私有排队不等于 delivered/consumed。用量未知为 null+reason。
9. `mark_done/close` 在写入前再核对 Issue 修订、范围和远端交付，保留其他标签，仅将唯一 status 改为 done，然后以 completed 关闭同一 Issue。已完成相同步骤应幂等；出现新贡献/验收范围变动则停止关闭。关闭失败只重试状态对账，不重新提交。`read` 最终回读后才报告完成。
10. `reconcile` 将 release.completed 和 issue.closed 交司南刷新父项/依赖与需求视图，父项不得自动关闭。同步失败保留待对账。该接口不发送其他无关消息。

## 准入与恢复

独立审查当前候选全部文件、精确指纹及职责迁移，取得交付通行证，注册框架 Agent、更新受影响注册/上报/候选清单及完整性锁并重验；不得修改旧批准记录或冻结原件。随后接通 Host 各方法，完成真实代表任务及失败恢复回执，才可声明自动提交/关闭已启用。

回退只停止后续调用并将尚未执行部分明确交还原责任人；保留已经提交内容、Issue 历史和谛听事件，不撤销真实完成事实。本候选不得阻断其他已准入 Agent 的无关操作。

`read` 的 published/closed 必须为严格布尔；未知值立即暂停。verification 必须是受信宿主认证过的持久回执，含 candidate（含 scope_digest）、receipt_id、全部 REQUIRED checks。首次发布前与已发布恢复路径均校验它；远端存在提交不能替代核查回执。

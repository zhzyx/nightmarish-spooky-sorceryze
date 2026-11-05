# 阎罗当前宿主入口

路径基准为仓库根。用户已批准 `customizations/components/yanluo` 的 v0.1.2 精确候选；原候选文件与待批记录保留为历史事实，实际批准见 `data-collection/yanluo-user-approval.json`。本接入在原位置加载该定义，不复制/迁移冻结框架、不改写旧批准。Git 专用执行留在 issue-workorders 接入层。

当前责任：合契交出已整合的候选、完整贡献快照和范围；阎罗负责最终核查、main 发布、发布后完成度复核、目标工单完成写入与回读；司南继续派发、依赖、父项验收和跨工单协调。已经在执行中的发布须完成原操作者交接，不能抢占或操纵其他工作树。此入口只接管新交接事件；原冻结 Agent 定义中的通用协作职责不扩展为另一位 main 发布者。

`yanluo_host.py --repo REPO --grant PRIVATE_GRANT --apply` 是真实 GitHub CLI 接入，默认不带 `--apply` 只校验授权。它从调用者已经认证的 gh 通道回读账号、Issue 和远端，使用同一通道更新 main、状态和记录。宿主必须在自身可信进程中提供 GONGGONG_HOST_KEY（至少 32 字符），沿用当前运行时 HMAC-SHA256/canonical JSON 约定。密钥不进日志、源码、工单或模型上下文；接入没有签发授权的命令。grant 由有权宿主签发，至少包括：

- payload：candidate（closure.Candidate 全部字段）、绝对 repo_root、expires_at（Unix 秒）、authority_ref、account_login、target=main、mode=fast_forward、adapter_sha256、approval_sha256、candidate_manifest_sha256、host_registry_sha256、definition_digest、trusted_files（可信安装全部执行依赖及framework文件摘要）、checks、required_ci_names、acceptance_items。
- checks：REQUIRED 中每项的真实证据路径（相对仓库根）、sha256、status=passed、同一 candidate。检查记录必须来自实际执行，独立审查由独立评价者承担；签名不把未知变成通过。交付核验先执行既有 check_delivery.py，结果列入 delivery 证据。
- acceptance_items：完整原 Issue 验收清单，每项 id、module、acceptance、state(done/remaining/unknown)、evidence。done 必须有真实验证依据；remaining 说明尚未支持内容；unknown 说明缺失证据。原始清单范围由宿主核对，不能删掉难项以提高完成度。
- signature：对 payload canonical JSON 的 HMAC-SHA256；代码/定义/候选/范围/权限漂移均需复核相应证据与签发，不跨任务复用。

自动发布采用已授权的快进路径：先把精确候选推送到任务分支并取得精确 SHA 的 CI，宿主回查正式门禁和 committed-data，再向 main 请求 `force=false`。不会调用 admin 绕过或构造未测的新合并树。保护分支要求 PR/合并队列时由保护规则拒绝此路径，保留待处理，不自动降级保护。多个工作树共用 Git common-dir 内的 OS 文件锁；这不是分布式全局锁，其他宿主仍需按交接规则串行发布。

实际执行状态使用 Git 私有目录的持久 journal；它不是 Diting 已落库或已消费的证明。main/工单完成/进度复核状态同时记录到真实 Issue 时间线，供现有 GitHub 来源适配消费；消费未知时保持 null，不声称司南已经处理。任务的公开测试/来源与实际 Diting 文件事件仍按原门禁提交；运行结束新增的来源事件按实际采集回执追加，不改写本次源提交。

## 合入后的完成度与拆单

每次实际 main 合入后，阎罗对照完整验收清单复核，记录已完成项数/总项数、未完成项、未知项及远端提交。不用代码行数、PR 数量、主观工时或 token 估计进度。

有证据确认大部分验收项完成（已完成项超过全部项的一半），或只剩至多两个未支持模块且已有其他模块完成时，为剩余模块创建关联 Issue。此数目是当前宿主的可审查判断规则，不代表工作量百分比；若任务模块不可比，宿主应将结论保留 unknown 并取得业务判断。新单含父单、已合入提交、未完成验收与依据，使用确定性稳定需求 ID；查询全部开放和关闭工单后复用开放匹配项；命中已关闭单但仍有剩余范围时记录冲突并停止，先核对关闭原因或开放继承单。回执不明不盲目重建，多重匹配拒绝。

未知项存在时不把“多数通过”当全完成。部分交付可拆单推进，但原单保持开放并记录剩余工单；只有原单全部验收完成才写 done/completed。创建 follow-up 不自动批准其生产执行，由司南按实际需求事件和容量派发；不关闭上级工单，不新增定时扫描。

故障恢复：先读真实 main 和 Issue，再用同候选的持久 verification 回执恢复。已发布不重复发布；缺回执不关闭；主线推进或范围变化只挂起受影响动作。权限失败、CI 失败和未完成项均保留准确状态。

宿主子进程环境移除签名密钥，门禁从可信安装加载；候选框架必须逐文件匹配宿主签名的可信框架清单。框架升级需独立安装审查，不能让待审候选自带门禁或替换进度实现来复用旧授权。状态标签只添加 done、删除本次已核对的旧 status；本机 journal 保存中断过渡，不覆盖其他业务标签。

当前宿主注册表为 customizations/host-agents.json，绑定上述已批准定义与元衡治理。customizations/registry.json 中原候选条目随批准对象保留，不将它的历史 pending 字段误当成当前宿主注册状态；此注册不改变 framework 的通用 Agent 清单，也不伪造后台进程。CLI签名同时绑定宿主注册表摘要。

## 子项交付与尾项结转衔接

按 [Issue 生命周期](issue-lifecycle.md) 区分正常完成与结转关闭。现有自动适配器只实现完成关单及剩余单创建，未实现原生父子关系迁移和 not_planned 结转关闭；这部分由实际有权操作者按文档逐项核实后执行。迁移进行中保持原单开放，不把创建 follow-up 当作承接已完成，不修改已批准 Agent 定义或将文档契约声称为自动实现。

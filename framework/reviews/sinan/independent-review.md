# 獬豸·框架审查（临时职能）：司南调度

日期：2026-11-02。评价者：独立子任务 `/root/quality_skill_forward_test`，临时承担獬豸框架审查；不创建正式 Agent，不参与产品实现，无批准权。方法：只读候选与适用共享规则，work 内隔离测试。

## 最终候选结论

**本次候选代码／配置在两项并发问题修正后通过已覆盖范围的独立评价，无本次已知遗留阻断项。** 最终 scheduler.json 仍 enabled=false，实际启用、真实扫描上报落库及周期运行由主流程后续执行并留证。当前 dispatch.mjs 是只读派发计划器，不启动宿主实例；计划输出不是已启动自动调度的证据。独立评价不代替用户批准或授予生产工具权限。

适用授权按主任务转述的真实用户要求，限未来共工体系建设与维护任务及职责划分。它不扩展到历史请求、其他业务、不可见聊天或外部发布／支出。实际授权引用及原始请求仍须由最终配置提供，不由本评价者自行签发。

## 已复现的发现

1. **路径别名绕过写入互斥。** dispatch.mjs 的 scopes 只做 path.resolve 与词法包含关系检查。Windows junction 的 target 和 alias 指向同一真实目录，但两个工单分别声明这两路径会同时进入 dispatch。隔离夹具实际建立 junction，确认两个选中范围的 realpath 相等。应按真实路径校验互斥及范围；未存在的写入路径需解析最近真实父级，不能仅因为叶子未创建就忽略祖先别名。还须防止经别名越出来源范围。
2. **blocked 不代表宿主实例已结束。** active 仅包含 running／review。源 CLI 的 block 只改任务状态，不取消宿主 worker；blocked 且 execution=host_acknowledged、未有停止回执的实例被排除，容量和写入范围立即释放。隔离夹具给一个这样的实例和两个 open 工单，仍选中两个新工单。应在宿主确认取消、完成或安全交接前保守占用容量与范围；任务状态不能替代真实生命周期。

两项均已先通知主流程，现已修正：realTarget 解析最近存在的真实父目录后拼接尚未创建的尾部，互斥与允许写入范围均据此判断；blocked 与 running／review 一并保守占位，待宿主对账。未知写入范围改为占用全部本轮授权根，比原先只占来源根更保守，与最终职责文档一致。独立 junction／blocked 夹具重跑后两项风险均不再复现；新增正式回归也通过。

主流程还纠正了 integration/module.json 的显示名称乱码；最终只读确认 name 为“司南”。最终 Skill 已有指向 reporting.json 和实际宿主绑定的一条要求，无需再加重复句。

## 通过的覆盖及边界

实际脚本：`work/sinan-dispatch-independent-check.mjs`，夹具位于 `work/sinan-independent-fixtures/`。初审运行结果：上述两个问题复现；禁用时无派发、范围未确认时无派发、未知范围独占、pending_host 占用范围均通过。最终修复后相同覆盖通过。复核时独立夹具曾仍预期 blocked 后有一个不重叠任务可选，但修复对未知范围锁全部授权根，实际为零；将夹具期望改为这个更保守且已明确的结果后通过，未改产品实现。没有调用真实 source CLI 或宿主派发工具，没有改生产账本。

实际运行 `node --test outputs/gonggong-workorders/test/coordinator.test.mjs outputs/gonggong-workorders/test/dispatch.test.mjs`，**21/21 通过**。其中包括禁用／范围确认、最多两个候选、写范围互斥、角色路由、用户取舍和越界阻断、新增 blocked／真实路径防护。测试只写 work 夹具。

职责文档正确区分司南收单／协调、偃师设计、业务实现、独立验证、夸父复杂质量事件、谛听事实分析与临时獬豸审查；未把职责表变成固定 Agent 编制。要求独立验证者与实现者不是同一实例，与当前 quality-responsibilities 的单一主责相容。标签路由只决定候选职能，不证明真实身份或授权。

来源与去重意图清楚：只接收 intake_after 之后明确提交的新请求，引用内容和助手建议不能授权；其他聊天在途工作只跟踪不重复派发。当前代码未实现聊天发现／游标持久化或宿主启动，它们属于后续宿主工作流，尚未据此宣称功能已运行。

重复派发方面，pending_host 作为 active 保留是正确的，不超时重派也符合回执不明先对账要求。dispatchPlan 本身无持久预留或全局批次锁，同一快照可反复生成同一计划；真正执行须由唯一宿主协调者串行对账、通过原 CLI 原子 start 保存状态，并检查实际宿主容量。最终启动配置和交接程序需能支持该过程，不能把只读计划当作重复派发防护已端到端验收。

当前 max_workers 以默认 2 限制计划，再预留独立审查职能；真实宿主能力、更低容量及其他活跃聊天实例仍须在实际派发前核验。配置值需为有效整数，文本 scope_confirmed 不产生权限。最终 source_ids／专用来源还须确保没有将同来源的历史或其他业务任务纳入自动授权。

## 共享治理与来源

CURRENT_FRAMEWORK.json 实际指向 gonggong-v0.9，版本 0.9.0。本轮读取该版本 gonggong-check、GOVERNANCE、governance-review、agent-organization、reporting 和 quality-responsibilities 的适用规则；未批量加载整个框架。当前纲领／锁文件、元衡 core／模板实测与前次有效指纹一致，复用正文上下文。

纲领 SHA256 `af0b14934f8998ac7e751475f8192f52adbeb3a26e3d709ee083bcbfeb42148f`；锁文件 `deb2b662be355e3357a55acecc9e5946830c36571d800346ff7d712d720a999c`；core `13baad2a5bcf0ff72c10fd2cc7481894179e66f03617e2db0f1221694073c202`；模板 `bb2eb701555ee0d391efcb013075f3bd9e59ba1648e18b8a400a29794db4c00b`。

元衡评价：目标范围及承诺边界清楚；区分事实和未知；复用现有 Skill、账本与宿主；身份和工具权力留真实委托；框架变化只重验受影响部分；维护不改冻结纲领。两项实现缺陷修正并复核后，上述评价通过本次覆盖；生产运行效果仍须以最终宿主绑定和真实回执判断。最终 Skill 实测 1876 字符（含 front matter 与换行，非 token 数），入口只保留职责、关键边界、工具引用与一条上报要求，没有复制整个框架。

## 初审版本指纹

候选根归档副本：`../archive/quality-workorders/gonggong-workorders`（相对框架根目录）。以下为历史审查结果，不代表当前绑定已启用。

| 文件 | SHA256 |
| --- | --- |
| 调度与Agent职责.md | `84d244068d47cd13afcf03ca8d093dd2c50ff029206e29444d57d888fc9e24d0` |
| dispatch.mjs | `e47102deaa918c4a97fa0da1b5dd8dea0b7d9959c2ede06190ed8b4df333ffa1` |
| coordinator.mjs | `ed16d55cec15c25260f0226bed705b7efe703de0b88582a77874fbee1017cc55` |
| skills/work-order-coordination/SKILL.md | `7f3ee51e47551cb6869e95e62dfa128f3976e5e6ac17380da8706221eedea71c` |

## 最终配置与上报复核

主流程通知后已增量检查 scheduler.json、sinan-runtime/authorization.json、intake-index.json、registry.json、专用账本、report-scheduler.py、reporting.json 与 integration/module.json。scheduler 的范围是 future_gonggong_construction_and_maintenance；只允许 gonggong-maintenance 专用来源，max_workers=2、保留审查槽=1、周期10分钟，框架指针与v0.9相符。授权文件保留用户启动与后续范围答复的消息／turn引用，intake_after 与来源证据一致；本评价者只核对该实际文件，不宣称独立认证全部聊天来源。

实跑只读命令 `node outputs/gonggong-workorders/dispatch.mjs outputs/gonggong-workorders/scheduler.json`：disabled、无新派发、来源可读且无诊断。最终来源已有当前真实主任务 YH-0001，status=running、owner=/root、execution=host_acknowledged、非派发候选；receipt 指向当前 thread/turn，未被记作完成。快照 eventCursor=4，SHA256 `b9672118ed35570f68e643febb0a13a02b7f2a23a6df978387c223a280bb173a`。这是对主流程既有任务状态的只读核对，本评价者未创建、start或ack任何真实任务。

用 v0.9 tools/reporting.mjs 导出的 checkProfile，ownerRoot 取实际交付 bundle，核验 skill 0.3.0、入口摘要、全部必需事件及共享依赖摘要：**通过**。独立脚本为 `work/sinan-profile-independent-check.mjs`；runtime_connected=false 未伪称接通。静态检查 report-scheduler.py 只观察本地真实扫描，模型用量标 null+unavailable，其他宿主／worker覆盖明确缺失，落库 sent 回执才返回上报成功。候选配置初审阶段没有执行包装器；后续快照修正增量仅在隔离数据库执行，见后节，未写真实 outbox或目标库。

新版本 reporting 要求实际宿主绑定、持久 outbox、目标库、必需事件及代表任务实际回执；排队、空队列或配置存在都不是已落库证明。这是后续实际启用需留存的证据，不把本次候选检查偷换为已经运行。

## 最终候选与绑定指纹

以下产品路径均相对候选根；同名初审摘要在前表保留，以追溯并发修正。

| 文件 | 最终 SHA256 |
| --- | --- |
| 调度与Agent职责.md | `960421be1b5b8e3d6c4b51119d74d6e6e83144bb1dbcd52bfeca9acadbf6eb5e` |
| dispatch.mjs（新增CLI基线检查后） | `2aafc9eee9bf39338b650f0f5936835da3ffd38b0588370e5e1c94e8952367b0` |
| coordinator.mjs | `ed16d55cec15c25260f0226bed705b7efe703de0b88582a77874fbee1017cc55` |
| skills/work-order-coordination/SKILL.md | `7f3ee51e47551cb6869e95e62dfa128f3976e5e6ac17380da8706221eedea71c` |
| skills/work-order-coordination/runtime-ref.json | `8ff88ea11d9c40050e4661b9cb8a89f04918c2bb78bc7c72e57d99b8c17db0e5` |
| skills/work-order-coordination/reporting.json | `46ec5dadf66dfb75cb9ddaee83967b07ae6b93ba8762fef0da27683cf885e1a5` |
| scheduler.json（disabled候选，含framework_baseline） | `75c2b5d1b29aac89520086933bcdb625c3d362f6df401bf505791fcb9c421364` |
| report-scheduler.py（快照复用修正后） | `3c3fefb158430e2403e61465b422fc0ccd2b51be94ac54214ad52696bf09f824` |
| integration/module.json（0.3.0） | `027e1273d22b7150311e4bb2a3aff74018040c83151fa4fb054ea27138fa63cf` |
| sinan-runtime/registry.json（相对工作区） | `585c53cf658c03d303ba4911db0d4eff824ac7b50a12fec6d93a13aa38a2d502` |
| sinan-runtime/authorization.json（相对工作区） | `1a1ffdb9ddf110f6bb4868d224df8d1c8143f2e143d7eaa3d671bc31ffa6865e` |
| sinan-runtime/framework-baseline.json（预接入基线，相对工作区） | `219a2fd0b307a7f300dbeb6636fb1b0f67a200c90e5bc223d0699a14e273d4da` |

### 最后增量：同路径基线变化

主流程补齐 dispatch CLI 对 scheduler.framework_baseline 的校验：不仅比较当前框架目录，还核对基线 root、当前 framework-manifest.json 的 SHA256 及 CURRENT_FRAMEWORK.json 的 SHA256。仅复核新增逻辑，没有重跑无关21项测试；前述21项结论绑定其当时版本，其余规划代码未变。

独立脚本 `work/sinan-baseline-independent-check.mjs` 在 work 构造独立框架／指针／配置，实际通过四项：匹配基线允许禁用状态只读扫描；目录不变而 manifest 内容变化时 exit=1；root不变而指针内容变化时 exit=1；框架目录变化时 exit=1。没有改真实框架、配置或启用生产。

该增量通过，当前候选结论维持。当前配置仍 enabled=false，framework-baseline.json 为明确的预接入基线；正式接入更新 manifest 后须由有权主流程生成并切换经过明确复核的 activation 基线，不能把自动重写基线当批准。该文件和指纹是可信本地操作员边界内的一致性检查，不替代身份、授权、逐文件变更审查或防篡改安全根。生产activation／实际落库／周期唤醒证据尚待后续独立核对。

## 未覆盖项与交接

### 上报包装器重复快照增量复核

主流程在真实第二轮扫描中发现同一 agent_id／version／definition_digest 创建新快照 ID 会被 logical_keys 拒绝，修复后改为检索已有快照并复用完整原记录、context 的 primary_agent_ref 和 binding.agent_snapshot_ref。本评价者仅对该修正增量验证，不触碰真实队列，不复跑无关21项。

独立脚本 `work/sinan-repeat-report-independent-check.py` 调用实际产品 report-scheduler.py 和当前实际框架；将 report_state、空来源 registry、基线和配置放到 `work/sinan-independent-fixtures/repeat-report-z2kdjv8p`。为满足包装器按配置目录寻找入口的约定，在隔离目录逐字复制调度器、协调器与职责文档，未改产品文件或复制共享框架。两轮都 enabled=false，只执行真实的本地只读扫描并上报到隔离 SQLite。

**结果：连续两轮成功，均获得 sent 且 committed=true 的实际隔离落库回执。** 首轮 inserted=10、replayed=0；次轮 inserted=9、replayed=1。数据库仅1条 agent_snapshot、1条 snapshot logical key；有2条 request、2条 step、2条 request_end；两批 context 及 binding 引用同一快照，原始快照记录完整相同。证明本次修正覆盖“顺序重复扫描产生重复快照”问题，增量结论通过。

原始结果与回执保存于 `work/sinan-repeat-report-independent-result.json`。本测试不证明并发扫描竞态、真实历史失败批次修复或定时任务已触发；这些仍须实际证据。主流程告知真实第三轮已 sent，但本次没有读取真实队列核验该声明，不能把隔离回执冒作生产回执。

本次未测试真实聊天分页发现、跨轮收单去重／恢复、周期自动唤醒、原 CLI start→宿主创建→ack、取消与租约、真实身份隔离、端到端结果回收、通知或生产谛听落库。隔离上报的顺序重复扫描已验证，不等于上述生产覆盖。未重跑旧质量 Agent 场景。报告不是启用批准；本评价者未改产品文件、启动自动任务、派生 Agent 或联系其他聊天。

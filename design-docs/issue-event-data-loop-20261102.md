# 接通 GitHub Issue 事件协调与 Hermes 数据交接，核销陈旧状态

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/9

<!-- olympus-request:issue-event-data-loop-20261102 -->

缺口证据：work-items.json 的 ariadne_source_registered=false；Olympus/modules/ariadne/runtime/registry.json 的 sources 为空；data-collection/sources.json 只索引 #1/#2 且 ingestion_confirmed=false；部分工作区/组件元数据仍写候选待审，与后续精确准入及发布证据不同步。

目标：Issue 新建、状态、依赖、决策与执行回执到达时，通过实际宿主入口协调进度和文档；所有模块复用 Hermes，交付与消费状态有真实回执。GitHub 仍为工单状态权威，不伪造元衡账本以适配只支持文件账本的旧协调器。

验收：
- [ ] 选定并显式绑定实际 GitHub 事件来源与当前宿主，按 repository+issue+事件 ID 幂等；无事件不调用，无 cron/轮询/延时唤醒。
- [ ] 类别、状态、负责人、依赖、需决策项及真实执行回执有明确映射；在途任务只关联不重复派发。
- [ ] 代表任务从 Issue 事件到本地文档/执行回执、GitHub 回读贯通；父单不因子单完成自动关闭。
- [ ] 修订当前状态元数据并保留历史；配置、排队、文件记录、提交、谛听消费分别证明。
- [ ] 使用同一 Hermes 分析入口进行一次授权范围真实读取，覆盖范围与未知用量如实记录；不重复导入冒充自产。

状态：待判断。实际长驻 webhook 接收宿主/权限尚未绑定；不以本单建立常驻服务或新增时间自动化。可先推进单次显式宿主调用与数据核查。

## 已完成的数据核查

已通过同一 Hermes analyze 入口真实读取本次clone中的 olympus-workspace 数据，回执见 `data-collection/issue-event-read-receipt-20261102.json`。记录包含旧发布32条及本次4张工单登记，共36条；范围为已有文件，不代表实时事件全覆盖。执行消费者为当前Codex根任务，未冒充谛听Agent消费。

修订当前元数据语义，保留历史证据与 ariadne_source_registered=false；GitHub仍为权威，Ariadne实际源为空。待接入的是实际宿主GitHub事件来源、幂等收件及协调适配，并非恢复已废止的定时扫描。远程事件需实际可用的GitHub权限（插件读可用、写403，本次用已有CLI）。

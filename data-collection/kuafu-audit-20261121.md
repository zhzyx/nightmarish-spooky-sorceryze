# 夸父事故对账 · 2026-11-21

来源与授权：[总单 #426](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/426)。仅事故恢复完成可关闭，原业务验收独立。关闭单逐项保留原失败、后继相同步骤、候选和 main 证据，链接见各单本轮评论。下表的“保留”不代表工作已完成。

## 仍需原责任链或现场输入

|事故/工单|核实事实及下一动作|
|---|---|
|#1697|PR1698/main21654eb5已修复flood/输出排空与最终邮箱竞态，PR1699完整模块CI通过；其他未映射事故及旧worker终态仍未知；已恢复的稀疏检出历史文件缺失对应 PR1704/main8bb0386a，不覆盖其他事故。不得释放未知工作者占用。|
|#1628|Windows service 身份 AccessDenied 需有权管理员；Docker mount 数组顺序误判沿唯一迁移责任链复验。当前 #1550 已限定内部开发联调，不进行正式部署。|
|#1653|A8 已交付，但原责任者明确保留间歇 curl28/reset；原环境稳定消费回执仍需补齐。|
|#1586|13本地事故中5有assessment、8缺原诊断；PR1702已合入9871aacb。不能以checkpoint或运输成功覆盖未映射原动作及实际消费者。|
|#1555|退出137同头重跑已过；底层原因未知及后续 Git HTTPS 事故仍需原责任链映射。|
|#1540|个人 Key 被拒需原生产管理端及原宿主事故，当前主机没有原件。|
|#1531|SDK准备已纠正，缺原 SCons 操作和实际消费者复验。|
|#1530 #1503|下载、隔离安装、回退、全生产与崩溃恢复/成本验收仍有剩余，250压力场景明确延期。|
|#1508|resolver 停留 planned/67% 原失败未由运输分片交付覆盖；需原输入下解析、发布与回写实测。|
|#1445|39本地事故已分簇对账；剩余Windows stage.rename WinError5原句柄占用、原cp936吞stderr诊断缺失、Linux300秒超时部分运输占时、两个同模块held生产者终态。已交付子项分别引用1473/1479/1485/1490/1494/1500；不重放未知生产者。|
|#1680 #1669 #1627 #1428 #1397|kaiyunxue 原宿主 local_incident 不在当前主机；保留原发布链，需诊断与同一操作恢复映射，业务关闭不代替事故恢复。|
|#1374|PR1385/main6590bc7e 后继静态检查已恢复；另两笔 kaiyunxue 本地 delivery 事故仍缺原件。|
|#1364|原部署六项验收已完成，剩余是清理被宿主自动审批拒绝（blocked by policy）；不绕过或盲重试删除。|
|#1360 #1356 #1353 #1136|原业务已有交付；缺跨宿主逐事故的诊断与原操作恢复，保留未知。|
|#1357|原requirements-intake仅AssertionError且缺process.log；同名后继步骤成功不足映射原场景，需原诊断或明确可复现输入。|
|#1559|原250 context burst退出137；后继相同步骤SKIPPED，不能以安装生命周期通过覆盖，保留已明确延期边界。|
|#1349|macOS原网络场景已恢复并有子项评论，另多笔跨宿主validation/delivery事故仍需映射。|
|#833|原 run43097980046 仍 queued、jobs=0；PR852恢复业务不解释旧队列。保留原运行，不重发旧候选或擅自取消。|
|#807 #561|保留明确暂停/停止范围和在途工作，不重启旧草稿。|
|#662|官方 CodeBuddy ACP initialize 成功、session/new -32000需认证；有权账号完成登录后原业务请求及基线时延验收。|
|#907|原7aa7c6f0推送与PR906/911替代关系需原发布者核对。|
|#514|IME边界候选位置、PR/main及真实边界验收仍缺映射。|
|#511 #522|指定Windows设备、安装版/会话的内存或连接阶段与时延现场回执不足。|
|#414|指定macOS安装版真实图片/网格生成、配置及Finder重开恢复未验收。|
|#217|刷新、切换、五强度映射和默认强度真实发送的完整安装版验收尚缺。|
|#954|macOS清理任务缺消费者进程与完整清理回执；当前Windows不能代证。|
|#953|提示词子集已交付；其他宿主/供应商全链路行为未验收。|
|#951|11/14用户已恢复仅源码合入授权；PR1245接替1234，须先取得原发布链终态/交接，禁止安装或继续原游戏。|
|#896|intake标签已恢复；native依赖凭据候选整合及正式安装真实运行仍未验收。|

## 方法、边界与清理

复用了已验证 github-issue-delivery/reconcile-workflow-incidents revision2。反例：#1559的250压力步骤被跳过、#833零作业旧队列、跨宿主原件缺失，均不能由后来绿色运行代替。使用仓库PowerShell入口避免遗漏tenant；第一次直接CLI遗漏参数的失败与纠正已沿同事故记录。

本轮仅修复复现的#1545/#1588静态检查，不改运行算法；未重启停止草稿、取消其他运行、释放未知占用或写入他人工作树。当前根工作区已有改动完整保留。本轮记录在独立工作树交付；初期审计无临时资源；后续#1545实现/验证及#1588测试产生本任务私有测试环境和构建目录，交付前保留必要原始回执，交付后核对进程终态再清理。交付后仅清理本任务独立工作树/分支及已归档的本任务副本，不清扫历史资源。

## 定向修复

#1588当前main仍有3文件Ruff格式失败，已修复格式及导入顺序；4原路径ruff check --no-fix、format --check均通过，executor23测试及Direct3D16测试通过。#1545当前main的CODEOWNERS等仍失败，已沿原单in-progress接单并修复；最终验证见本轮补充结果。

## 已验收的事故恢复

以下27张均已completed关闭并回读status:done，完整原失败与恢复依据在对应评论和kuafu-audit-closures-20261121.json。#1706由原责任者另行交付并关闭，不计入本会话关闭数。

|事故|关闭回执|
|---|---|
|#1684|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1684#issuecomment-7051244223)|
|#1692|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1692#issuecomment-7051242118)|
|#1693|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1693#issuecomment-7051239932)|
|#1695|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1695#issuecomment-7051248591)|
|#1696|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1696#issuecomment-7051246555)|
|#1546|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1546#issuecomment-7051276358)|
|#1593|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1593#issuecomment-7051278305)|
|#1594|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1594#issuecomment-7051280478)|
|#1599|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1599#issuecomment-7051282417)|
|#1632|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1632#issuecomment-7051284542)|
|#1569|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1569#issuecomment-7051286846)|
|#1496|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1496#issuecomment-7051307533)|
|#1596|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1596#issuecomment-7051309701)|
|#1514|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1514#issuecomment-7051320157)|
|#1346|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1346#issuecomment-7051326798)|
|#1489|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1489#issuecomment-7051250078)|
|#1478|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1478#issuecomment-7051252498)|
|#1482|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1482#issuecomment-7051254892)|
|#1498|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1498#issuecomment-7051257413)|
|#1507|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1507#issuecomment-7051259923)|
|#1497|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1497#issuecomment-7051262252)|
|#1493|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1493#issuecomment-7051361100)|
|#1470|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1470#issuecomment-7051363862)|
|#1611|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1611#issuecomment-7051366637)|
|#1381|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1381#issuecomment-7051369477)|
|#1660|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1660#issuecomment-7051272419)|
|#1446|[恢复证据](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1446#issuecomment-7051433514)|

## 修复候选的最终本地验证

#1545通用静态检查、许可/补丁摘要及新增/缺失补丁拒绝均通过。独立Windows MSVC19.51 CPU Release构建全部目标成功，CTest api/c-api/binding/tokenizer四项通过，geometry7项通过。测试显式保留默认编译选项并为标准getenv加入_CRT_SECURE_NO_WARNINGS；首次缺DLL后仅给测试子进程补Release库目录，使用同一二进制复验通过。未宣称默认MSVC、Vulkan、GPU或模型质量验收。

/root/audit_legacy独立对照旧C++输入经同版clang-format结果，确认差异仅格式/pragma/文案；Python为类型/格式及导入。LICENSE/NOTICE与GGML补丁原件未改。最初patch集合缺口已修，审查通过。正式门禁一轮通过，新增判断记录将随最终writer再次核验。

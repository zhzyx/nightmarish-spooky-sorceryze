# 推进当前 Git 内夸父阻塞

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/426
稳定需求 ID：daqian-direct-dfb3577984bfc0915d62。

## 2026-11-21 本轮授权与范围

用户明确要求「排查并推进当前git内所有夸父阻塞」。当前责任者为 Codex 当前会话，GitHub 操作者 Sail-Li，已回读 push 权限。复用原总单，不重复创建需求。产物为逐事故恢复与剩余条件对账、权威 Issue 状态及公开证据；本轮复现 #1588 AINative格式失败与 #1545 SkinTokens检查失败，修复范围增加这两项原失败路径的格式、类型、CODEOWNERS及独立CMake/许可证检查边界；不改算法与框架定义。所有持久路径相对各文件所属仓库根。

回读开放夸父跟踪单、原始失败运行/本地事故、后继原步骤与精确候选、main 和业务验收。仅对应故障恢复有证据时关闭事故，不自动关闭原业务。保留在途候选、明确暂停、原设备/账号验收、人工节点及审批拒绝。没有把后来任意绿色 CI 当作恢复。没有新增定时扫描。

采用已验证 github-issue-delivery/reconcile-workflow-incidents revision 2：按运行、attempt、job、步骤和场景对账；缺失原件、被跳过测试及业务未验收均保留未知。初期三位原生子Agent受委托审计及指定工单收尾；发现可复现问题后，audit_runs获明确委托在本任务隔离工作树修复#1545，当前责任者修复#1588，audit_legacy独立审查。未操作其他工作者的生产副本。实际工具启动/终态在当前会话中可核验，不宣称使用了生产派发桥。

验收：每项核查保留原失败、恢复或缺口、责任链及下一事件；关闭项回读 completed 与 status:done。全部阻塞清除前总单保持开放。公开报告见 data-collection/kuafu-audit-20261121.md。独立只读核对、正式门禁、提交后历史校验及精确候选 CI 用于本轮记录交付，不代替未完成业务验收。

本轮 intake 最初遗漏 tenant 参数被拒绝；读取 work-items.json 后以 tools/run_issue_gate.ps1 默认 gonggong-workspace 重验成功。沿原事故 c993f138…保存判断，未修改门禁。

## 定向修复验证

#1588：Ruff 0.17.1四个原路径复验，3文件格式及一处导入顺序纠正；ruff check --no-fix及format --check通过。executor 23项测试通过；Direct3D 16项在本任务隔离Python3.14测试环境安装numpy2.5.5/Pillow13后通过。初次缺numpy/PIL属于本机测试环境缺依赖，不是已交付运行包故障。

#1545：独立Apache-2.0工具的Godot版权/include规则不适用；保留LICENSE/NOTICE、原版权及CMake输入。通用静态检查与自身许可/构建验证仍执行。具体定向结果以本轮报告及精确CI为准。无新模块、运行服务或生产配置切换。

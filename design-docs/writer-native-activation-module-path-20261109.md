# 签发后原生入口核验的独立 CLI 导入修复

request_id: writer-native-activation-module-path-20261109

真实工单 [#591](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/591)，关联 #393、#462。唯一源修主责为 `/root/runtime_entry_fix`，由原用户完整工作流验证及发现阻断修复授权承接；Root 负责原业务的真实后验。新任务不重开或修改原 #462 验收状态。已真实 intake，并读取非空夸父职责后接单。

## 真实故障与最小边界

Root 在真实 PR590 合入后运行正确 Node/Python/GitHub 环境的 writer_submit --inspect-pr590。GitHub/main 回读完成后，后置原生 App 入口核验在 verified_manifest 的 editor_native_app 延迟导入处抛出 ModuleNotFoundError，CLI exit1。原 stderr 及空 stdout 原件保留；后续由已有官方 standalone activation CLI 完成全守卫激活，不追认原失败调用成功。

writer 通过 importlib 按文件加载 tools 模块，父解释器的正常脚本目录却是 issue-workorders。后续本机 App/managed entry 的同目录延迟导入不成立；测试进程预先将 tools 加入路径或缓存模块会掩盖问题。修复仅将后置事件交给干净独立 Python 进程：固定受信安装 tools 工作目录、固定执行代码、repo 独立 argv、真实 fresh inspect 的 report 作为 JSON stdin，忽略 Python 环境/用户 site。正常模块查找可解析整个同目录依赖图，不修改父进程 sys.path 或全局模块缓存，不增新 CLI 业务事实输入接口。既有 manifest standalone CLI、activation 验证及正常 tools worker 均保持。

不改 C++、应用包、旧 manifest/source_inputs/binding/回执、生产配置/历史，不重编应用，也不把新 helper 变更追标到已经验收的 C629 产物。

## 验收

1. 干净解释器、无 tools PYTHONPATH/模块缓存，真实 writer CLI 经固定独立调用完成现有本机原生核验；远端仅以明确 mock fixture 替代，不能运行生产入口。
2. PR/Issue/main 仍由 writer 在原权威路径 fresh inspect，activation 继续独立核来源、产物及验收。失败保留 pending，不把导入、异常、非 JSON、非零退出误认作 activated。不得添加任意 helper 路径或未验收事实输入。
3. 原 manifest standalone/普通 native after_delivery 路径必要回归，完整签名、来源、验收和幂等守卫不变；无应用重编。
4. 固定静态、正式 gate/writer、非作者独审与精确 CI；main 等 Root 独审放行。新 bug 保持开放，等 Root 从新可信 checkout 真实 --inspect-pr590 对已激活原入口幂等回读，再按实际结果关闭。

## 当前验证与产物边界

从实际最新 main f9c45dec（包含 7d461d9a）隔离。唯一产品修改为 writer_submit.py；activation、native App、managed entry、candidate/source manifest 和 native finalizer 原字节保持。

作者实跑：writer 10 项、干净 CLI 3 项、原 activation 16 项及正确 Node/GitHub 环境的全部适用固定静态检查通过。干净 CLI 使用系统临时目录中的真实 Git 与签名 App，覆盖整包核验/复制/重复复用、坏签名保留原入口且只返回 pending、带空格/引号/中文 repo 只作为参数、PYTHONHOME/PYTHONPATH 与 repo 假模块陷阱不加载。GitHub 读取与签名信封为明确离线夹具，不声称真实服务批准。完整 native/managed 模块图验证为导入解析，不冒称重复执行全部 managed link 业务验收。

幂等保留应用包、源码、原 manifest/binding；既有 helper 可原子更新 launcher receipt 的真实 main/reused 元数据，不承诺回执字节永远不变。新脚本本身仍是源输入，不能把它的新摘要追标进已接受 C629 的旧 manifest。

保留首个 Git URL 夹具配置错误和首次本地 preflight 漏配 Node 的失败原件；修正调用环境/夹具后通过，不追认原失败。正式生产 App/入口/用户历史/配置未在本修复中操作，真实 --inspect-pr590 回读由 Root 执行。

# 主屏命令切换后验证实际选中与可见状态

授权来源：用户已要求发现引擎内命令缺口即修复，并完成独立验收和 main 交付；2026-11-08 宿主在 #483 实际验收中将本缺陷独立交接给当前执行者。关联原命令覆盖 #386（已关闭，不作为本次生产准入）。

实际观察与源码判断分开保留：#483 的旧 source545 实际应用处于 AINative 时，生产 POST `/v1/messages` 的 `main_screen` / `AI Chat` 返回 routed/completed/ok，但 `visible:false`，界面仍是 AINative；真正点击 AI Chat 后才切换。PR #510 的 main28b 及本次最新 main a144 源码仍调用 `make_visible()`，会被当前主屏禁止自动切换的标记阻止，且无条件返回成功；未将旧应用观察冒称为新版运行失败。

本次最小产物：主屏导航复用真正原生主屏选择入口，实际选中且可见才返回成功，未知或不能切换时明确失败；只读主屏列表补充可见状态。保持原权限、人工确认、身份、咨询模式与 autoexec 边界，不操作用户应用、会话历史或全局配置，不扩展通用框架。

验收：在 macOS arm64/Clang 的私有 `_sc_` headless 编辑器中，经真实生产 POST→receipt→GET state/list 回读验证 AINative→AI Chat→其它屏；每一步核对唯一选中、当前主屏、目标可见和旧屏离开，不使用 EditorInterface 另一入口替代路由。保留未知目标、权限/确认及现有命令回归。独立审查、必要编译、正式门禁、精确 CI、main 回读和本 bug 的 completed/status:done 结束回执全部完成后交付；不代替 #483 或原用户入口整体验收。

基线：真实远端 main a144411fb39d6470ed2b70a9f6ea6ad8220695ac。独立分支由本任务持有，修复范围为主屏命令及其现有测试。

本地验证：原 PR #510 的真实 main28b 编译产物在私有 headless 回归中实际失败，POST/receipt 均报完成而 state/list 仍停留旧屏，详见 `data-collection/issue542-main-screen-before.json`。修复后的 20 项完整命令回归通过，8 次主屏导航均核对真实回执、当前主屏、唯一选中、目标可见及旧屏退出；未知目标失败且状态不变。6 个原生状态/权限语义单测共 85 断言通过。原生单测第一次因私有夹具漏测试数据导致初始化失败并崩溃，保留该失败并按原启动约定修正夹具；产品未为此改动。实际结果见 `data-collection/issue542-main-screen-after.json`。独立审查及正式 Git/CI/main 结束状态沿本单继续回读，不代替父任务验收。

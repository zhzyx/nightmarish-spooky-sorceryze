<!-- gonggong-request:yanluo-issue-63-nonwindows-artifact-20261105 -->

# 修复自更新对 macOS/Linux 无扩展名 a/b 产物的接收判定

父单：#63；审查来源：#88。需求文档：`design-docs/yanluo-issue-63-nonwindows-artifact-20261105.md`（路径相对仓库根）。

已交付依据：平台 allowlist、产物命名与 Python venv 分支修正 c6445d3961f9 已合入；macOS 增量编译记录不证明自更新产物接收成功。
已合入提交/审查基线：`c6445d3961f9de835b823a1529fd0a2d9f3ff478`。

剩余验收：

- [ ] 修正 _poll_engine_build 对 .self_update_a / .self_update_b 无末尾点产物的接收判定，同时保持 Windows .exe 接收及拒绝非编辑器/非 a/b 名称。
- [ ] 为 windows/macos/linuxbsd 的实际 artifact_path 输出建立 a/b 正反例一致性验证；记录纯函数/静态验证与真实平台端到端执行边界。
- [ ] 按原 #63 目标验证非 Windows 自更新代表链路，实际平台不可用时保留 unknown，不用命名解析代替运行。

边界：独立审查已执行实际 Python artifact_path probe：Windows=True、macos=False、linuxbsd=False，对照 C++ 第 4020 行 requires '.self_update_a.' 或 '.self_update_b.'。本审查不修代码、不编译；后续绑定精确候选。

证据：tools/editor_self_build.py:artifact_path; editor/docks/ai_chat_dock.cpp:4020; design-docs/build-engine-macos-20261105.md。

本单由阎罗全仓审查及独立复核形成，后续由司南按真实需求事件派发；创建不等于已执行或生产启用。原父单未满足全部验收，继续开放；本单完成后重新核对父单。

<!-- gonggong-host-git:Sail-Li -->

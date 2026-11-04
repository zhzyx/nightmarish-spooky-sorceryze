# CodeBuddy CLI 桥接：chat 输出在管道下被截断到 8 KiB

<!-- gonggong-request:codebuddy-cli-stdout-fix-20261104 -->

- 需求 ID：`codebuddy-cli-stdout-fix-20261104`
- Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/50
- 类别：`type:bug`
- 责任人：待实际指定

## 原始需求与目标

问题（2026-11-04 本地复现）：CodeBuddy CLI v2.176.0 在 stdout 为管道时，`--print --output-format json` 的输出被截断到 8192 字节；同一调用的 stdout 落到文件时输出完整（实测 22233 字节 vs 管道下 8192 字节）。`tools/codebuddy_cli/godot_bridge.js` 的 chat 分支因此读到不完整的 JSON，编辑器需求整理（issue-agent）报 `Requirements model API failed in CodeBuddy`，并且没有具体原因。

目标：chat 分支能完整取回 CLI 输出；需求整理失败时报出实际错误；为较慢的模型留出足够超时。

## 范围与非目标

范围：

- `godot_bridge.js` chat 分支：CLI 的 stdout 改为写入桥接临时目录中的文件（`fs.openSync` 后作为 stdio fd 传入），进程结束后读取；仍按 2 MiB 输出上限拒绝超长输出。
- chat 请求传 `--effort medium`；chat 超时 120 s → 180 s。
- `customizations/components/godot-host/requirements_agent.py`：桥接调用超时 150 s → 210 s，大于桥接内部超时；失败时附带桥接 JSON 错误信息或 stderr 摘要。

非目标：不修改 CodeBuddy CLI 本身；不改变 ACP（`godot_acp.js`）长会话通道；不放宽门禁或权限。

## 验收标准

- [ ] chat 分支取回完整输出（超过 8 KiB），编辑器需求整理返回正确的 choices。
- [ ] 输出超过 2 MiB 时仍以 `OUTPUT_LIMIT` 失败。
- [ ] 需求整理失败时错误信息包含桥接给出的原因。
- [ ] `tests/editor/test_codebuddy_bridge.js` 全部通过。

## 验证与采集证据

- 本地复现与验证：同一调用落到文件 22233 字节、管道下 8192 字节；修复后编辑器 chat 返回正确 choices（2026-11-04）。
- `node tests/editor/test_codebuddy_bridge.js`：pass 35 / fail 0。
- 谛听事件：`gonggong-diting-data/events/gonggong-workspace/codebuddy-cli-stdout-fix-20261104/`。

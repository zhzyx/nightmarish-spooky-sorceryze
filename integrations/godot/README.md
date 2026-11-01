# Godot + Olympus 运行与目录

当前接入直接编译进引擎，不再运行复制补丁安装器。

| 位置 | 职责 |
| --- | --- |
| `editor/docks/ai_chat_olympus.cpp` | 所有模型请求前的框架检查与取消隔离 |
| `editor/docks/olympus_panel.*` | 原生框架状态、校验和分析页面 |
| `customizations/components/godot-host/` | Python 宿主适配器及单元测试，唯一实现 |
| `tools/olympus_bridge.py` | 引擎稳定调用入口 |
| `tools/build_olympus_editor.ps1` | Windows 编译及 AIChat 回归检查 |
| `tools/launch_olympus_editor.ps1` | 绑定当前工作区、Python、Node 并启动编辑器 |
| `samples/olympus-workbench/` | 可直接运行的示例工程 |
| `tests/editor/*olympus*` | 实际编辑器调用链测试 |
| `Olympus/` | 全量同步框架，独立准入边界不变 |
| `design-docs/`、`data-collection/`、`olympus-hermes-data/` | 需求、采集交接和真实事件，分别维护 |

## 构建和启动

需要 Windows C++ 构建环境、Python（3.14 或带 zstandard 的兼容版本）、SCons、Node.js。当前本机构建配置禁用未安装 SDK 的 AccessKit、D3D12 和 ANGLE；不是这些驱动的发布验收。

```powershell
./tools/build_olympus_editor.ps1 -Python PATH/TO/python.exe
./tools/launch_olympus_editor.ps1 -Python PATH/TO/python.exe -Node PATH/TO/node.exe
```

二进制位于忽略的 `bin/`；预编译包应解压到对应源码检出的 `bin/`，不提交编译缓存。启动后在 Agents 配置 HTTP 模型 endpoint、model 和凭据，或自行配置已安装的兼容 CLI。仓库不捆绑第三方账号登录状态和 CLI 私有依赖，默认使用 HTTP 配置入口。

Olympus 页设置工作区、Python 和租户，点击任一检查按钮保存设置。上游位置可通过环境变量或本机 `.olympus-local.json` 绑定；示例文件在仓库根。没有有效上游、定义准入或文件数据回执时，聊天明确拒绝发送，不能回退为未受框架管理的模型聊天。

## 验证

```powershell
python customizations/components/godot-host/test_bridge.py
python tests/editor/run_olympus_chat_gate.py --godot bin/godot.windows.editor.x86_64.console.exe
python tests/editor/run_olympus_chat_gate.py --godot bin/godot.windows.editor.x86_64.console.exe --mode accepted
python tests/editor/run_olympus_chat_gate.py --godot bin/godot.windows.editor.x86_64.console.exe --mode cancel
python tests/editor/run_olympus_chat_gate.py --godot bin/godot.windows.editor.x86_64.console.exe --mode tool
python tests/editor/run_olympus_chat_gate.py --godot bin/godot.windows.editor.x86_64.console.exe --mode recovery
python tests/editor/run_olympus_chat_gate.py --godot bin/godot.windows.editor.x86_64.console.exe --mode recovery_rejected
python tests/editor/run_olympus_chat_gate.py --godot bin/godot.windows.editor.x86_64.console.exe --mode recovery_cancel
python tests/editor/test_olympus_distribution.py
```

accepted 使用临时合成上下文和本机 HTTP 服务，仅验证传输。它不是生产批准；真实框架测试当前验证的是正确阻断。合成数据均位于临时仓库，不写入生产事件目录。

源码根的 `bin/` 接受匹配源码提交的 Windows x64 预编译包。构建脚本会重新生成被 Git 忽略的 `.gen.*` 文件；不再提交生成代码与构建缓存。C# 示例另需 .NET 版 Godot 与已安装 .NET SDK，本次验证的运行示例是 `samples/olympus-workbench/`。

框架候选通过 `Olympus/sync/gonggong_sync.py prepare` 在新目录生成，全量核对来源。正式 `build`、`check` 和聊天上下文入口仍要求上游正式准入；候选验证不能解锁聊天。来源索引为 `Olympus/source-evidence.json`，原件留在外部上游，不随本仓库复制。源码移动后按示例配置上游相对位置即可重新核验。

`verification.json` 是初次独立目录接入的历史证据，保持原字节供旧事件引用；其中源码路径与状态不作为当前版本的验证结论。当前需求及验收见 `design-docs/godot-olympus-chat-20261102.md`。

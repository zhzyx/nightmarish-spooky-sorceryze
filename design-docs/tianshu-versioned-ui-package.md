# 独立加载、发布与回退天枢图布局业务包

天枢图布局和展示脚本从原生编译依赖中分离；提供可实际使用的打包、选择、分发、校验及回退入口，保留默认开箱即用、工单间隔离和宿主权限。相同编辑器二进制下验证新旧版本可观察的布局行为，覆盖损坏、版本不兼容和缺失场景。

父工单 [#687](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/687)。独立交付 [#689](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/689)。目标为 main。

## 桌面编辑器的布局与展示包

Windows、macOS、LinuxBSD 的编辑器从安装目录加载 `tianshu-ui.json`。SCons 在 `bin/` 生成此文件，裸编辑器随可执行文件一起分发；macOS App 将其放在签名前的 `Contents/Resources/`。Windows 安装脚本逐文件核验并登记哈希。原生自更新的两个槽位分别使用 `tianshu-ui.self_update_a.json` 和 `tianshu-ui.self_update_b.json`，候选清单绑定实际包摘要。Web 和移动编辑器继续使用原来的内嵌脚本。

试点包包含 `editor/docks/daqian/graph_layout.gd` 与 `issue_graph.gd`。宿主使用固定接口 `tianshu-graph/1` 加载这两个脚本。图规则、工作区、权限检查、工单执行与看板适配器仍随引擎构建。包内脚本具有编辑器脚本权限，发布者需要审查脚本，并通过可信渠道提供整个包的 SHA-256。包内摘要用于检测内容损坏。

从已经审查的候选源目录打包后，将生成的文件和输出摘要交给对应工单。以下示例在 PowerShell 中为单次启动选择候选，可在不同进程中并行验证不同工单。

```powershell
python tools/package_tianshu_ui.py --source editor/docks/daqian --version 2 --output bin/tianshu-v2.json
$env:GONGGONG_TIANSHU_UI_PACKAGE = (Resolve-Path bin/tianshu-v2.json).Path
$env:GONGGONG_TIANSHU_UI_SHA256 = '<已审查候选的完整 SHA-256>'
& ./bin/godot.windows.editor.x86_64.exe --editor --path <项目目录>
```

回退时在新的进程环境中选择先前版本的绝对路径与对应摘要，或取消两项环境变量以使用安装包。包缺失、损坏、摘要不符或接口不兼容会在天枢页显示错误，日志记录拒绝原因。修复选择后重新启动编辑器。用户工程中的同名文件不会参与发现。

在仓库根执行 `python tests/editor/run_tianshu_ui_package.py --godot <裸编辑器> --report <报告路径>`，可用隔离工程复验同一编辑器的换包、拒绝和回退。

# B06　编辑器外壳、桌面资源包与宿主桥

本清单供 U01 调整原生命令、K00 核对构建责任时使用。基线是 `0e1dcb293a55e3034bf92b4e02bc6b0028e5fb14`。入口来自 [B01](gonggong-ai-workbench-b01.md) 和 [B03](gonggong-ai-workbench-b03.md)。[工单 #1872](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1872)

| 改动输入 | 实际消费者和生效动作 | 可用版本与回退 |
| --- | --- | --- |
| 原生命令、停靠容器、C++ 包加载器，以及构建脚本选入生成头的资源 | [原生加载器](../editor/docks/daqian_dock.cpp) 与 [SCons 输入](../editor/SCsub) 决定编译和链接范围。桌面目标与内嵌目标分别跟踪各自选中的输入。在隔离源树按[构建入口](../tools/build_gonggong_editor.py)重建相应平台编辑器并验收。 | 保留上一份完整安装及其匹配的 sidecar。此次使用安装修订 `22ba06d9543c16ca5e91c0a5c8a4c8fc2545a4f4` 的编辑器，SHA-256 为 `fcb08b5401d18c129368bc3ee431b24cfe64aa788cde509a49871495017190e9`。停止本次候选进程，重新调用上一安装内的编辑器和配套包，在同一测试项目复验。 |
| 桌面天枢 UI 包的布局、标签或其他打包输入 | [UI 打包器](../tools/package_tianshu_ui.py) 产生独立资源包，由桌面加载器检查路径、兼容版本及内容摘要。更换候选时同时选择包的绝对路径和对应摘要。板数据运行包的独立输入及 ABI 另见[看板实测](../data-collection/tianshu-board-runtime-package-1404.json)。 | 已安装包 `3b581a11d1e472eb698a6da997d5e0887bdf7864ea0cf802504973bf68feb462`。在独立测试进程中撤销本次设置的 `GONGGONG_TIANSHU_UI_PACKAGE` 和 `GONGGONG_TIANSHU_UI_SHA256`，重新启动同一编辑器，读回安装包。 |
| AI Chat 调用的宿主桥及其 Python 依赖 | [聊天桥选择器](../editor/docks/ai_chat_gonggong.cpp) 选择可信宿主路径。[便携入口](../tools/gonggong_bridge.py) 从相应目录加载[宿主桥](../customizations/components/godot-host/bridge.py)。修改 Python 行为时部署同一版的宿主文件，并通过所选入口发出真实请求。修改 C++ 选择器时走原生构建。 | 托管安装回退时先退出该候选编辑器，用上一完整安装内的编辑器打开原目标工作区。核对其安装清单中的修订和编辑器摘要，确认该安装根内的桥及配套 Python 文件齐全。AI Chat 将从这一安装根选桥。单独核对宿主时，从已验收的宿主检出运行 `python <旧检出>/tools/gonggong_bridge.py status --workspace <目标工作区>`。本次对基线、上一安装修订、基线依次执行，三次返回 `ok=true` 和框架版本 `0.10.0`。两修订的入口 blob 相同；回执记录了实际选择来源。 |

## 定向验收

从仓库根运行下列 PowerShell 命令，使用待检安装中编辑器的绝对路径和测试报告路径。

```powershell
$env:PYTHONPATH = 'tools'
python tests/editor/run_tianshu_ui_package.py --godot $editorPath --report $reportPath
```

本次 Windows 编辑器实测，安装包显示「48 应用更改」，选择候选后为「96 应用候选」，撤回后恢复「48 应用更改」。测试还验证了错误摘要、缺少摘要、项目内相对路径、候选缺失、包损坏、版本不兼容和默认包缺失的拒绝结果。原生重链接沿用已有实际 SCons 编译记录，其中选定加载器的改动触发重编和链接，四个独立看板 Python 输入仅重打包。本次安装件的运行结果与原编译记录各自绑定对应摘要。[同一二进制实测入口](../tests/editor/run_tianshu_ui_package.py) · [构建失效实测](../data-collection/tianshu-board-build-boundary-1404.json)

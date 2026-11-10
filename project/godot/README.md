# Godot 本地安装

此目录是工作区的引擎运行安装位置。源代码仍在仓库根目录；`framework/` 是唯一框架，`gonggong-diting-data/` 是共享文件数据目录。

- `bin/`：当前 GongGong 定制编辑器，AI 聊天在每次模型调用前经过框架准入及数据回执检查。
- `installed.local.json`：安装脚本生成的相对路径与可执行文件 SHA256 清单。

Git 工作区的普通 Windows 启动器（包括 `tools/launch_latest_editor.ps1`、桌面快捷方式和根目录的 .NET 示例入口）共用主检出目录的安装，位置按 Git common directory 解析。启动前校验安装清单中的编辑器、控制台和天枢包摘要。原有 v1 清单需重新安装。

安装时主检出 HEAD 须与远端 main 一致。本地构建请从该提交的干净工作树运行构建脚本，再以 `-BuildDirectory <构建输出>` 安装，或通过 `tools/install_gonggong_editor.ps1 -ActionsRun <运行编号>` 安装该提交的成功 Windows Actions 产物。安装器核验来源与摘要并整体替换。候选工作树的 bin 用于开发验证。标准构建禁用 Mono，C# 示例的脚本执行需要具备 Mono 支持的编辑器。

二进制和本地安装清单不进入源码 Git。新检出仓库后，执行 `tools/build_gonggong_editor.ps1 -Python <构建Python路径>`，然后执行 `tools/install_gonggong_editor.ps1`，即可生成此目录的可运行内容。构建需符合仓库 Windows 构建依赖；构建 Python 需安装 SCons，并支持 zstd。

也可下载同仓库 [完整 Release 工作区](../../distribution/README.md)，其中已包含此安装目录、标准运行时和对应提交的全部源码。大型二进制以 Release 资产分发，源码与发布索引仍由 Git 管理。

从任意当前目录运行 `tools/launch_gonggong_editor.ps1 -Python <Python路径> -Node <Node路径>`，默认打开仓库内 `samples/gonggong-workbench`。引擎根据可执行文件的祖先目录定位工作区，不依赖原安装盘符或 IDE。也可在 GongGong 面板配置其他工作区和 Python。

可运行 `python tools/install_gonggong_runtimes.py --python-home <已有Python安装目录> --node <node.exe路径> --git-home <含cmd/git.exe的Git目录>`，将标准 Python、Node 和 Git 部署到 `project/runtime/`；不复制 IDE 的第三方 Python 包或用户账户目录。部署后直接运行启动脚本即可，不需 Python/Node 参数或 IDE 环境；直接启动编辑器也会发现工作区 Python。运行时文件只保存在本机，由相对路径清单校验，不随源码 Git 分发。省略 `--git-home` 时需保证 Git 在系统 PATH 内；Diting 文件校验需要 Git。

GongGong 面板的“诊断生产聊天阻断原因”分别显示候选校验、正式准入、各 Agent 通行证与谛听数据结果。检查通过不能替代实际宿主权限、模型凭据及聊天回执。

# Godot 本地安装

此目录是工作区的引擎运行安装位置。源代码仍在仓库根目录；`Olympus/` 是唯一框架，`olympus-hermes-data/` 是共享文件数据目录。

- `bin/`：当前 Olympus 定制编辑器，AI 聊天在每次模型调用前经过框架准入及数据回执检查。
- `versions/godot-4.7.2/`：从本机迁移的原始独立安装，保留回退用途；原版不含定制 Olympus 面板。
- `installed.local.json`：安装脚本生成的相对路径与可执行文件 SHA256 清单。

二进制和本地安装清单不进入源码 Git。新检出仓库后，执行 `tools/build_olympus_editor.ps1 -Python <构建Python路径>`，然后执行 `tools/install_olympus_editor.ps1`，即可生成此目录的可运行内容。构建需符合仓库 Windows 构建依赖；构建 Python 需安装 SCons，并支持 zstd。

从任意当前目录运行 `tools/launch_olympus_editor.ps1 -Python <Python路径> -Node <Node路径>`，默认打开仓库内 `samples/olympus-workbench`。引擎根据可执行文件的祖先目录定位工作区，不依赖原安装盘符或 IDE。也可在 Olympus 面板配置其他工作区和 Python。

可运行 `python tools/install_olympus_runtimes.py --python-home <已有Python安装目录> --node <node.exe路径> --git-home <含cmd/git.exe的Git目录>`，将标准 Python、Node 和 Git 部署到 `project/runtime/`；不复制 IDE 的第三方 Python 包或用户账户目录。部署后直接运行启动脚本即可，不需 Python/Node 参数或 IDE 环境；直接启动编辑器也会发现工作区 Python。运行时文件只保存在本机，由相对路径清单校验，不随源码 Git 分发。省略 `--git-home` 时需保证 Git 在系统 PATH 内；Hermes 文件校验需要 Git。

Olympus 面板的“诊断生产聊天阻断原因”分别显示候选校验、正式准入、各 Agent 通行证与赫尔墨斯数据结果。检查通过不能替代实际宿主权限、模型凭据及聊天回执。

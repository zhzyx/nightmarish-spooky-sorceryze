# 共工 Windows 完整交付

本包包含唯一当前 `framework/`、Godot 源码、共工 Windows x64 编辑器、Git/Godot/CLI/采集子模块、示例、Python/Node/Git、固定版本 CLI 依赖和同版本 Git Bash，以及原始 Godot 4.7.2 回退安装。无需外部共工来源；不含本机凭据。模型验收仅使用模拟服务。

[发布页面及摘要清单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/releases/tag/gonggong-windows-x64-20261104-r2) · [下载完整 ZIP](https://github.com/zhzyx/nightmarish-spooky-sorceryze/releases/download/gonggong-windows-x64-20261104-r2/gonggong-windows-x64-20261104-r2.zip)。清单绑定源码提交、构建输入、可执行文件和逐文件摘要；旧发布继续保留。

1. 下载后按发布页面的 SHA256 核验，再解压到新的目录。
2. 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File tools/initialize_downloaded_workspace.ps1`，建立包内源码快照；已有仓库保留。完整 Git 历史保存在原远端仓库，ZIP 不含账号或 `.git`。
3. 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File tools/launch_gonggong_editor.ps1`，启动共工示例与编辑器。此参数只作用于该启动进程。
4. GitHub 操作使用用户自行登录的 GitHub CLI；模型服务使用用户自己的配置。新数据写入 `gonggong-diting-data/`，历史来源只读。

独立复核已验证所有原有子模块实现、52 项 CLI 测试及二进制仅修改只读诊断路径。最终包验收及远端回读证据在发布索引中；模拟服务结果不代表真实模型供应商验收。C# 示例需要额外 .NET 版 Godot 与 SDK，本包不扩展该范围。

---

以下为不可改写的旧发布说明，仅适用于各自历史包。



# 完整 Windows 工作区交付

源码、框架、业务内容、文档和真实任务数据在当前 Git 仓库。仓库 Releases 提供完整工作区 ZIP，额外包含定制编辑器、标准 Python/Node/Git 和原始 Godot 4.7.2 回退安装。逐文件清单与归属在包内 `bundle-manifest.json`；包摘要与下载链接记录在本目录的发布索引。

历史发布：[2026-11-02 完整 Windows 工作区](https://github.com/zhzyx/nightmarish-spooky-sorceryze/releases/tag/olympus-windows-x64-20261102) · [下载 ZIP](https://github.com/zhzyx/nightmarish-spooky-sorceryze/releases/download/olympus-windows-x64-20261102/olympus-windows-x64-20261102.zip) · [发布索引](releases/olympus-windows-x64-20261102.json) · [解包验收](verification-full-package-20261102.json)。ZIP 为 346,102,303 字节，SHA256 为 `e2602af05e17be6328410b0c5d97f96b820acf44e7ea21b2bcf48dc19dfdae3b`。

包内源码固定为 `6a817ff0e6b5bc8f2621985ec8707792abe125bb`；发布后的索引、工单关闭回执和文档澄清随后提交到 main，不改变已经验收的可执行内容。

1. 下载发布索引指定的 ZIP，核对 SHA256，解压到新的目录。
2. 执行 `tools/initialize_downloaded_workspace.ps1`，为源码 ZIP 创建本地 Git 快照；已有 Git 检出会保留。源码原提交与树记录在清单中，ZIP 不复制 `.git` 历史、账户或凭据。
3. 运行 `tools/launch_olympus_editor.ps1`，默认启动可运行的 `samples/olympus-workbench`。
4. Olympus 正式调用仍需配置有效的共工来源，示例见根目录 `.olympus-local.example.json`。上游本体不包含在当前发布。模型验收范围按用户指示为模拟服务；不捆绑模型账户。

`project/godot/bin` 是定制引擎；`project/godot/versions/godot-4.7.2` 是未修改原版；`project/runtime` 是校验过的运行时。C# 示例源码已包含，运行另需 .NET 版 Godot 和 SDK，本包默认编辑器不是 .NET 版。

定制编辑器是明确标识的发布派生版本：仅在精确偏移白名单中，将只读诊断字符串的本机源路径前缀等长替换为有效相对前缀。没有重新编译或改动执行节；原件与派生产物分别记录摘要，回归测试针对派生版本。策略与工具位于 `integrations/godot/release-editor-path-policy.json` 和 `tools/prepare_release_editor.py`。

构建生成代码、重复旧构建、缓存、本机配置和临时测试目录不构成第二套交付源。全部当前源码均由 Git 跟踪，可根据构建入口重新生成。运行时保留原有许可证，Node 完整版本许可证在 `distribution/notices/`；Godot 版权与许可证见仓库根文件及引擎内版权信息，Git 的许可证与依赖许可证位于运行时目录。

发行出处：Python 3.12.14、[Node 24.22.1](https://nodejs.org/en/download/archive/v24.22.1)、[Git for Windows 2.53.0(3)](https://github.com/git-for-windows/git/releases/tag/v2.53.0.windows.3)。Git 对应源码位于同一上游发布标签；所有第三方运行时按原始内容分发，路径清理仅作用于本项目无签名的定制引擎。

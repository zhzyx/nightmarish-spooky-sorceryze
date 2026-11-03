# 共工 + Godot 工作区

共工唯一当前框架由 CURRENT_FRAMEWORK.json 定位到 framework/。仓库包含完整当前框架、Godot 源码、Git/Godot 接入、示例及采集工具。已取消 Olympus 派生框架和外部共工同步依赖，历史原件保留用于追溯。

使用 `powershell -NoProfile -ExecutionPolicy Bypass -File tools/launch_gonggong_editor.ps1` 启动编辑器（仅对该进程允许脚本，不修改系统策略）。接入见 integrations/godot/README.md；完整 Windows 包和逐文件摘要见 [发布页面](https://github.com/zhzyx/nightmarish-spooky-sorceryze/releases/tag/gonggong-windows-x64-20261104-r2)。五个当前 Agent 定义均绑定本次独立审查及用户批准，宿主仍须核验具体操作授权。

当前事件写入 gonggong-diting-data/；历史 olympus-hermes-data/ 只读，来源与回执放 data-collection/。工单使用 GitHub Issue。模型验证范围为模拟服务，不包含模型账号。

下面保留 Godot 原项目说明和许可证。

<p align="center">
  <a href="https://godotengine.org">
    <img src="misc/logo/logo_outlined.svg" width="400" alt="Godot Engine logo">
  </a>
</p>

## 2D and 3D cross-platform game engine

**[Godot Engine](https://godotengine.org) is a feature-packed, cross-platform
game engine to create 2D and 3D games from a unified interface.** It provides a
comprehensive set of [common tools](https://godotengine.org/features), so that
users can focus on making games without having to reinvent the wheel. Games can
be exported with one click to a number of platforms, including the major desktop
platforms (Linux, macOS, Windows), mobile platforms (Android, iOS), as well as
Web-based platforms and [consoles](https://godotengine.org/consoles).

## Free, open source and community-driven

Godot is completely free and open source under the very permissive [MIT license](https://godotengine.org/license).
No strings attached, no royalties, nothing. The users' games are theirs, down
to the last line of engine code. Godot's development is fully independent and
community-driven, empowering users to help shape their engine to match their
expectations. It is supported by the [Godot Foundation](https://godot.foundation/)
not-for-profit.

Before being open sourced in [February 2014](https://github.com/godotengine/godot/commit/0b806ee0fc9097fa7bda7ac0109191c9c5e0a1ac),
Godot had been developed by [Juan Linietsky](https://github.com/reduz) and
[Ariel Manzur](https://github.com/punto-) for several years as an in-house
engine, used to publish several work-for-hire titles.

![Screenshot of a 3D scene in the Godot Engine editor](https://raw.githubusercontent.com/godotengine/godot-design/master/screenshots/editor_tps_demo_1920x1080.jpg)

## Getting the engine

### Binary downloads

Official binaries for the Godot editor and the export templates can be found
[on the Godot website](https://godotengine.org/download).

### Compiling from source

[See the official docs](https://docs.godotengine.org/en/latest/engine_details/development/compiling)
for compilation instructions for every supported platform.

## Community and contributing

Godot is not only an engine but an ever-growing community of users and engine
developers. The main community channels are listed [on the homepage](https://godotengine.org/community).

The best way to get in touch with the core engine developers is to join the
[Godot Contributors Chat](https://chat.godotengine.org).

To get started contributing to the project, see the [contributing guide](CONTRIBUTING.md).
This document also includes guidelines for reporting bugs.

## Documentation and demos

The official documentation is hosted on [Read the Docs](https://docs.godotengine.org).
It is maintained by the Godot community in its own [GitHub repository](https://github.com/godotengine/godot-docs).

The [class reference](https://docs.godotengine.org/en/latest/classes/)
is also accessible from the Godot editor.

We also maintain official demos in their own [GitHub repository](https://github.com/godotengine/godot-demo-projects)
as well as the [Asset Store](https://store.godotengine.org/).

There are also a number of other
[learning resources](https://docs.godotengine.org/en/latest/community/tutorials.html)
provided by the community, such as text and video tutorials, demos, etc.
Consult the [community channels](https://godotengine.org/community)
for more information.

[![Code Triagers Badge](https://www.codetriage.com/godotengine/godot/badges/users.svg)](https://www.codetriage.com/godotengine/godot)
[![Translate on Weblate](https://hosted.weblate.org/widgets/godot-engine/-/godot/svg-badge.svg)](https://hosted.weblate.org/engage/godot-engine/?utm_source=widget)

---

# GongGong 工作区

本仓库是共工（GongGong）的工作区。框架以共工为上游，保留共工名称体系；独立的谛听文件数据模块豁免同步覆盖。

| 路径 | 用途 |
| --- | --- |
| `framework/` | 框架、Agent、skill、契约与同步工具 |
| `gonggong-diting-data/` | 需求生产数据，独立命名，必须随需求产出合入 Git |
| `gonggong-workspace.json` | 工作区约定与入口 |
| `work-items.json` / `.github/ISSUE_TEMPLATE/` | GitHub Issue 工单约定及按任务类别预设标签的表单 |
| `design-docs/` | Markdown 需求与设计文档，引用实际 Issue |
| `data-collection/` | 谛听采集交接目录，保留真实事件来源与摘要 |
| `tools/verify_workspace.py` | 全量同步检查与文件数据 Git 检查 |
| `framework/modules/sinan/` | 已同步共工登记的事件驱动司南 0.4.0 模块，GongGong 名称为司南 |

当前分发基于有效共工 0.9.0 主线，Sinan 为事件驱动 0.4.0；3 个 Agent、10 个 skill。三个 GongGong 本地定义已获用户对精确摘要的批准，正式来源及本地准入验证通过。实际运行仍由宿主绑定权限及回执；模型流程按用户确认范围完成模拟服务验收。

Python 3.10+、Node.js、Git 可用于本地验证；谛听文件模式无需数据库。仓库初始化数据后，新需求按 `framework/extensions/diting-files/README.md` 生成真实事件。禁止将生产数据放入会随上游重建的 `framework/` 目录。

## 验证与数据分析

将 `GONGGONG_FRAMEWORK_SOURCE` 指向实际共工 `CURRENT_FRAMEWORK.json` 或有效框架根。仓库不提交机器本地源路径。上游缺失或不一致时，框架验证及 Agent 上下文装配会阻断；独立文件数据分析仍可执行。

```powershell
$env:GONGGONG_FRAMEWORK_SOURCE = 'PATH/TO/CURRENT_FRAMEWORK.json'
python tools/verify_workspace.py --require-committed
python framework/extensions/diting-files/diting_files.py analyze --repo . --tenant gonggong-workspace
```

文件数据记录须使用实际 Agent 快照、来源和时间。导入模板前填写真实字段；未知用量保持 null，不能伪造成 0。工具会保留历史版本，校验事件摘要及引用；Git 检查区分已记录、已跟踪、已提交，不能以本地提交冒充远程合并。

## 共工同步

从本仓库当前的 `framework/sync/gonggong_sync.py` 发起同步，生成新的临时框架目录，完成全量验证后按 Git 变更流程替换 `framework/`。不可用共工原件直接覆盖共工目录。同步会逐字节携带现有 `extensions/diting-files/`，遇到上游占用豁免路径时拒绝继续；不得覆盖或删除仓库根 `gonggong-diting-data/`。

完整规则见 `framework/sync/POLICY.md`。本仓库没有常驻同步服务。当前本地定义批准见 `framework/reviews/local-admission/`；它只绑定对应候选，不替代宿主运行授权或后续来源变更复核。


## 完整引擎交付

当前源码、框架、项目、文档、测试和任务数据全部由本仓库跟踪。完整 Windows 发布包在同仓库 Releases，含定制编辑器、Python/Node/Git 运行时和原始 Godot 回退安装；下载及校验方式见 `distribution/README.md`。源码含可运行 `samples/gonggong-workbench`；C# 示例另需 .NET 版引擎和 SDK。模拟模型全流程入口为 `tools/verify_gonggong_flow.py`。

# 共工 + Godot 工作区

[按平台查找共工接入子模块](customizations/platforms/README.md)

## 轻量克隆共工框架与工单资料

查阅框架、设计、谛听事件和来源回执时，可以只下载当前主线的相关目录。在新目录运行以下命令（需要 Git）：

```sh
git clone --depth 1 --single-branch --branch main --filter=blob:none --sparse https://github.com/zhzyx/nightmarish-spooky-sorceryze.git GongGong
git -C GongGong sparse-checkout set framework customizations design-docs data-collection gonggong-diting-data tools
```

需要查阅退役的谛听原始记录时，运行 `git -C GongGong sparse-checkout add olympus-hermes-data`。需要查看完整主线历史或进行工单开发时，依次运行 `git -C GongGong fetch --unshallow origin main` 和 `git -C GongGong sparse-checkout disable`。首次取回省略的内容需要连接远端。[占用实测和历史文件恢复](design-docs/history-storage-20261107.md)

当前版本和准入以 [框架登记表](framework/framework-manifest.json) 及其指向的逐项批准为准。0.10.0 的批准绑定五个 Agent 和工单协调技能；框架发现页开头保留的 0.9.2 字样属于旧版说明。


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

在工程根可用 `scons module-bmp` 单独编译 BMP 模块。按 Git 变更选择目标及 CI 触发范围见[引擎模块编译](design-docs/engine-module-build.md)。

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

本仓库的有效框架由 [CURRENT_FRAMEWORK.json](CURRENT_FRAMEWORK.json) 定位。以下路径均相对仓库根。

| 路径 | 用途 |
| --- | --- |
| `framework/framework-manifest.json` | 当前 Agent、Skill、版本和精确候选准入引用 |
| `customizations/platforms/process-management/yuanheng-local/sinan/` | 司南的事件刷新、依赖判断与派发 |
| `customizations/components/repository-dispatch/` | 协作者取得代码后使用的宿主派发入口 |
| `work-items.json`、`design-docs/` | 真实 Issue 的仓库绑定、需求与验收 |
| `data-collection/`、`gonggong-diting-data/` | 采集来源、回执与实际生产事件 |
| `integrations/gonggong/frozen-distribution.json` | 经独立复核的离线分发文件登记 |

## 工作区自检

在仓库根使用 Python 3.11+、Node.js 和 Git 运行以下命令。第一条先核对当前框架指针，再离线核对分发文件及语法，随后校验框架包、准入文件与谛听数据的 Git 提交状态。第二条汇总当前租户已记录的事件。

```powershell
python tools/verify_workspace.py --require-committed
python customizations/platforms/data-collection/git-files/storage/diting_files.py analyze --repo . --tenant gonggong-workspace
```

更新分发登记时，将变动路径逐项对应到已复核的框架提交和包清单，单独审查登记差异。实际执行由当前宿主核实操作者、工单授权和工作者回执。协作与交付入口见 [AGENTS.md](AGENTS.md)。

谛听事件须记录实际 Agent 快照、来源和时间，未知用量保留为 null。远端交付结果按目标分支回读。

## 完整引擎交付

当前源码、框架、项目、文档、测试和任务数据全部由本仓库跟踪。完整 Windows 发布包在同仓库 Releases，含定制编辑器、Python/Node/Git 运行时和原始 Godot 回退安装；下载及校验方式见 `distribution/README.md`。源码含可运行 `samples/gonggong-workbench`；C# 示例另需 .NET 版引擎和 SDK。模拟模型全流程入口为 `tools/verify_gonggong_flow.py`。

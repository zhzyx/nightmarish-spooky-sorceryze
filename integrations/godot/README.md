# Godot 接入

本目录保存原生编辑器接入代码、可审查增量补丁及验证脚本。Godot 的现有 AI 对话、会话隔离、定时器、自编译、重启恢复和回滚继续使用原实现。新增 `Olympus` 页位于原 AI 工作区第三个标签。

## 使用

在 Olympus 页填写工作区根目录、Python 可执行文件及租户（默认 `olympus-workspace`），然后选择状态、上游核对、数据校验或分析。配置保存于本机 Godot 编辑器设置；也可在首次启动前设置 `OLYMPUS_WORKSPACE`、`OLYMPUS_PYTHON`。桥接工具不复制框架或数据，始终读取该 Git 工作区。

上游核对沿用框架的 `GONGGONG_FRAMEWORK_SOURCE`、`GONGGONG_SINAN_FRAMEWORK_SOURCE`、`GONGGONG_SINAN_IMPLEMENTATION_SOURCE` 环境变量。未配置、缺源或漂移均返回失败。状态读取只展示清单，不证明同步或准入。数据校验和分析可独立执行，无需上游在线。

此入口没有 Agent 启动器。现有 Godot 通用 AI 会话不被重新命名为已获准的 Olympus Agent。以后启用框架 Agent 仍需绑定指纹的独立准入和真实宿主管理。

## 重用与恢复

`install.py --engine ENGINE --backup NEW_BACKUP --apply` 仅合并已知 AI 面板入口，拒绝重复安装和未知钩子。SCsub 已按通配符编译 docks 下的 C++ 文件。安装前在新备份目录保存原文件及合并后文件；`engine.patch` 是本次实际补丁。新增文件为 `editor/docks/olympus_panel.{h,cpp}` 和 `tools/olympus_bridge.py`。

恢复时先核对入口文件未被后续修改，再恢复备份并移除上述三个新增文件，重新编译或使用原二进制备份。不要将旧入口覆盖到后续已编辑的文件上。此操作不涉及 Olympus 框架和数据目录。

## 比对边界与已发现差异

| 对象 | Godot 现状 | Olympus 现状 | 合并处理 |
| --- | --- | --- | --- |
| 编辑器交互 | 已有 AI、定时器和构建恢复 | 无原生编辑器页面 | 增加第三个页面，原入口仅三行增量 |
| 框架与身份 | 通用 AI 会话 | Zeus 治理、三个待准入 Agent | 共用框架位置，明确未启用 |
| 数据 | 项目内 AI 会话历史 | Git 文件事件、租户分析 | 直接调用现有 Hermes 工具，不导入会话历史 |
| 工单模块 | 未发现 Olympus 接入 | Ariadne 0.2.1 | 保留现有版本，不绕过上游全量核验 |
| 有效共工 | 当前司南登记 0.3.1 | 同步器仍处理旧审查格式 | check/build 均阻断，待兼容新版来源后再全量同步 |

Godot 目录无 Git 元数据，无法证明某项代码相对于其原始历史版本的差异。本次对比依据当前文件与内容摘要，补丁相对于本次合并前快照。没有覆盖 Godot 源码树，也没有将引擎源码当作框架上游。

## 验证入口

`python integrations/godot/test_bridge.py` 覆盖缺失进程、未知动作、上游拒绝传播、租户参数和不自动启用 Agent。`smoke.gd` 在实际编辑器中寻找 Olympus 页并点击状态与数据校验，验证子进程桥接及返回状态。测试数据留在忽略的本地缓存中，不作为生产事件。

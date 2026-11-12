## 问题与目标

当前 Godot 分叉需要逐步迁移为独立引擎。改名、换目录或继续包装 Godot API 不能证明独立。本 PR 建立 `next_runtime` 的第一道可执行构建护栏，不实现或宣称已经完成新运行时。

## 改动与候选

- 新增 `tools/engine_next_contract.json`，声明新引擎源码根、Godot 禁止根、系统/第三方依赖边界、禁止 token 和链接输入规则。
- 新增 `tools/check_engine_next_contract.py`，检查直接与传递包含、路径逃逸、未知依赖、Godot 专用构造以及链接清单的路径、文件和 SHA-256。
- 新增 21 项临时目录正反测试，包括真实符号链接和空源码防假通过。
- 新增独立 Windows/macOS CI，在相关路径变化时运行测试与源码审计。
- 新增需求设计、本地验证证据、真实 Diting 请求/验证事件和来源索引。
- 不修改 Godot 编辑器、模板、资源格式、运行逻辑或现有编译入口。回退移除本 PR 新增文件即可。

目标基线：`35e3bbe0fc92a16d17e51556a544a528d87ce4ec`。目标分支：`main`。

## 验证与数据

- macOS 15.3.1 arm64 / Python 3.12.16：21 项测试通过，0 跳过。
- Ruff lint、Ruff format、Python 语法编译、契约 JSON、CI YAML 和 `git diff --check` 通过。
- 当前基线返回 `no_sources`，同时保持 `godot_free_runtime_verified=false`。
- 正式本地 Issue 门禁通过；最终候选由签发入口重新绑定并记录，`module_build_impact=[]`。
- 证据：`data-collection/engine-next-build-contract-verification-20261112.json`；真实事件位于 `gonggong-diting-data/events/gonggong-workspace/engine-next-build-contract-20261112/`。
- 本单为独立 host tool 与 CI 护栏，无框架或 Godot native 实现变更；未把责任者自检描述为独立人工审查。
- PR #900 已合入为 `35e3bbe0fc92a16d17e51556a544a528d87ce4ec`；PR 与 main 的专用 CI、通用 CI 均通过，主线树与已测候选树一致。交付后测试和提交态数据核验通过，见 `data-collection/engine-next-build-contract-delivery-20261112.json`。
- 本次候选只追加设计溯源、交付证据和 request_end 事件，不改变已验收实现。

## 未验证项与交付状态

- 尚无 `next_runtime` 可执行程序、真实链接器生成清单、符号审计或干净环境运行；这些属于后续 M1/M2。
- 原实现交付验收已完成；本收尾 PR 合入后关闭 #882 和排障单 #884，并回读终态。
- 当前执行责任：Kimi Work 会话与已验证协作者 `kaiyunxue`。无模型用量或外部服务用量声明。

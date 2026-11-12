# Engine Next 无 Godot 构建契约

<!-- gonggong-request:engine-next-build-contract-20261112 -->

## 当前结论

- 用户目标：把当前 Godot 源码分叉逐步迭代为纯新引擎；改名、换目录或继续包装 Godot API 不算完成。用户于 2026-11-12 11:21 明确要求继续落实“无 Godot 构建契约”。
- 本次产物：`next_runtime` 的源码范围、禁止依赖、模块边界、链接输入与干净环境验收契约，以及可执行的静态检查、链接清单检查、测试和实测证据。
- 本次不实现新运行时、渲染器、脚本或编辑器，不改变现有 Godot 编辑器、模板、项目格式及运行行为。独立检查器通过不代表整个引擎已经去 Godot。
- 需求 ID：`engine-next-build-contract-20261112`。
- Issue：[#882](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/882)。
- 类别：`type:development`。
- 责任人：当前 Kimi Work 会话；开始、提交、推送、CI、main 回读及已验收工单收尾沿本仓库既有授权连续执行。

## 原始需求与目标

当前仓库包含完整 Godot 源码和项目自有的 Gameplay、AINative 能力。迁移必须建立一个新的、可独立验证的实现边界，而不是把 Godot 类型换成新名称后继续链接原实现。

本次建立第一道工程护栏，回答四个问题：

1. 哪些源码可以进入 `next_runtime`，哪些 Godot 源码和 API 明确禁止？
2. 如何阻止本地头文件、传递包含和兼容宏把 Godot 对象模型重新带入新内核？
3. 如何核对实际链接输入和运行文件，避免“源码看似独立、二进制仍携带 Godot”？
4. 如何区分项目自有算法迁移、独立第三方依赖和 Godot 衍生实现，避免把复制改名声明为全量原创？

## 范围与非目标

### 范围

- 一份版本化、机器可读的构建契约，声明新引擎源码根、公共头根、Godot 禁止根、允许的系统和第三方依赖、禁止的 Godot 专用语言构造以及链接输入规则。
- 一个仅使用 Python 标准库的离线检查器，支持源码扫描和实际构建产物清单核验；不访问网络，不修改引擎源码或构建产物。
- 源码检查覆盖直接与传递本地包含、路径逃逸、未知非系统包含、Godot 专用宏和类型，以及注释/字符串中的误报隔离。
- 链接清单检查覆盖输入路径边界、文件存在性、SHA-256、禁止库和运行文件；清单格式绑定具体目标、对象和库。M2 的真实构建目标必须从实际链接输入生成该清单，不能用人工填写代替链接器证据。
- 独立单元测试和负例，证明干净样例可以通过，Godot 包含、传递包含、专用宏、链接输入及摘要不符会被拒绝。
- 独立的 Windows/macOS CI 工作流，在契约、检查器或新引擎源码变化时运行测试与源码审计，不触发 Godot 引擎编译。
- 本设计、验证命令和实际验证回执。

### 非目标

- 不创建或宣称已经完成 `next_runtime` 可执行程序。
- 不重写或移动 Godot 的 `core/`、`scene/`、`servers/`、`editor/`、`drivers/`、`platform/` 等目录。
- 不迁移 Gameplay 算法，不更换构建系统，不引入新的第三方运行依赖。
- 不承诺源码级干净室审查已经完成；本单只建立来源分类和未来准入要求。
- 不把静态扫描描述为完整的 C++ 语义分析或许可证审计。

## 设计方案

### 目标边界

新引擎使用独立的 `engine_next/` 与后续 `runtime_next/` 源码根。现有 Godot 根目录只服务 legacy 宿主，不能成为新目标的本地包含或链接输入。Godot 兼容适配器只能进入 legacy 目标。

新内核公共接口不得暴露 Godot 类型。项目自有玩法与工作流规则可以在去掉 Godot 类型后迁移；通用能力优先使用标准 C++ 或具有独立来源的第三方库；Godot 原有子系统必须按新契约重新实现，任何实际保留的衍生代码继续保留许可与来源记录。

### 源码门禁

检查器从新引擎源文件出发解析 C/C++ 包含指令，拒绝 Godot 根、绝对路径、逃逸源码根的路径、未声明的仓库外依赖和未知非系统包含。本地包含递归检查，防止经由自有包装头间接引入 Godot。扫描代码 token 时去除注释和字符串字面量，禁止 `GDCLASS`、`GDVIRTUAL`、`Variant`、`ObjectID`、`RefCounted` 等 Godot 专用构造；该规则只是补充护栏，不代替包含和链接检查。

没有源码时检查器返回明确的 `no_sources`，不得输出“已验证无 Godot 运行时”。后续 M1 必须使用 `--require-sources`，M2 还必须提供真实链接清单。

### 链接与运行门禁

链接清单记录目标、对象、静态/动态库和随包运行文件，并对每个本地文件核对路径与 SHA-256。Godot 对象库、禁止根下的产物及未声明运行文件一律拒绝。系统库和第三方库采用显式允许清单，不根据文件名猜测安全性。

M2 的构建目标需要从实际链接响应或等价构建器记录生成清单，并保留链接器输入证据；本单只实现清单契约和检查器，不虚构尚未发生的链接验证。干净环境运行、无 Godot 符号检查和默认工程无 Godot 格式分别属于 M2、M4、M7 的验收，不由本单提前标记完成。

### 落地文件与执行入口

- `tools/engine_next_contract.json`：唯一机器可读边界；新增第三方依赖、系统库和构建根必须显式修改并审查。
- `tools/check_engine_next_contract.py`：源码与链接清单检查器。
- `tools/test_check_engine_next_contract.py`：临时目录中的正反样例，不触碰真实 Godot 文件。
- `.github/workflows/engine_next_contract.yml`：相关路径变化时在 `windows-latest` 和 `macos-26` 运行同一测试与源码审计。

当前基线命令：

```sh
python3 -m unittest tools.test_check_engine_next_contract -v
python3 tools/check_engine_next_contract.py --repo .
```

M1 增加 `--require-sources`；M2 增加 `--require-link-manifest --link-manifest <实际构建器生成的清单>`。当前没有真实运行时目标，不执行这些未来命令并冒充通过。

### 回退

本单新增独立检查工具、契约、测试、专用 CI 和文档，不接入现有 Godot 编译或发布路径。回退只需移除这些新增文件；旧引擎字节和运行行为不变。

## 依赖及风险

- 目标工具：Python 3.11+ 标准库；实际本机验证平台为 macOS arm64。纯 Python 测试可在 Windows CI 环境复跑，但只有实际运行结果记为已验证。
- C++ 预处理具有条件分支和生成头，本单静态扫描不声称求值所有宏；后续真实构建必须提供实际编译包含和链接证据。
- 链接清单证明清单内文件及摘要符合边界，不单独证明清单由链接器生成；M2 必须补充生成端绑定。
- 禁止通用名称并不能证明原创性，源码来源审查和第三方许可证审查仍按后续实际依赖执行。

## 验收标准

- [x] 机器可读契约明确新引擎源码范围、Godot 禁止根、系统/第三方允许边界、Godot 专用构造和链接输入规则。
- [x] 独立源码样例通过；直接及传递 Godot 包含、路径逃逸、未知包含、专用宏和类型均被拒绝。
- [x] 合法链接清单及摘要通过；Godot 链接输入、越界运行文件、缺失文件和摘要不符均被拒绝。
- [x] 空源码树返回 `no_sources`，`--require-sources` 失败，不产生 vacuous success。
- [x] 所有测试只使用临时目录，不修改现有 Godot 文件；相关单元测试和语法检查通过。
- [x] 设计与实际实现、命令、覆盖范围和未验证事项一致，实际验证证据写入 `data-collection/`。
- [x] 正式工单门禁、提交后 Git 数据核验、精确候选 CI 和 main 回读完成；远端 Issue 按实际验收状态收尾。

## 验证与采集证据

2026-11-12，在基线 `90c17c9770bac3e0ecc4a9d53bbf9e2e15a730fc` 的隔离工作树上完成以下本机验证：

- macOS 15.3.1 arm64、Python 3.12.16：21 项单元测试全部通过，无跳过；覆盖独立源码、直接与传递 Godot 包含、注释/字符串、专用 token、路径逃逸、符号链接、未声明第三方、空源码、合法/非法链接清单和摘要。
- Ruff lint 与 format 检查通过；Python 语法编译、契约 JSON 解析、CI YAML 解析和 `git diff --check` 通过。
- 当前仓库基线返回 `no_sources`，同时明确 `godot_free_runtime_verified=false`；没有真实 `next_runtime`、真实链接清单、符号审计或干净环境运行结果。
- Windows 验证由新增专用 CI 执行，远端结果在取得前保持未知。既有 Godot 编译是否由通用工作流触发不影响本单“不修改 Godot 运行行为”的范围。

实际命令、输入摘要和结果见 `data-collection/engine-next-build-contract-verification-20261112.json`。真实工单绑定事件见 `gonggong-diting-data/events/gonggong-workspace/engine-next-build-contract-20261112/request-882-engine-next-build-contract.json`，来源索引位于 `data-collection/requests/engine-next-build-contract-20261112/`。

## 整合与主线交付回执

- 候选随后无冲突整合到 `979dfe277c6bc8460e9a174a148a6c2bf6f58cf5`，21 项测试、Ruff 和正式门禁再次通过；网络阻塞及恢复证据见 `data-collection/engine-next-build-contract-integration-20261112.json`。
- PR [#900](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/900) 的本地候选为 `1bf68230524ac146cf5dbdac9cb6530ff77952d2`，签发提交为 `9cb6d12cbcc31a81133071e3cea012ee45122736`；专用 Windows/macOS CI、静态检查、工单关联和 Windows 编辑器检查全部通过。
- PR #900 于 2026-11-12T07:16:46Z 合入，远端 `main` 为 `35e3bbe0fc92a16d17e51556a544a528d87ce4ec`，其树与已测候选树 `df4f4213f4ad1b6b5e806052ab59f9be0ebe8da6` 完全一致。
- main 上专用 CI 运行 `43174085538` 和通用 CI 运行 `43174085445` 均成功；交付后 21 项测试、源码基线和提交态数据核验通过。
- 完整交付证据见 `data-collection/engine-next-build-contract-delivery-20261112.json`。本次仅完成构建契约与护栏，不宣称 `next_runtime` 已实现，也不宣称真实链接器、符号和干净环境运行已经验收。

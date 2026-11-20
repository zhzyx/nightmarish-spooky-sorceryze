# 多宝原生执行快照（#1414）

`native_workspace.py` 是既有多宝组件内的 `host_tool`，由可信本机宿主使用 Python 标准库独立执行。输入为已认证组织身份、明确绝对数据库路径、精确模块修订选择、新目录/工作目录与资源限制。不运行 Git、模型、编译器或引擎；普通工具可以自行读取输出目录。JSON CLI 不是认证服务，不能向不可信远端直接开放。`candidate` 与 `received` 均不表示批准、发布或线上完整工作流接入。

## 调用契约

入口（路径以仓库根解析）：

```text
python customizations/components/tianxuan/duobao/native_workspace_cli.py --db <绝对数据库路径> --tenant <组织> materialize
```

标准输入传单个 UTF-8 JSON 对象，标准输出返回 `{"ok":true,"data":...}`；拒绝返回 `ok:false` 并退出 2。数据库父目录须已存在。四种命令输入：

| 命令 | 必需字段 | 可选字段 |
| --- | --- | --- |
| materialize | selected（模块→精确修订）, destination（不存在的绝对目录） | limits |
| collect | selected, workspace（绝对目录） | limits |
| submit | selected, workspace, actor, request_key | limits |
| delta | module, before, after（两个精确修订） | cursor, limits |

例如 `{"selected":{"gameplay":"<64位修订摘要>"},"destination":"D:/authorized/snapshot-1"}`。库方法使用同名参数，首参数为 tenant；`submit` 复用 NativeStore 的稳定请求键协议。相同工作目录/来源/请求键重试返回相同回执，键对应内容改变会拒绝。无变更返回 `unchanged`，不创建提交回执。`collect` CLI 以 Base64 编码新增/修改内容，删除为 null；库直接返回 bytes/null。

## 来源、收集和并发

输出目录按 `<模块>/<对象名>` 布局，根 `.duobao-source.json` 包含组织、精确闭包、候选状态和来源摘要。这是可核对的说明文件，绝不是 authority。每次收集都要求宿主重新传入可信 selected，从不可变存储解析依赖闭包、校验修订和内容；编辑或删除说明文件不会改变提交基线。删除模块目录等价于删除该模块全部对象；未知顶层模块拒绝。空目录没有对象语义。

任意 CLI 的读取集合未知，所有被改模块均提交 `reads=None`。同模块头漂移一律拒绝；未改模块不参与写冲突。依赖保持原修订固定值，包括本批其他模块同时被改时也不自动转换为 `@batch`。该语义表达对旧依赖的修改，不声称发现工具实际读取的新依赖；宿主需按后续验收决定新的组合。跨模块接收由 NativeStore 单事务执行。

宿主必须保证单一责任写入、扫描期间工作目录和数据库不可变来源不被其他进程修改，并隔离未受信任的同机用户。检查拒绝符号链接、Windows reparse/junction、未知文件类型、路径越界、保留设备名、尾空格/点、ADS、大小写冲突和 `~` 短名称；对象名使用 NFC。Windows 仅接受本地盘绝对路径，拒绝 UNC/device namespace。目录祖先也检查链接。此实现没有抵抗恶意同机进程竞态的 OS 沙盒或跨进程锁。

物化先完成来源和资源预检，再向目标同父目录的新临时目录写入；完整写入来源文件后重命名发布。已有目标（包括空目录）拒绝，失败清理当前 stage。突然断电或进程强杀可能遗留隐藏 stage，宿主确认无占用后可删除；它不代表完整快照。原子命名发布不承诺断电持久性。

## 有界上下文

默认和硬上限：128 模块、10,000 文件、20,000 扫描/物化条目、单文件 8 MiB、源/工作文件总量 64 MiB、CLI 请求和单修订元数据 4 MiB。limits 只能降低，必须为正整数；扫描预算包括目录和说明文件。来源闭包总元数据最多 128 × 4 MiB，单次扫描的内容最多 64 MiB。已有 NativeStore API 非流式，本适配器先用 SQLite length 预检再读取原接口。

delta 返回按对象名排序的新增/修改/删除、前后摘要、变化总数、偏移、下一游标和截断标记。未变对象不重复内容。每页默认最多 100 项，项 JSON 累计最多 256 KiB（`page_items` / `page_bytes`）；`item_bytes` 是紧凑 UTF-8 JSON 项字节之和，封套、游标和两个依赖表另计，受两个修订各 4 MiB 元数据上限约束。分页游标绑定组织、模块、前后修订和全部 limits；可重复请求，不可混用输入。游标是确定性分页位置，不是访问凭据。

内容能放入预算时返回 `encoding:utf-8` 或 `encoding:base64`；无效 UTF-8 或含 NUL 按二进制编码，空文件保留空字符串。保守预估 JSON 转义开销后，放不下的内容仅返回摘要与字节数、`content_omitted:true`，`truncated:true`；这类遗漏不会产生内容分片游标。调用者可用原 `NativeStore.read` 按精确 after 修订补读，不得把摘要当完整需求证据。依赖变化在前后依赖表中单独表示，即使对象变化数为零。

## 验证与回退

```text
python -X utf8 -m unittest discover -s customizations/components/tianxuan/duobao -p test_native_workspace.py -v
```

真实临时文件系统、空 PATH 子进程 CLI、普通 Python 修改、重启幂等回读、跨模块原子接收/拒绝、来源篡改、路径/资源拒绝、写失败清理与增量二进制分页测试见该文件。大文本场景保留 100,000 字节未变对象，比较实际增量 JSON 传输字节；不估算 token。Windows junction 与 Linux symlink/FIFO 按平台真实能力留证，不能将跳过解释成通过。记录在仓库相对 `data-collection/duobao-native-workspace-1414.json`，独立审查与 Linux 由父工单收尾。

宿主契约为 NativeStore 的 revision/read/submit 与同库只读长度预检；无需重新编译引擎。回退停止调用这两个新入口，保留权威数据库、有效工作副本和必要来源证据。测试临时数据库与快照由 TemporaryDirectory 清理；没有生产安装、配置或服务改动。

## 工单批准资产的 Godot 导入

使用 `native_workspace_cli.py godot-import` 可从当前工单的批准输入生成可打开的独立 Godot 项目。可信本机宿主设置 `TIANXUAN_PUBLIC_ORIGIN` 指向部署的 HTTPS 服务、`TIANXUAN_TOKEN` 为当前用户身份、`TIANXUAN_GODOT_EXECUTABLE` 指向已安装的编辑器。标准输入仅含工单 ID 和新的绝对目标目录，例如：

```json
{"issue_id":"issue-example","destination":"D:/A8Checks/review-01"}
```

命令从认证服务读取该工单已提交的全部概念图/模型，服务逐一检查当前批准绑定。命令在临时目录以 headless 编辑器导入并检查导入产物，发布新目录前再次读取当前批准集合。待审、退回、撤权、摘要变化、导入失败或目标已存在时拒绝发布。成功的项目是该次消费时的快照；后续受保护的消费要重新执行命令。原有 materialize/collect 等普通快照操作继续沿用各自契约。生产切换由部署责任者安排。

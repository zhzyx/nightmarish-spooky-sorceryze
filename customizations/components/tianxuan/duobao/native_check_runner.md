# 原生实际检查入口

`NativeCheckRunner` 是 `placement=host_tool` 的 Python 宿主接口。本项关联 #1422，设计为 `design-docs/native-check-runner-20261117.md`。它连接已验收的 NativeStore、NativeWorkspace、EvidenceCache、NativeRelease，不启动调度器，不执行外部模型，不提供匿名 HTTP 或任意命令 CLI。

## 实际输入与安装

宿主传入 `EvidenceCache`、已存在的绝对工作根、固定检查注册表、`authorize(tenant, authenticated_actor, check, "execute")` 和 `verify_installation(check, installed_spec)`。两项回调均必需且只有严格 `True` 通过。身份必须来自已认证宿主，不能将不可信请求内 actor 直接视为认证。EvidenceCache 的 record 权限另外验证。调用者只选择检查 ID、精确组合与稳定运行键；不能传入命令、环境或 passed。

注册表每项必须包含 `argv`（绝对可执行文件，禁止 cmd/bat 隐式 shell）、`env`（明确环境，不合并宿主完整环境）、`toolchain`、`environment`（64 位摘要）、`timeout`（0..86400 秒）、`log_bytes`（1..900000 字节）。输入范围和规则版本沿用 EvidenceCache 已安装 policy。宿主验证器负责核验工具链、依赖、环境与指纹真实性；单个 executable 摘要不等同整体环境证明。本实现会在运行前后调用验证器。测试验证器只对应确定性 Python 测试安装，不是生产认证实现。

固定命令参数可使用 `{input}` 和 `{output}` 占位符，同时收到 `DUOBAO_INPUT` 与 `DUOBAO_OUTPUT` 的绝对路径。进程 cwd 固定为该运行的独立 output 目录，通过新增可选 cwd 参数传至 OwnedCommand/Popen；不使用全局 chdir。执行合同版本纳入可信上下文，现有 helper 调用不传 cwd 时仍保持默认继承行为。完整精确组合通过 NativeWorkspace 物化；生成物写入分离 output。即便 policy 声明部分输入，runner context 仍包含完整 candidate，保守避免可访问的其余组合漂移被误复用。上下文也绑定注册表、runner 源码、进程 helper 摘要和 EvidenceCache policy/输入。

可执行路径同样拒绝符号链接与重解析点；安装者应核验规范化后的真实可执行路径。例如 Linux 的 python 别名可能是链接，应登记核验后的 python3.12 实体路径，不由不可信请求临时解析替换。

进程依赖复用 `tools/ainative/owned_process.py`。默认路径相对于本模块的仓库布局根（`Path(__file__).parents[4]`）解析；独立安装可通过 `process_helper_path` 指定已安装 helper 的绝对路径，无需 Git。Windows 还必须携带 `editor_provenance_process.py`：若 helper 位于 `tools/ainative`，在其父 tools 中查找，否则与 helper 同目录。现有 native 模块应处于 Python import 路径。停止入口并保留数据库和工作根即可回退，不切换任何有效生产服务。

## 运行、限制与证据

运行键按 tenant 唯一；actor、candidate、context 或 policy/inputs 变化使用同键会冲突。短事务先占用，子进程、输出等待、输入核查、安装核查都在写事务之外。不同运行键可并发，其他 NativeStore.submit 不等待检查结束。

执行占用同时持久化原始检查绑定。EvidenceCache 构造绑定时复制规则，使读取范围与规则版本来自同一份快照；写回通过可选 expected_binding 核对实际绑定后，只按这份绑定记录。运行期间或写回入口规则变化会拒绝登记，保留 result，不能将旧执行重新标为新规则通过。恢复原规则可幂等补写已持久结果，不重新运行进程；缓存命中也核对原占用绑定。后续规则变化会使旧键失效，消费仍须核对当前规则。

OwnedCommand 在 Windows 将暂停子进程绑定 kill-on-close Job 后恢复；POSIX 用独立 session 与未回收 leader 固定进程组身份，可信命令不得自行逃离 session。超时、取消、超量输出和读取错误终止所有权范围；不确定清理会保留 held，不产生通过事实。不以记录 PID 对重启后的进程盲目信号或重启。检查不是 OS 沙盒；网络、文件访问、生成物磁盘用量未实施系统级隔离，宿主必须只安装可信检查。

退出后读取 NativeWorkspace 实际内容，并核对原输入和 manifest 的内容、mtime/ctime 与有界目录结构。普通写后恢复也会改变时间戳而被拒绝；此检查不能证明恶意代码没有读取目录外文件或恢复所有内容及时间戳。真实退出码、原因、原始日志摘要、有界 base64 transcript 写入 EvidenceCache。原始日志最多 log_bytes；transcript 最多取前 600000 原始字节并明确标记截断，确保 EvidenceCache 总记录小于 1MiB。失败、超时、取消和输入污染只能产生 failed；未知状态不产生 passed。

## 幂等与恢复范围

- `reserved`：已占用，可能尚未启动。重启后也不自动抢占。
- `running`：持久工作目录已记录，进程可能运行或已结束但尚无可靠结果。重复调用只返回记录。
- `held`：启动/清理/其他执行错误，保留目录与逻辑占用，需要当前所有者或有权宿主外部核实。无自动 PID 接管、租期抢占或重试 API。
- `result`：真实终态与日志已持久化；再次调用可以幂等写回 EvidenceCache。覆盖缓存已提交但回执丢失的窗口。
- `complete` / `cached`：历史执行回执或本次缓存命中；同键重放返回历史事实，不重新执行。撤回、过期后的旧回执不等于当前有效检查，消费方必须调用 EvidenceCache/NativeRelease 验证；新真实事件使用新键重试。

崩溃于子进程结束与 result 持久化之间仍保持 running，不声称自动恢复。工作目录全部保留以供证据归档；清理属于宿主在核实终态与归档后的明确操作。unknown/held 不得清理。run 表与证据库必须放在同一个 NativeStore，数据库属于可信宿主存储边界。

## 验证

`py -m unittest discover -s customizations/components/tianxuan/duobao -p test_native_check_runner.py -v` 使用真实本地 Python 子进程验证退出、超时与后代终止、超量输出、输入污染、取消、运行键竞争、独立提交、真实 Windows 控制进程死亡后的重启保留、证据提交后回执丢失恢复、缓存/撤回/环境和输入漂移，以及 distinct producer/runner/reviewer/publisher 的 NativeRelease 测试通道选定。所有身份和通道都是隔离测试，不涉及生产部署或真实模型。

## 既有嵌入 helper 的构建边界

新 runner 为独立 host_tool；此次新增 cwd 参数同时修改既有嵌入资源 `tools/ainative/owned_process.py`。实际消费链为 `editor/SCsub` 的 `#tools/ainative/*.py`（排除 test_）→ `editor/ainative/builders.py:bundle_sources/build_bundle` → `editor/ainative/bundle.gen.h`。Windows helper `tools/editor_provenance_process.py` 由 bundle_sources 加入实际生成依赖。以上路径基准均为仓库根；独立部署则按前述 process_helper_path 解析，不依赖源码工作树。

`test_owned_helper_change_invalidates_generated_bundle` 使用真实生成器在临时目录生成头文件，修改 owned_process 输入后头文件及嵌入摘要改变，恢复原输入后头文件完全恢复。既有 bundle_graph 测试另外核对 editor/SCsub 真实输入图及独立布局的 helper 加载；未声称本次完成引擎二进制重编译或替换。回退新 runner 时停用入口并保留记录；helper 的 cwd=None 默认兼容，嵌入版本若发布须随原有构建与签发入口处理。

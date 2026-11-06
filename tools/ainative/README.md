# AINative 交换契约 v1

本目录是 01-contracts 的可执行起点，使用 Python 3.11+ 标准库；尚未接入 Godot 编辑器或任何生成模型。所有相对路径以仓库根为基准。

运行：

```text
python tools/ainative/contracts.py tools/ainative/example.json
python -m unittest discover -s tools/ainative -p "test_*.py"
```

Artifact 必须含 id、revision、type 和 payload 对象。dependencies 和 context.artifact 使用 {id, revision}；当前交换包必须闭合引用。扩展 type/payload 无损保留，领域插件负责额外校验。revision 是调用方提供的不可变版本标识，内容寻址与存储强制不可变由 02 实现。

context 条目必须有 role、scope、strength（reference/constraint），以及 text 或 artifact 二选一。scope 当前为插件解释的字符串；内核不静默展平上下文。

binding.level 包含 unbound / semantic_mapped / animation_retargeted / target_bound / roundtrip_verified。后四者要求 skeleton_profile 引用；已绑定 garment 另需 character/avatar_profile 作为 fit_target；回读声明需 validation_report 引用。校验器检查声明结构，不能证明几何拟合、蒙皮、目标工具回读确实成功；实际证据内容校验属于各领域验收。

验证报告的 payload.subject 必须为被验证资产的 {id, revision}。binding.evidence 是非生产引用，不加入生产 DAG，因此报告可以通过 dependencies 记录其验证对象而不会形成伪循环。

example.json 全部是合成契约夹具，UE/Mixamo Profile 是占位元数据，没有真实骨架/网格，不可作为兼容实现或真实生成样例。

`extensions.py` 提供可执行的扩展契约：

- `NodeRegistry.register/get`：注册可 JSON 序列化的版本化节点定义；输入、输出端口分别声明 types 和 required；同 id/version 的定义不可替换，读写边界深拷贝。类型名称不设全局白名单，领域扩展可自行声明。
- `validate_invocation(registry, request, manifest, provider)`：检查必需端口、版本引用、类型、参数与上下文能力，返回 SHA-256 调用键。节点定义、完整输入包、Provider/模型版本、参数、带 role/scope/strength 的上下文都参与计算；当前保守包含整个包，因此无关资产变化也可能失效。存储层仍需保证版本不可变。
- 参数 schema 使用明确子集：顶层 properties/required，属性支持 type/enum；type 支持 string/integer/number/boolean/object/array。未知参数和未知 schema 关键词拒绝，object/array 内部仅保证 JSON 值，不宣称完整 JSON Schema。参数不自动填默认值。
- `provider_manifest` 验证 Provider 和模型的固定版本、能力、上下文类型、可用性；`Provider` Protocol 定义 describe/submit/poll/cancel。submit 必须接收 idempotency_key；是否真正保证幂等由具体 Provider 与 #143 执行器验证。凭据不属于序列化定义。
- `validate_job` 检查任务身份、状态转移及终态不可变；queued 可直接观测为 succeeded。只有 succeeded 可带非空 outputs；failed 必须有 error。`validate_outputs` 进一步对照节点端口和输出资产清单验证结果，执行器应在发布前调用两者。
- `PublishAdapter.encode` 是受信任纯编码接口，输入为深拷贝，输出 bytes。`publish_new` 将单文件写入同目录临时文件并以独占硬链接原子发布；目标存在时拒绝，编码/链接失败不会覆盖源文件，临时文件清理。调用方提供存在且受信任的目标目录；不支持硬链接的文件系统报错，不降级为覆盖写入。多文件事务、Godot Resource/Scene 编码及实际发布适配器由 #144 提供。

扩展调用顺序：注册定义 → Provider.describe → validate_invocation → submit/poll/cancel → validate_job/validate_outputs → publish_new。该顺序是 #143 执行器的接口，不代表当前已实现调度、重试或真实生成服务。

单元测试的 Provider 元数据、编码器和 UE/Mixamo 目标请求均为显式合成夹具。#142 的交付是契约及其可执行验证；ArtifactStore、任务持久化和引擎 UI 仍属于后续工单。

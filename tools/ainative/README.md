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

后续接口职责：ArtifactStore 解析版本并存储；NodeRegistry 注册输入输出类型、参数 schema、context 能力；Provider 报告能力及任务生命周期；PublishAdapter 从验证产物生成 Godot 资源。当前仅实现共享 Manifest 验证，不声称上述执行接口已经实现。

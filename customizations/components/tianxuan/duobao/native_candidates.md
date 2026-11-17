# 不可变候选接收（#1451）

路径基准为仓库根。`native_candidates.py` 在既有多宝 host_tool 边界中提供 `NativeCandidates(store, authorize, limits=None)`；当前消费者是 `native_candidates_cli.py` 和确定性测试。未接入 NativeWorker、HTTP、合契或发布选择；这些由父 #1444 继续。实际 SCons 图核对新增四个宿主文件与原生输入零交集后，已登记到 `tools/native_host_inputs.json`；证据见 `data-collection/native-candidate-host-boundary-1451.json`，不据此声称渲染性能收益。

`receive(tenant, actor, request_key, changes, origin)` 保留每项显式 base、reads、edits、dependencies。base 可以为 null（独立初始候选），即使模块已有 head；非 null 必须是本租户/模块可用的精确修订。`origin` 精确包含 source_ref、worker_ref、issue_url 三个非空字符串。所有身份及来源由可信宿主绑定，不从工作副本自证。authorize(db, tenant, actor, module, action) 对 receive/read 必须严格返回 True；回调只执行短、本地操作，可使用当前事务核对可变授权。依赖读取也检查权限。

接收以原始 base 为 parent，保留未知 reads=null，始终返回 requires_final_composition_validation=true。它不是无冲突证明、独立审查、可发布判断或业务验收。下游必须对最终组合做真实语义核查；不能仅因存储成功就发布候选。返回的 revisions 可传给既有 compose/read/NativeWorkspace.materialize。

候选回执单独存入 native_candidate_receipts，以 tenant/actor/request_key 幂等。相同请求重放原回执，不同输入重用键拒绝；来源参与请求摘要。不同 actor 即使内容相同也有独立 id 和回执，内容修订去重。`receipt(tenant, actor, request_key)` 重启后回读本人空间回执，仍检查当前权限。SQLite 事务一次保存对象、修订和回执；失败全部回滚。不写 native_heads、native_receipts、发布表或生产频道。原 submit 的未知读取漂移拒绝没有改变。

限制复用 NativeWorkspace.Limits：128 模块、10000 文件/编辑/读取名、20000 目录项、单文件 8 MiB、总内容 64 MiB、修订/请求元数据 4 MiB；宿主只能降低。源基线和最终依赖闭包均验证摘要、便携路径、大小写/前缀冲突和预算。CLI 总 JSON 输入另限 4 MiB（含 Base64），因此 CLI 可接收的内容小于库的 64 MiB 上限。内部 @batch 依赖有界且拒绝缺失、循环。数据库位于可信本机宿主边界，不是恶意本机进程沙盒。

```text
python customizations/components/tianxuan/duobao/native_candidates_cli.py --db D:/authorized/native.sqlite --tenant team --actor worker --request-key task-1 receive --input changes.json --source-ref frozen-input --worker-ref process-1 --issue-url https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1451
python customizations/components/tianxuan/duobao/native_candidates_cli.py --db D:/authorized/native.sqlite --tenant team --actor worker --request-key task-1 receipt
```

CLI 是有权访问本地数据库的 OS 操作者入口，参数不是外部认证协议。服务消费者必须改用库并绑定认证身份和授权回调。changes.json 格式沿用 native_cli 的变更数组，edits 值为 Base64 或 null，reads 必须显式提供。

回退停用新增入口，保留全部对象、候选修订与回执；旧 NativeStore 可继续读写。实测在新增表存在时回退旧接口仍成功读 base 并 submit，未改变既有数据格式。无引擎二进制或有效服务切换。证据见 `data-collection/native-candidate-intake-1451.json`；本机 Windows 回归不能代替父责任者的 Linux 验证、独立审查和源码交付。

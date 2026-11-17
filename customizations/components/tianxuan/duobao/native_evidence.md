# 原生检查证据缓存

`native_evidence.py` 的 `EvidenceCache` 供可信宿主调用，复用 `NativeStore` 的组织、精确组合和 SQLite 持久存储。它返回检查事实，不签发独立批准或发布。当前未挂载线上 HTTP 路由，模型不能通过提交一个 `passed` 字段获得发布权。

宿主构造缓存时安装检查策略，并提供 `authorize(tenant, actor, check_id, operation)`；必须在对应组织对实际检查执行者返回严格的 `True` 才能写证据，`operation` 为 `record` 或 `revoke`。身份、策略来源及执行者权限由宿主验证，字符串不是身份凭证。记录者传入真实运行日志；本库不执行检查，也不能仅凭日志证明外部运行真实发生。上层仍须绑定实际执行回执与独立审查责任。

每个策略包含 `version`、`reads`、`max_age_seconds`。例如读取 `gameplay` 模块 `rules.json` 与尚不存在的 `extension.json`：

```python
policies = {
    "rules-validation": {
        "version": "v1",
        "reads": {"gameplay": ["rules.json", "extension.json"]},
        "max_age_seconds": 3600,
    }
}
```

`reads` 为 `None` 时绑定完整组合；某模块的值为 `None` 时绑定该模块完整修订。已知对象范围必须由宿主保证完整，不能把模型自行声明当作工具访问隔离或依赖采集证明。参数、工具链与环境分别绑定 JSON 和精确 SHA256；规范、范围、依赖或实际输入变化会改变键。对象范围检查不绑定无关模块或同模块其他对象的修订变化，因此能复用原证据。整体组合检查仍使用自己的完整范围。

正常调用依次为 `binding(...)` 确认输入、由宿主执行检查、`record(...)` 写实际结果；后续 `lookup(...)` 返回 `cached_check_fact` 或 `None`。回执同时保留原受测组合与本次请求组合，避免把复用误写成又执行了一次。`failed`、`unknown`、过期、撤回、执行者权限撤销的最新证据均不返回通过；不会回退寻找更早的绿色结果。`revoke(...)` 追加幂等撤回记录，不改写原证据。读取校验源对象、精确依赖、证据及日志完整性。

数据库路径由原生存储构造参数明确指定。策略、工具链/环境摘要及日志均为可信宿主输入；没有生产默认授权器。日志限 1 MiB，参数限 64 KiB。短事务只保存结果，不包住模型、编译或检查执行。回退为停用此缓存，保留数据库和原始检查证据。

路径以仓库根为基准，验证入口：

```text
py -B -X utf8 -m unittest discover -s customizations/components/tianxuan/duobao -p test_native_evidence.py -v
```

覆盖不相交对象复用、真实读取/缺失/依赖/规范/环境变化、保守未知范围、租户隔离、幂等并发、事务失败、损坏及撤回。此测试不代表线上 API 接线、可信读集合自动捕获、生产发布或实际 token 收益。

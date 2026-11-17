# 原生独立审查与内容选定

`native_release.py` 是 `placement=host_tool` 的可信宿主 Python 库，依赖同目录的
`NativeStore` 和 `EvidenceCache`，运行不需要 Git、网络、外部进程或模型。
SQLite 路径沿用 `NativeStore` 的显式绝对路径；逻辑模块名称不解析为宿主路径。
本模块新增独立表，不改变既有存储和证据表的语义。

## 宿主接口与信任边界

构造 `NativeRelease(cache, authorize, contributors)` 时必须显式提供两个回调：

- `authorize(db, tenant, actor, scope, action) -> bool`：在已认证会话中取得 actor，
  验证租户、产品和操作权限。产品 scope 的 action 为 `configure`、`approve`、
  `revoke`、`publish`、`read`；检查 ID scope 的 action 为 `evidence:record`。
  后者与原 `EvidenceCache.authorize` 都必须允许，避免旧缓存实例绕过宿主撤权。
- `contributors(db, tenant, candidate) -> set[str] | None`：从宿主已核实的来源记录，
  返回完整组合的全部贡献者。不得使用提交者自报名单；未知、空集合、自审拒绝。
  来源集合变化后旧批准失效，需重新独立审查。

回调必须是本地、有限时、无网络／编译／模型／外部进程的判断。所有可变授权和
贡献来源必须读取所给 `db` 的同一事务，更新使用同一数据库写事务；不可另开连接
读取其他快照。原证据授权回调亦必须保持本地、不产生外部工作。宿主可在请求前
采集远端事实，但必须明确其快照有效性，不能把进程外权限变动宣称为本库的原子保障。
宿主提供的检查注册表及回调实现须作为固定安装版本，禁止在正在执行的操作中
并发修改 Python 对象；产品政策变更使用 `configure`，由 SQLite 排序。

本库不鉴别传入 actor 字符串的真实身份，不维护远端身份连接，不防御能任意修改
SQLite 并重算所有摘要的恶意数据库管理员。摘要检查用于发现损坏和错误关联，
不是数字签名。宿主负责凭据、数据库访问控制、来源真实性和可靠时钟。

## 使用顺序

以下变量必须来自可信宿主接线；没有默认放行授权器或默认审查人。

```python
release = NativeRelease(cache, host_authorize, verified_contributors)
context = {"toolchain": toolchain_digest, "environment": environment_digest,
           "parameters": {"mode": "release"}}
release.configure(tenant, authenticated_admin, product, {
    "checks": {"composition-test": context},
    "review_max_age_seconds": 3600,
})
# cache 的 composition-test 必须预先安装 reads=None 的完整组合检查规范。
# 实际检查在写事务之外完成；runner 接收的日志必须是真实执行结果。
fact = cache.record(tenant, authenticated_runner, run_key, candidate_id,
                    "composition-test", **context, outcome="passed", log=runner_log)
review = release.approve(tenant, authenticated_reviewer, review_key, product,
                         candidate_id, {"composition-test": fact["id"]}, review_notes)
receipt = release.publish(tenant, authenticated_publisher, publish_key, product,
                          channel, review["id"], expected_previous_receipt_id)
current = release.selected(tenant, authenticated_reader, product, channel)
page = release.events(tenant, authenticated_reader, product, after=0, limit=100)
# 每项含 sequence 和不可变 record；下次以最后的 sequence 继续读取。
```

`expected_previous_receipt_id=None` 只允许创建尚无选定内容的通道。后续操作必须传入
该通道当前回执 ID，而不是候选 ID。每组织／产品／通道独立比较；不同通道没有
全局追赶要求。SQLite 仍将数据库写入短暂串行化，这不是无限并发吞吐承诺。

`configure` 只接受宿主安装的检查 ID 和精确工具链／环境／参数，且至少有一个
`reads=None` 检查；规范摘要同时绑定全部必需检查的安装规范。批准绑定候选、
全部证据 ID、规范摘要、审查记录、独立身份与已核实的贡献来源。
失败、未知、最新证据替换、过期、撤回、权限撤销、损坏及政策漂移均拒绝放行。

批准、批准撤回、发布均有稳定请求键，范围是租户和 actor。相同请求重试返回
原回执，异内容同键报 `Conflict`。返回旧回执仅说明此前操作已记录；尤其发布
重试不会重新选择旧内容，也不会把已失效批准恢复为有效。消费者须调用
`selected` 检查当前可用性，不能把历史回执当作当前授权。

## 原子性与撤回

批准和发布在 `BEGIN IMMEDIATE` 内读取当前产品政策、真实身份授权、贡献来源、
批准撤回、最新证据、证据撤回、期限和内容摘要。内部只读事务适配器让
`EvidenceCache.binding/lookup` 使用同一连接，不在验证与指针提交之间开独立快照。
清单记录、请求回执、通道指针和事件在同一事务提交，失败全部回滚。

证据撤回或新失败先提交时发布拒绝；发布先提交时保留历史事件，后续撤回使
`selected` 拒绝返回当前有效选定。读取仅代表该事务观察时有效，不提供跨事务
消费租约。未来的安装／消费流程必须建立自己的真实接收和执行回执。
`selected` 和 `events` 使用同一只读快照核对状态，不申请写锁，允许其他通道
在读取期间发布。`events` 按租户／产品索引读取持久历史，使用递增游标和
1–1000 条的页上限；不声称外部消费者已读取，也不自动重新投递。

回退调用同一个 `publish`，选定旧组合的仍有效独立批准，并使用当前通道回执
作为 expected。已撤回或过期的批准不能用于回退；必要时先补充有效检查与新审查。
历史记录保留，回退产生新的内容选定记录。

## 验证与停用

从仓库根运行：

```powershell
py -X utf8 -m unittest discover -s customizations/components/tianxuan/duobao -p test_native*.py -v
py -m ruff check customizations/components/tianxuan/duobao/native_release.py customizations/components/tianxuan/duobao/test_native_release.py
py -m mypy --follow-imports=silent customizations/components/tianxuan/duobao/native_release.py customizations/components/tianxuan/duobao/test_native_release.py
```

测试覆盖双向确定性撤回竞争、同通道 CAS、多模块闭包、通道与租户隔离、故障
注入事务回滚、重启、损坏、撤权、政策漂移、幂等和重新审查后的回退。
无需原生二进制重建；以同一 Python 宿主加载或停用本模块。回退方式是停止调用
新发布入口并保留数据库和历史，不切换任何生产安装，不删除已交付数据。
这是可信宿主库验收；线上身份接线、安装、消费确认属于后续 P0-D，不在 #1409
声明为已完成。

# G05　导入并回查 Git 标签

多宝从 G03 导入的 `history.bundle` 读取标签。导入时，归档层逐项核对镜像、采集报告和 bundle 的引用，随后将原始 bundle 发布至指定租户和项目。G05 为该目录新增两个只读查询，已有 G03 目录也能直接查询，无需再次采集或发布。[G05 工单 #1823](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1823) · [G03 导入与发布](gonggong-ai-workbench-g03.md)

## 核对引用和原始对象

1. 带上项目和发布回执中的 `revision`，请求 `GET /api/v1/migration/history/tags`。AI 使用 `migration.history.tags` 和相同参数。列表按完整引用名排序，`limit` 为 1 至 100，传入返回的 `next_offset` 可继续翻页。
2. 每行的 `ref` 为完整的 `refs/tags/…` 引用，`oid` 为引用直接指向的原始 Git OID。轻量标签的 `kind` 为 `lightweight`，`target_oid` 即 `oid`。附注标签的 `kind` 为 `annotated`，`oid` 标识附注原件，`target_oid` 和 `target_type` 来自该对象头。两类标签均返回递归解引用后的 `peeled_oid` 和 `peeled_type`。当附注指向另一层标签时，直接目标与最终目标可分别核对。
3. 以完整附注对象 `oid` 请求 `GET /api/v1/migration/history/tag_object` 或 `migration.history.tag_object`。默认从字节 0 开始，后续请求将 `next_offset` 作为 `byte_offset`。依次解码各页的 Base64 `data` 并拼接，得到 Git 的原始 tag 内容，含原始对象头、说明和签名字节。最后一页的 `next_offset` 为 null。可用同一对象格式仓库中的 `git hash-object -t tag --stdin` 核对 OID。验证签名时应使用接收方认可的签名公钥。

这两个查询沿用历史入口的身份、项目及修订检查。运行输入为原生目录中已核验的 Git bundle，Git 在隔离镜像中执行只读对象查询。该适配使用现有迁移服务的 Python 和 Git 运行环境；回退服务代码即可恢复上版历史接口，原目录及标签仍可从其 bundle 恢复。[Git 读取实现](../customizations/components/tianxuan/migration/history_git.py) · [HTTP 与 AI 入口](../customizations/components/tianxuan/server/migration_history_api.py)

## 验收实录

定向用例生成一次性 Ed25519 测试密钥，对一个大于 48 KiB 的附注执行 SSH 签名，并以测试公钥在源仓通过 `git verify-tag`。同一快照含轻量 blob 标签和指向已签名标签的外层附注。G03 将快照发布至隔离项目，移开源仓与采集目录后，HTTP 和 AI 仍可分页回查各标签及签名对象。恢复的字节与源对象逐字节相等，按 Git 的 tag 对象头计算的 SHA-1 也等于源 OID。用例同时覆盖错误对象类型、偏移越界、租户隔离及失效修订。[定向测试](../customizations/components/tianxuan/server/test_migration_tags.py)

回执保存实际目标修订、采集的引用、目标映射、两端摘要、测试用签名公钥和本次微型 bundle。独立复验时，将 `source_bundle_base64` 解码为文件，将 `allowed_signer` 写入 allowed-signers 文本，在隔离目录克隆该 bundle，并以 `git -c gpg.ssh.allowedSignersFile=<文件绝对路径> verify-tag <verified_signed_oid>` 复核签名。G07 可按上述两个入口取数，将源引用、附注直接目标和最终目标分别纳入其完整性报告。[源样本与目标接收回执](../data-collection/gonggong-ai-workbench-plan1-g05.json) · [后继 G07 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)

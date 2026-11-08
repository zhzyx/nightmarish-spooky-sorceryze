# 修复同步目录中的原生应用激活入口

<!-- gonggong-request:native-activation-staging-metadata-20261108 -->

原用户授权发现流程故障后修复并交付；父宿主在原生 #483 实际 activation_pending 后明确委派本单。关联 #483、#462、#393、#390。本单只拥有新的隔离工作树和实际工作者身份，不复用483 owner、源码候选、绑定或运行窗口。

## 已发生的故障

#483 的 PR567 已真实进入 main，固定收尾 worker 完成工单关闭，但复制已签原生 App 到 Documents 下绑定入口的自有 staging 后，严格签名校验报 `resource fork, Finder information, or similar detritus not allowed`，返回 completion_verified=true、ok=false、activation_pending。原有效入口未被替换；source store 的签名包仍有效。

后续私有实测证实：即使只删除这两种属性，发布到 Documents 后约一秒 FileProvider 仍会重新附加 FinderInfo，严格签名再次失败。因此单次清理不能作为修复。原失败记录保留；父宿主明确批准下述完整密封副本与登记链接方案。

## 实施范围

- 新增显式 `--entry-type managed_native_app_link`：逻辑启动位置仍是原绑定 App，完整已签包复制到真实 OS 用户的非同步 `Library/Application Support/gonggong/engine-launch-payloads/<完整上下文摘要>/Engine.app`，再以事务替换逻辑链接。普通入口默认仍整包复制，不自动变更类型。
- 上下文绑定原 manifest 全字节摘要、sourceDigest、验收 C、签发 S、tree、sourceRoot、Issue/request/owner 和逻辑入口；已发表安装副本永不覆盖或删除。下一候选创建新的副本，旧副本和原入口备份保留。
- 源 App、manifest、私有 binding、locator、签名字节与 CodeResources 不变，不重签、不清属性、不放宽 strict、source inputs 或 Issue/main 条件。全部常规文件字节、模式及 custom attrs 精确；ditto 明确保留 quarantine，但允许系统复制自然规范化，仅记录实际存在/摘要差异，不解释标志位、不手动修改。
- 只接受私有回执登记的绝对链接和精确 payload；拒绝未登记、相对、跨用户、来源或指针漂移。发布前后核 strict 与身份，使用不覆盖的 rename 并校验 inode，异常只恢复本次实际移走的入口，不删除外部替换物。
- 新 helper 的继承及编译配置消费者识别登记入口，避免把安装副本当成新可写目标；旧不可变二进制不会因此获得新回执 pin 校验，旧 C 仅继续已有 locator/binding/SHA/source 检查，恢复由新可信 helper 承担。
- 验证可信新 helper 从独立 checkout 处理既有不可变 sourceC/manifest 的现有高层 CLI 条件；若存在真实适配缺口，只补最小必要入口，不漂移旧 SourceInputs。
- 不运行生产 worker/正式 activation，不操作92413、原目标、原用户 Applications、原项目、历史或全局配置；生产恢复由 root 持有。

## 验收

1. 保留复制、删除、发布后 FileProvider 回填的真实失败；私有完整副本/链接在 1/3/10 秒 strict 均通过，来源保持。
2. 显式登记、复用、下一候选更新、继承和编译配置均实际验证；同一 Mach-O 不跨 C/S/manifest 上下文复用副本。
3. 签名、复制或发布失败保留或恢复旧入口；未知入口竞态不覆盖、不删除；未登记链接及来源漂移失败关闭。
4. 完整变更静态检查、必要 macOS 实测、独立审查、正式 gate/writer、精确 CI、main 及本单权威终态回读完成。

原483 pending 恢复与原用户入口实际安装/冷启动不在本单冒称完成；提供已交付可信 helper 的精确调用方式，由原宿主继续实测。

## 完整模板复制保真补充

组合验收实际发现 ditto 会漏掉 alternate Info plist 上存在但长度为零的 CodeSignature 属性。原生 getxattr 与十六进制读取交叉核实；普通 xattr -p 还会在 NUL 处截断二进制值，因此改为完整 hex 解码记录原始长度/摘要。仅在本次新建且 owned 的副本上，对源已证实为零长度且目标缺失的非 quarantine 属性执行 CREATE|NOFOLLOW 原子创建；已有属性不重写，EEXIST 拒绝并保留外部值。随后仍要求完整 raw 属性/文件字节/模式精确及 strict 签名，绝不忽略 cs.* 差异。原 v1 PR573、失败和旧证据保留，新版本另签发；572组合及精确CI未完成前不合入。

# G01　迁移源与开放 PR 清单

2026-11-21 04:43 UTC 采集 `zhzyx/nightmarish-spooky-sorceryze`。只读镜像中 main 指向 `0e1dcb293a55e3034bf92b4e02bc6b0028e5fb14`。迁移接收方应从清单中的精确修订建立比较点；后续产生的提交与 PR 另取增量。[机器可读清单](../data-collection/gonggong-ai-workbench-g01-inventory.json) · [工单 #1837](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1837)

| 检查范围 | 实测结果 | 接收用途 |
| --- | --- | --- |
| Git 服务发布的引用 | 1,640 项，包括 683 个分支、3 个标签和 954 个 PR 引用。清单逐一绑定完整引用名和目标 OID。 | G04/G05 可分别按引用命名空间比对，PR 引用保留原来源。 |
| 从上述引用可达的唯一对象 | 2,656 个 commit、15,423 个 tree、36,394 个 blob，共 54,473 个。三类对象未压缩内容分别为 2,260,742、88,567,823、761,676,861 字节。 | 迁移验收按对象类型和 OID 去重。借用对象库中的不可达对象不计入。 |
| 大文件和子模块 | 逐个解析可达树项的文件模式，`160000` 共 0 项。检查可达小 blob 的 Git LFS v1 指针头和 SHA-256 OID，匹配 0 项。 | G06 可用明确包含指针及 gitlink 的独立样例验证支持。源快照的空结果不验证外部存储读取。 |
| 开放 PR | #1661、#1245、#1234、#1216、#645，目标均为 main。清单逐单列出原作者、原链接及候选 head。 | 由原作者和审查流程在 GitHub 收尾。合入时对实际 merge commit 执行一次同步，关闭时存档原终态。G16 接收逐单处置。 |

## 复核口径

在只读镜像运行 `git for-each-ref --format="%(refname) %(objectname)"` 取得引用。用 `git rev-list --objects --all --no-object-names` 枚举可达对象，再用 `git cat-file --batch-check` 统计类型和内容长度。向 `git cat-file --batch` 读取树，按模式、名称和二进制对象 ID 解码；对不超过 1,024 字节的 blob 检查 LFS v1 指针。开放 PR 另从 GitHub 列表读取，记录采集时的目标、作者及候选。Git 身份验证由采集宿主处理，清单只保存仓库公开标识和对象元数据。[B04 迁移基线](gonggong-ai-workbench-b04.md)

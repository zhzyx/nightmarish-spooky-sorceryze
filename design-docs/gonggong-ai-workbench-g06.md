# G06　核对大文件及子模块引用

G01 在 2026-11-21 04:43 UTC 取得的 GitHub 镜像共有 1,640 个引用。G06 使用其完整引用映射重新扫描，从固定的源快照得到 2,656 个提交、15,423 棵树和 36,394 个 blob。逐树检查文件模式，扫描其中 4,824 个不超过 1,024 字节的候选 blob，得到 0 个 Git LFS v1 指针和 0 个子模块引用。该快照需要补收的外部对象为 0。[工单 #1824](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1824) · [G01 清单](../data-collection/gonggong-ai-workbench-g01-inventory.json) · [G06 实测回执](../data-collection/gonggong-ai-workbench-plan1-g06.json)

## 复核入口

从仓库根目录运行下列命令。第一项输入是本地 Git 镜像，第二项是 G01 清单或 G03 快照的 `git-report.json`。相对路径以调用目录为基准。

```sh
python customizations/components/tianxuan/migration/audit_external_objects.py MIRROR INVENTORY
```

先核对源地址、HEAD 和每个引用名及其完整 OID，再按固定对象 ID 遍历全部可达历史。对 LFS 指针记录 Git blob ID、声明的 SHA-256 与大小，按内容寻址路径流式读回实物。缺省在镜像的 `lfs/objects` 查找，`--lfs-root OBJECTS` 可以指定目标端导出的对象目录。Gitlink 按历史仓库内路径和固定修订去重，保留样例根树及可用的提交 ID。每个子模块的本地仓库由接收方用 `--module GIT_PATH LOCAL_REPO` 指定。程序读取固定修订的原始 commit 对象，连同 Git 对象头重新计算 OID。[只读核查入口](../customizations/components/tianxuan/migration/audit_external_objects.py)

标准输出的 `lfs` 和 `submodules` 逐项记录结果。G07 可用 `inventory_sha256`、`head` 和清单中的完整引用映射复核来源。外部对象全部核实或经扫描确实为空时，`complete` 为 true，退出码为 0。对象缺失、摘要或长度不符时返回逐项状态并以 1 退出。清单与镜像不匹配时命令报错，须重新确认输入版本。本次工具运行于既有天璇 Python 迁移宿主，可直接用原版 G03 命令读取既有目录；回退时移除此只读核查入口即可。[G03 导入契约](gonggong-ai-workbench-g03.md)

## 隔离项目目标回读

样例的父提交同时保存 LFS 指针和路径为 `vendor/模块` 的子模块。最新提交已移除两者。G03 向 `owners/g06` 发布两个提交和三项二进制制品，项目回读的目录修订为 `a20850e5d9a9ce58d237ed4722501f369fd5991a6c6a3aa92350f769356b6bdf`。在该修订下分别导出 bundle、报告和 LFS 实物，由 bundle 重建目标镜像后执行核查。[定向用例](../customizations/components/tianxuan/migration/test_audit_external_objects.py) · [目标发布、实物摘要与逐项缺失回执](../data-collection/gonggong-ai-workbench-plan1-g06.json)

| 验收项 | 目标端实测 |
| --- | --- |
| 指针回查实物 | 指针 blob `db5508e9274edfe82e19348919f4d167d0cf9432` 对应 24 字节。导出内容逐字节等于样例，SHA-256 为 `92e912cecf03f5b070472ddaba2dffdf601b5f5ca63a21f0f48162257277559b`。 |
| 子模块回查固定修订 | 历史提交 `d5e642e2d125818ca7f2ce1d3c33624c0ff69090` 在该路径固定 `c9bba7b8d96c3ef6943641894be31136edf8ba3a`。子模块仓库 HEAD 已前进至 `109f5aa8c9215113133709148768781d143ceb64`，仍能回读并重算原 commit OID。 |
| 缺失对象逐项列出 | 移除导出实物并指定空的子模块库，同一次执行返回该 SHA-256 的 `missing_payload` 和该固定修订的 `missing_revision`，退出码 1。 |
| 损坏与漂移 | 同长度改写实物后为 `payload_mismatch`。缺少本地子模块绑定为 `missing_repository`。给源镜像新增一个清单以外的引用后，输入校验拒绝该快照。 |

候选源码 SHA-256、解释器版本及完整测试命令均在实测回执中。G06 与既有 G03 导入的四项定向测试全部通过。后继 G07 另按 #1804 的全部前置和验收要求汇总。[G07 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804)

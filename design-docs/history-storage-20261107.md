# 历史数据占用与恢复索引

本轮响应 [#317](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/317)，在原机器上释放了 **1,689,179,240 字节（1.57 GiB）**。此数是恢复档案已处理文件和本地 Git 对象目录的分配字节差值；盘符自由空间还会受其他并行工作影响。文件路径均从工作区根解析，私有清单单独从 Git common-dir 解析。

## 去哪里找历史记录

| 内容 | 路径与查询方式 | 本轮处理 |
| --- | --- | --- |
| 谛听不可变事件 | `gonggong-diting-data/events/<租户>/<需求 ID>/`，需要事件种类、版本或纠正关系时从这里查 | 基线共 1,938 个受跟踪文件，含清单等元数据，逻辑大小 3,017,207 字节。Git 对象参与无损重打包。 |
| 来源、回执、工单和设计 | `data-collection/` 保存来源及核验，`design-docs/` 保存设计，工单编号可回查 GitHub 时间线 | 来源目录基线 543 个受跟踪文件。旧结论、修订和原始指纹继续按原编号查询。 |
| 退役框架与历史数据集 | `archive/olympus-retired-20261104/`、`olympus-hermes-data/` | 历史身份及证据通过原路径读取。 |
| 本机恢复现场 | `archive/local-recovery-20261104/`，下表按可读文件的逻辑大小排序 | 仅普通、未压缩、可独占写入且只有一个硬链接的候选文件启用 NTFS 透明压缩。 |
| 本地 Git 历史 | `git log`、`git show`，对象存储在 Git common-dir 的 `objects/` | 保留不可达对象重打包。前后完整对象集合指纹相同，`git fsck --full --no-dangling` 两次通过。 |

## 本机恢复现场

| 恢复目录（相对于上述本机恢复现场） | 用途 | 可读逻辑大小 GiB | 已压缩文件 | 实际释放 MiB |
| --- | --- | ---: | ---: | ---: |
| `godot-integration-local-archive/` | 旧 Godot 接入、安装备份与验证现场 | 7.86 | 1,591 | 882.96 |
| `gonggong-work/` | 历史任务工作材料与发布副本 | 6.78 | 177 | 82.83 |
| `worktrees-archive/` | 已归档的工作树材料 | 1.73 | 8 | 0.09 |
| `olympus-workspace/` | 退役工作区的本机文件 | 1.59 | 4,572 | 637.04 |
| `unused-initial-clone/` | 初始克隆 | 0.12 | 0 | 0.00 |
| `gonggong-root/` | 旧工作区根材料 | 0.00 | 9 | 0.48 |
| `local-settings/` | 原恢复材料 | 0.00 | 0 | 0.00 |
| `gonggong-candidates/` | 原恢复材料 | 0.00 | 0 | 0.00 |
| `collisions/` | 原恢复材料 | 0.00 | 0 | 0.00 |

另盘点专用工作树目录约 52.82 GiB。处理时跳过 46 处已注册工作树或含 Git 标记的工作副本，以及专用证据、设置目录、重解析点、已压缩媒体和小文件。2 个目录因访问权限未纳入，未调整 ACL。受跟踪目录统计固定于 `e115e1d902d0bdaf681d0fbc6f4c8f7ad5c43d40`。

## 核验与恢复

6,357 个文件均按原路径重新读取，SHA-256 逐项匹配，共读取 4,122,579,287 字节。其实际分配由 4,135,944,192 降到 2,454,650,880 字节。一个 130,362 字节样本另用 Windows 自带 `compact /U` 解压并核验，再用 `compact /C` 恢复压缩并再次核验。Git 对象目录由 138,155,256 降至 130,269,328 分配字节，重打包前后均有 27,001 个对象。

日常读取与检出沿用原路径。需要撤销某文件的透明压缩时，先使用 `git rev-parse --path-format=absolute --git-common-dir` 定位 `gonggong-history-storage/issue-317/verified.jsonl.gz`；清单中的 path 以本机恢复现场为基准。按记录核对 SHA-256，运行 `compact /U "文件绝对路径"`，再用 `Get-FileHash -Algorithm SHA256 -LiteralPath "文件绝对路径"` 复核。私有清单仅保存在执行机器；[汇总回执](../data-collection/history-storage-20261107.json) 留存清单指纹、目录口径、实测字节和校验结果。其他克隆可读取索引，实际节省以各自本机操作为准。

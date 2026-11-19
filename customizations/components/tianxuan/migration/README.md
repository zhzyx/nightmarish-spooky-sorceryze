# 天璇历史迁移

这些命令从本目录运行，输入目录使用绝对路径，数据存放在操作方选择的工作目录。需要 Python 3.11+、Git、Git LFS、已登录且有读取来源权限的 gh。迁移页面 index.html 可以直接打开，选择清单报告或原生归档回执核对字段。

1. 用 `python inventory.py --repo CHECKOUT --source OWNER/REPO --revision COMMIT --output INVENTORY` 采集只读来源清单。每次新快照使用新目录；同目录续跑会固定初始成员并复用分页缓存。GitHub 内容反映采集窗口内的观察值，Git 版本绑定精确提交。保存 report.json 与配对的 records.jsonl。评论正文、操作人等完整来源内容须按源库可见性保存。
2. 用 `python git_archive.py --source OWNER/REPO --records INVENTORY/records.jsonl --output GIT_DIR` 按来源引用及 PR 的历史提交创建完整镜像、history.bundle 与引用报告。再次运行会复用同一镜像。采集不同时间点使用新目录。已有可信检出可用 --reference CHECKOUT 加速获取；导出前镜像独立保存所有可达对象。
3. 用 `python attachments.py INVENTORY/records.jsonl ATTACHMENTS` 下载清单发现的上传件，核对失败列表。访问受限的附件须由有权限的责任者取得及核验。
4. 用 `python migration_archive.py INVENTORY/report.json GIT_DIR ATTACHMENTS DATABASE --tenant TENANT --actor ACTOR --receipt RECEIPT.json` 将 JSONL、bundle 和附件写入多宝 NativeStore。测试时指定隔离数据库。生产运行由整合主责确认数据库、租户、来源报告并取得独立审查。回执绑定原生目录模块与修订，恢复 API 为 importer.restore_inventory(database, tenant, module, revision, output)。输出目录须为新路径。可恢复并逐字节对照报告及二进制摘要。
5. 新建任务入口在创建前调用 routing.select_entry(database, project, requirement)。项目默认 existing，显式项目配置可选 tianxuan，需求配置优先；历史条目传 historical=True 后直接返回 archive。可使用 `python routing.py DATABASE PROJECT --set tianxuan`，需求加 `--requirement ID`。回退时选 existing。入口选择只返回宿主应使用的入口，任务创建仍由宿主负责。

这些脚本属于天璇外置 Python 宿主工具，使用现有 git_service 与 native_store 接口。更新和回退随宿主脚本版本切换，保留源清单、目标数据库、内容摘要及既有修订。Git 引用与 GitHub 元数据分别采集，报告须注明两个来源的覆盖范围。Git bundle 仅包含 Git 对象，外部内容需要单独核验。

## 发布原生目录回执

在归档命令中指定 `--publish-project OWNER/REPO`，经办人将该目录的摘要、计数及来源修订发布给所选租户下的项目。省略参数时，归档继续作为私有目录保存。HTTP 宿主从认证会话取得租户，通过 `migration_status.read_import_status(database, tenant, project)` 读取项目最新发布的回执。每次读取重新核验原生修订及目录字节摘要。

历史 v1 目录可由经授权的管理入口调用 `migration_status.publish_import(database, tenant, project, actor, module, revision)` 单独登记。回执的 `published_at` 记录首次向该项目发布的时间，`imported_at` 记录已取得证据的导入完成时间。旧目录缺少导入时间时此字段为 null。重新发布同一目录保留原有时点。

## 平台迁移入口

从侧栏进入 `/migration`。管理员在此按项目或需求保存入口。编辑和管理员可提交新任务；天璇入口创建 backlog 工单，GitHub 项目保留原入口时返回预填的新建链接。新任务以 call_id 去重，原生目录中的历史记录仅供查阅。

已认证客户端通过 GET `/api/v1/migration/status?project=OWNER/REPO` 查看已发布的来源、计数、导入及发布时间。GET/PUT `/api/v1/migration/entry` 接受 project 和可选 requirement 文档 ID，PUT 的 JSON 包含 entry。POST `/api/v1/migration/tasks` 接受 project、可选 requirement、title、call_id。AI 可通过现有 `/api/v1/tools` 调用 migration.status、migration.entry、migration.start。在线入口配置存于天璇领域库，离线管理使用 `python routing.py DOMAIN_DB PROJECT --tenant TENANT --set tianxuan`，HTTP 与 CLI 共用租户规则。旧式无租户规则只用于本地独立入口；如需启用，管理员从旧库读出指定项目和需求的有效值，再明确绑定至对应租户。

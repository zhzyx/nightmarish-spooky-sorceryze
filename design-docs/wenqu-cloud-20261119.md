# 文曲云文档注册与 AI 工作流

用户要求在天璇 / 文曲基础上完善类似 Confluence、飞书的云文档系统，用户注册后在线创建、编辑，AI 使用效率优先。2026-11-19 当前 Codex 会话确认沿用现有产品。关联既有需求 #1085 与剩余总表 #1188，本次范围为云文档。

## 验收

- 用户可注册独立工作空间、登录、创建与编辑 Markdown 文档，刷新后内容持久保留。
- 用户与 AI 使用同一权限边界，跨工作空间读取、搜索和修改均拒绝。
- AI 可检索、读取结构化文档、按版本执行局部修改，过期版本拒绝覆盖。
- 注册登录模式与现有管理员密钥模式明确配置，注册流程可通过 Web 使用。
- 完成相关后端回归、Web 构建与真实浏览器操作验证，记录未满足的部署条件。
- 通过适用审查与门禁后提交、推送、合入并回读，线上部署另核实实际目标与运行凭据。

## 实施边界

沿用 Next.js、FastAPI、SQLite 与 Markdown 数据契约。修改现有天璇模块，构建输入为 Web 源码及 Python 运行包。在独立工作树从 main ac8d1376 开始。目标运行环境沿用自托管部署，Windows 执行本地验证。回退通过原发布包及配置恢复，数据兼容既有模式。新增账号默认创建独立工作空间，复用已有注册领域逻辑。

主线生产模式明确关闭注册，当前 Web 仅个人密钥登录。先核验注册与文档链路，再补充 UI 与必要的认证模式配置。AI 只读核查由原生子 Agent wenqu_read_audit 承担，写入由当前责任者统一进行。

方法召回 github-issue-delivery 的已验证经验适用于出现 CI 失败后的关闭核对。当前未发生 CI 失败，保留条件性使用。

## 当前状态

工单 #1548 已创建并通过 intake-only。PR #1567 的完整模块回归（1217 passed、9 skipped、233 subtests）、Web 构建、Windows 编辑器及静态检查通过；浏览器已验证真实创建、连续保存与刷新持久性。普通 Docker 检查退出 137，不能交付。与整合父 #1550 协调，生产认证切换由整合主责核对。本会话只读核验已有服务器，未改变生产配置。

临时资源为本任务独立工作树、分支、`.venv-wenqu`、Web node_modules/构建输出，以及仓库根相对 `data-collection/receipts/wenqu-cloud-1548/` 私有验证资源。交付完成后按仓库规则清理。

## 接口与部署

`TIANXUAN_AUTH_MODE=accounts` 显式启用注册工作空间，配置 HTTPS `TIANXUAN_PUBLIC_ORIGIN` 并设 `TIANXUAN_REQUIRE_KEYS=0`。保留原 `TIANXUAN_TENANT_ID` 以继续验证已有个人密钥。浏览器使用 HttpOnly 会话 Cookie，脚本会话返回 Bearer token。现有密钥模式继续由原部署配置选择。

新注册空间默认独立租户，开放经过权限核验的文档相关接口。原部署共享代码仓库、合入队列及宿主全局操作由原租户控制。模型调用继续使用调用者的 BYOK 与既有租户计量。

AI `doc.read` 与 HTTP `GET /api/v1/docs/{id}/ai-view` 支持 `include_body`、`start_line`、`max_lines`、`max_chars`、`expected_version`。预算限制正文，目录元数据仍完整返回。默认调用兼容全文读取。

`doc.search` 复用可见文档检索，当前仍为全文扫描。`doc.patch` 与 HTTP patch 使用同一事务、版本条件与 `call_id` 幂等回执。同键重试重核当前权限。搜索规模性能尚未作万级文档验收。

## 普通容器内存诊断

固定原候选 dee99e99 的隔离运行 44486124788 在安装更新回退用例期间退出，Docker State 确认 OOMKilled=true。保持 192 MiB、1 CPU 和普通测试序列，仅将 API 的 DOCX/PDF 导出库延迟到对应请求加载，运行 44487065465 的 77 项普通测试通过，2 项独立突发测试未执行，退出码 0、OOMKilled=false；9 项导出回归通过。基础镜像摘要和依赖解析一致。成功运行内存峰值仍触及预算，不能推导生产容量余量。诊断、独立审查与限制见 data-collection/wenqu-cloud-1548-memory-validation.json 和 wenqu-cloud-1548-memory-review.json。

该修复需进入正式候选并复验 CI。已回读 PR #1570 合入 main 3e4f05e5ed3b8f3526ffc0ef2434c8c8911e5d34，22 个上游路径无冲突整合，不包含未验收的 resolver 扩展。生产认证保持整合主责已定版的个人 Key，自主注册上线及 A3 双人协作/版本恢复仍未验收。

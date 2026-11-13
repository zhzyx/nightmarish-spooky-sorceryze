# Windows 验收准备的宿主 TLS 与调用参数恢复

<!-- gonggong-request:blender-checksum-host-tls-20261113 -->

父 #978 的 Windows Blender 验收子项 #1059 在回读官方校验和时遇到宿主工具故障：网页获取工具返回402；独立 Python 3.14 的默认 HTTPS 证书验证返回 `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`。原失败发生在源码与运行时准备阶段，不是 Blender 几何或引擎产品缺陷。

当前会话负责限定排障。系统 curl 保持 TLS 验证取得官方 `https://download.blender.org/release/Blender4.5/blender-4.5.11.sha256`，与上一轮已验证原清单字节一致。随后对同一 Python HTTPS 操作仅在该进程设置 `SSL_CERT_FILE=/etc/ssl/cert.pem`，使用现有系统 CA 清单，原操作复验成功，返回字节也相同。未关闭验证、未替换系统证书、未保存全局环境变量，未修改用户登录及引擎有效配置。此项证明限定宿主操作可继续，不声称修复网页获取服务或全局 Python 安装。

验收为：保留原失败引用与准确层级；正常 TLS 校验取得官方清单；同一 Python/URL 在进程级可信 CA 配置下复验；公开记录不泄露私有路径/凭据，必要独立证据核验及随 #1059 候选正式交付；临时设置随进程结束，无遗留安装或配置。原始清单、curl日志、Python成功回执保存在宿主私有 receipts 中，基准为实际 Git common directory 父目录。

本项与 #1059 三项 Windows 几何运行分开：宿主校验和恢复不能代替 Windows 测试通过。初次夸父接单将故障误关联到 development 类 #1059，门禁正确拒绝且未接单；本单建立实际 bug 来源后接续原事故，不改变 #1059 类别或伪造接单回执。

同阶段子工作者的 intake-only 调用遗漏稳定需求 ID/租户参数，门禁按契约拒绝；读取实际 `work-items.json` 并补齐 `--request-id blender-windows-geometry-acceptance-20261113 --tenant gonggong-workspace` 后同一 #1059 intake 回读通过。这是独立的操作者调用错误，不是 TLS 的结果或门禁源码缺陷；原失败、自动事故与成功回读分开保留。本单收尾同时核对这一准备动作已经恢复，不修改正确的拒绝行为。


正式故障来源为 [#1060](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1060)。工单创建曾两次返回整条 CLI 操作的120秒超时；两次终态后分别回读最新远端 Issue，未发现该稳定需求。恢复时沿 GitHub 返回的 next 链逐页读取全部开放及关闭来源，11页、1059条（包含 PR）耗时103.536秒，完整查重后通过原 work_items 创建入口核对本人写权限并创建唯一 #1060。每页仍使用原120秒边界，整体只读恢复另有900秒界限；未放宽写入超时、未跳过查重、未重发未知写入。此为本次宿主私有恢复，不声称原两次超时已精确定位到某个子命令，也不声称通用分页实现已重构。

#1059 候选审查另发现并修复了版本头缺少 `LTS` 导致误拒绝、工作流清理失败可能未传递的问题。这些由 #1059 的源码审查与CI验收绑定，不能用本宿主恢复证据代替它们的实际Windows验证。


### 实际产物回读恢复

PR #1061 的Windows作业成功后，宿主 `gh run download` 等待326秒仍无本地文件，责任者仅终止本次只读下载；独立正常TLS单流取得部分字节后达到120秒上限。随后对固定artifact ID按服务器范围响应并发六条有界HTTPS读取，每段核对206、范围与长度；合并完整ZIP后核验GitHub服务器SHA256和ZIP完整性。PR和main原始归档分别为13,877,647与13,877,847字节，回读后原三项测试及每份产物摘要通过。这是本次宿主传输恢复，未重试发布、未绕过TLS、未将API认证转发到存储域、未声称修复通用gh实现；原评估快照的未知消费状态保持。详细绑定在1059最终验收记录，相关原始证据按同一私有receipts基准保留。

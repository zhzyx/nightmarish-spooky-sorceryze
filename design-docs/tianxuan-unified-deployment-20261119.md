# 天璇 Web 部署包

工单 #1577，隶属 #1550，需求 tianxuan-unified-deployment-20261119。

部署者从 main 手动运行 Tianxuan deploy build，将 release_revision 设为已接收的完整 main 祖先提交。CI 从该源码构建服务并经 Compose 验证后，归档正在运行的 Web 容器的镜像 ID。接收者校验 Actions 归档摘要、内部 tar.gz 摘要、镜像身份、源码 commit/tree 与运行编号，再在独立部署流程切换版本。日常 PR 沿用原构建与 API 包流程。

验收使用目标 3e1bb937a8635b2f1acd0f2adfb49b7b1e370210，检查 API 与 Web 两项实际上传及本地摘要。生产数据、登录与回退的验收记录由 #1577 部署者负责。

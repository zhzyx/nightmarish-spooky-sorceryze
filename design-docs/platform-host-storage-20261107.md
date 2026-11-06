# Git 文件采集和交付检查迁出共享框架

<!-- gonggong-request:platform-host-storage-20261107 -->

父工单 #231。基于八类平台目录，迁移 Git 文件采集实现与 Git 交付检查器（含模板、测试），核对工作区、工单门禁、阎罗签发、CI 分发检查和旧数据读取的调用位置。平台实现仍在其独立可信清单中核验，离线验收不能因迁移少检文件。父工单保留所有 Agent 精确候选的变更与独立验收。路径以仓库根解析。

本地验证与独立复核（#238）：交付清单 15 项、工单门禁 16 项、阎罗宿主 12 项、Godot 直接工单 16 项、离线注册校验 14 项。以上独立运行共 72 项通过，1 项环境条件跳过。正式框架校验及独立安装验证通过。宿主实录见 gonggong-diting-data/events/gonggong-workspace/platform-host-storage-20261107/platform-host-storage-20261107-request.json，来源索引在 data-collection/requests/platform-host-storage-20261107/。此回执限定本地文件落库，远端消费未知。仓库捆绑 Python 上既有桥接计时断言在基线和候选都可复现；用本机 Python 3.14 运行同一桥接测试，25 项通过。

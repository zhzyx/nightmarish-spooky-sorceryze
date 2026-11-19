# A8 工单资产预览和当前批准输入读取

父工单 #1550，承接已交付 #1552 的 A8 联调缺口。责任人 Sail-Li。

在工单确认区展示固定修订的真实概念图与可查看模型，保留下载。领域只读入口 read_approved_asset(store, actor, issue_id, kind, module, revision, path) 返回核验后的原生字节；认证 GET /api/v1/issues/{issue_id}/work/approved-asset 使用同名查询参数 kind、module、revision、path。以当前类型的最新提交和人工决定为准，重新读取同租户原生对象并验证摘要；失败拒绝交出字节。原生 head 前进不撤销固定修订，一旦工单改提新修订立即拒绝旧批准对象。

写范围为工单详情确认区、专属预览组件、work_management.py、work_management_api.py 与相关测试、工单文档及证据。#1581 负责执行核心的实际消费，#1577 独占生产写入，用户负责视觉签收。使用真实 PNG/GLB 验证预览、授权、摘要、旧版拒绝。沿用既有服务与 Web 安装入口，回退可恢复前一版本，无新数据表。

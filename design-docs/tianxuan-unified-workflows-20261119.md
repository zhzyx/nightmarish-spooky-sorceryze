# 工单计划与美术人工确认

关联子工单 #1552，父工单 #1550，需求 ID 为 tianxuan-unified-workflows-20261119。基线为 ac8d1376d0a03678b625cbe4bd9b09ea18120475。仓库内路径以仓库根解析。

## 正常入口

在天璇工单页打开真实工单即可维护计划、登记实际分钟数、提交美术资产和查看变更历史。路线图按路线图、里程碑和迭代排列可访问工单。自定义状态记录制作阶段。原生调度和交付继续使用既有工单状态与验收规则。

HTTP 使用现有天璇身份。GET /api/v1/issues/{id}/work 返回版本、计划、日志、累计工时、当前资产与历史。GET /api/v1/work/roadmap 提供跨工单视图。以下 POST 操作相对于 /api/v1/issues/{id}/work，每次写入带 expected_version 和稳定 call_id。

|操作|输入|
|---|---|
|plan|plan 对象，支持 iteration、milestone、roadmap、estimated_minutes、status、custom_fields|
|log|minutes、note|
|submit_asset|kind 为 concept 或 model，另附 module、revision、path|
|decide|同一组资产标识，decision 为 approved 或 changes_requested，note 记录意见|

AI 调用复用 Tianxuan.dispatch_tool，名称为 work.read、work.roadmap、work.plan、work.log、work.submit_asset。工单操作在 payload 中传 issue_id。人工判断通过工单页面的明确选择写入，记录认证身份和原生内容摘要。新提交的资产修订进入待确认。

冲突后重新读取工单版本。结果未知时使用原参数和调用键重试，可取得原版本回执。

## 存储与回退

扩展既有天璇 Python 服务、SQLite 领域库与 Next 工单页。原生资产输入来自已有 NativeStore 中精确模块、修订与路径。更新时重启服务、重建 Web；旧工单初始计划版本为 0。回退可部署上一版服务和 Web，保留领域数据库及原生库以便恢复历史。

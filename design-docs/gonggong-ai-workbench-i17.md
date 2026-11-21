# I17 项目内的工单分类与标签

工单 [#1758](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1758) 对应 [方案一 I17](gonggong-ai-workbench-plan1.md#i17)，直接前置为已交付的 [I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)。Mac 的先行观察确认工单详情已有类型，列表收到标签名后仍返回项目内所有可见工单。[原始观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1758#issuecomment-7067787786)

## 原生入口和归属

已登录用户可在侧栏输入标签名查找当前项目的可见工单，再点击编号和标题打开 I02 原生详情。详情展示工单类型和标签，每行一个标签；有写权限的用户可以添加、替换和清除。标签名按去除首尾空白后的原文精确匹配，同名工单通过稳定工单 ID 和项目内编号区分。类型沿用天璇已有的字符串。

天璇在原库创建 `issue_labels(issue_id, name)`，以工单 ID 和标签名作为联合主键，归属从原工单的租户与项目取得。旧工单从空标签集开始，已有类型继续可读。列表的可选 `label` 参数与项目、模块、需求、状态过滤叠加，并沿用原工单和上级需求的读取权限。标签查询成功时，服务回传实际筛选的项目和标签；原生界面据此识别旧服务忽略查询参数的情形。仅提供标签时，服务端采用默认项目。无标签参数的原有调用保持原语义。

I02 按编号返回详情时一并给出标签和当前操作者可否编辑分类。原生保存向 `PUT /api/v1/issues/{id}/classification` 提交目标类型、完整标签集合和原来读到的分类。在事务中重新核对租户、项目、角色及祖先写权限。两位编辑者提交通向不同分类的修改时，后到的过期修改返回 409；已保存目标的重试可直接读回成功。类型与标签同时持久化，成功后重新读回原单。用户切项目、退出或更换详情后，迟到的响应按请求代次丢弃。

## 构建、回退与验收

编辑器将 `editor/docks/workbench/issue_actions/issue_classification.gd` 通过已有的 IssueActions 生成流程嵌入侧栏。更改该脚本需要重新构建编辑器。还原时使用上一个编辑器和匹配的天璇服务；标签表可保留供新版再次读取。

以具有服务依赖的 Python 运行下列命令，编辑器测试在系统临时目录中创建数据库、两个项目和隔离编辑器。

```powershell
python -m pytest -q customizations/components/tianxuan/server/test_issue_classification.py
python tests/editor/run_workbench_issue_classification.py --godot <本次构建的编辑器> --report <本机报告路径>
```

定向验收包括两个项目各有一张带标签和一张无标签的同名工单、按标签只返回所属项目的原单、编辑类型和移除标签、只读账号重新打开、重开数据库后分类一致，以及跨项目、祖先权限和并发旧值检查。[候选及验证记录](../data-collection/gonggong-ai-workbench-plan1-i17.json)

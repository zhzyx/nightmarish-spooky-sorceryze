# S01　把工单能力要求交给司南

在原生工单的分类编辑中填写 `capability:<能力 ID>` 标签。例如，角色移动工单可填 `capability:coding`，角色动画工单可填 `capability:animation`。能力 ID 与安装目录区分大小写、精确匹配。一单可要求多种能力。工单标题可以相同，司南沿工单 ID 和已签认的定义分别取值。[S01 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1851) · [A03 阶段签认](gonggong-ai-workbench-a03.md)

## 输入与授权

天璇沿现有工单分类权限保存标签，并将能力 ID 的有序列表写入 `issue_snapshot.definition.required_capabilities`。普通标签沿用原来的分类用途。没有能力标签的历史工单沿用原定义摘要和既有复杂度映射。增减能力会更新定义并使原阶段签认转为待确认。即使改回原先的标签，负责人也须重新签认。[工单定义](../customizations/components/tianxuan/server/tianxuan_core.py)

认证的 `POST /api/v1/native/workflow/authorize` 接收原单 ID。宿主将安装计划所需能力与签认工单的能力合并，保留原计划中的顺序。已有的安装、生产身份、写入范围、检查项和阶段签认继续约束这张票据。`status` 可回读完整合同中的 `source.definition.required_capabilities`、`source.definition.stage_authorization` 与合并后的 `capabilities`。改变能力后，执行入口会阻止旧的已预约票据启动。[安装计划](../customizations/components/tianxuan/server/native_entry_factory.py) · [授权与司南看板](../customizations/components/tianxuan/sinan-workorders/native_workflow.py)

## 司南接收与缺口

`inspect.requests` 将票据、安装 profile 和全部所需能力送入既有 `dispatchEvent`。受信计划可指定 profile；普通安装入口优先使用已安装且覆盖全部能力的可用 Agent profile，有显式选择时保持该绑定。司南从同次看板读取的目录做最终匹配，服务在预约时复核。对缺能力的工单，原生适配器在 `deferred` 返回票据、profile、该 profile 对目标的可用状态、合同全部要求和该 profile 缺少的具体能力。该工单保持待派发，独立匹配工单可以执行。[原生适配器](../customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs) · [司南路由](../customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs)

## 验收与复跑

从仓库根运行下列命令。测试环境需要天璇 Python 依赖和 Node。Windows 实测使用同一签认设计拆出的两张同名模块工单，安装目录为程序与动画各提供一个本机测试 profile，两者各从真实进程读取自己的签认上下文，并写入各自授权的输出。第三张工单额外要求 `mesh-rigging`，路由返回该缺口，工作者库中没有该票据的物理进程记录。[定向验证](../customizations/components/tianxuan/sinan-workorders/test_native_issue_capabilities.py) · [候选和接收回执](../data-collection/gonggong-ai-workbench-plan1-s01.json)

```powershell
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_issue_capabilities.py
```

上游 macOS 观察覆盖原生设计文档的精确修订和历史恢复。本卡的司南 HTTP 接收及本机工具运行实测来自 Windows。S02 接续本机模型与 Agent 发现。[D03 Mac 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860#issuecomment-7067023618) · [D06 Mac 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861#issuecomment-7068555775) · [S02](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1848)

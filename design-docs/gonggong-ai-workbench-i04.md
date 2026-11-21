# I04 维护工单依赖

在 AI 工作台打开「工单详情」，读取当前项目的天璇工单编号。「上游工单」显示每个直接上游的标题、业务状态和验收结果。输入当前项目的上游编号后点击「添加上游」，或选中一行后点击「移除选中上游」。点击「刷新依赖」可以看到其他责任者刚接收的上游。收起详情、切换编号或退出账号会清空已显示的依赖。[I04 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1831) · [I02 详情接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854#issuecomment-7066884069)

## 数据与权限

控件先通过当前项目的 `GET /api/v1/issues/by-number/{number}` 解析上游，再使用详情记录的 ID 读取 `GET /api/v1/issues/{id}/work/flow`。添加和移除均向 `POST /api/v1/issues/{id}/work/flow/dependencies` 传递完整依赖集合、刚读取的 `expected_version` 和本次修改的 `call_id`。如果服务拒绝或写入回执未知，控件重新读取集合与版本，保留其他协作者的修改。内容修订仍由原工单详情给出。[工单控件](../editor/docks/workbench/issue_actions/issue_dependencies.gd) · [天璇服务](../customizations/components/tianxuan/server/issue_flow.py)

天璇核对当前操作者的写权限及对各上游的可见性，拒绝自依赖、循环和终态工单的依赖修改。只读用户可以刷新并查看进度。普通工单到达 `done` 后通过依赖判断。对原生托管的上游，服务还要求已有工作流验收回执。生产者运行结束时，面板继续显示「未验收，阻塞推进」；独立检查、审查、发布并验收后，刷新显示「已验收」，下游可按原有状态机推进。[工作流接收](../customizations/components/tianxuan/sinan-workorders/native_workflow.py)

## 构建与接收

该 GDScript 是现有编辑器的嵌入资源，随 I03 的共享构建入口生成 `IssueActions.gen.h`，由原生详情节点挂载。发布和回退以编辑器二进制为单位；依赖仍保存在天璇原有关系表中。I04 复用当前业务会话、详情变更信号及流程接口。

静默探针从命令面板打开原生工作台，启动本机隔离天璇服务和真实生产子进程。探针与另一个写入方交错修改依赖，核验过期版本遭拒并保留已登记关系，然后移除、添加、刷新上游。测试先尝试从 backlog 推进，记录未验收的拒绝，再对实际产物执行独立验收并再次推进。最终从新数据库连接核对关系、状态、流程版本与内容修订。[控件探针](../tests/editor/workbench_issue_dependencies.gd) · [服务与发布验证](../tests/editor/run_workbench_issue_dependencies.py) · [验证记录](../data-collection/gonggong-ai-workbench-plan1-i04.json)

```sh
python tests/editor/run_workbench_issue_dependencies.py --godot <候选编辑器> --report <本地报告>
python -m pytest -q customizations/components/tianxuan/server/test_issue_flow.py
```

前置账号入口的 Mac 观察覆盖凭据及租户隔离，本卡原生依赖控件的实测平台见验证记录。[D14 账号观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7060361368) · [D14 会话复核](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7062658872)

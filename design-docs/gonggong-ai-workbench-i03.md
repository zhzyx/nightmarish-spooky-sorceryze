# I03　维护父子工单

在 Godot 命令面板打开「Open AI Workbench」，登录天璇项目，进入「工单详情」读取子工单。层级控件显示当前父工单和可见的直接子工单。输入本项目的天璇编号并点击「设置父工单」可以增挂或换父项，点击「解除上级」可以解绑。成功后，详情重新读取内容版本和双向关联。窄窗口可纵向滚动至详情操作或关闭按钮。[工单 #1750](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1750) · [设计条款 I03](gonggong-ai-workbench-plan1.md#i03) · [前置 I02](gonggong-ai-workbench-i02.md)

## 服务与数据

`GET /api/v1/issues/{id}/hierarchy?project=...` 返回 `parent` 和 `children`。摘要包含 `id`、`number` 和 `title`。天璇按同一读事务核对主体、租户、项目和祖先需求权限，过滤无权读取的子项。

`PUT` 使用同一地址，以 `parent_number` 指定目标父项，传 `null` 解除关系。调用者传入上次读到的 `expected_parent_id`。写事务先取得 SQLite 写锁，核对当前工单和新父项的祖先写权限，沿真实父链检查成环，再比较旧父项。成环或竞争者已经改成其他父项时返回 409。重试已达成的目标时可直接读回结果。服务只更新既有 `issues.parent_id` 和修改时间。切换编号、收起详情或退出账号时，控件丢弃迟到的响应。[服务实现](../customizations/components/tianxuan/server/tianxuan_core.py) · [原生控件](../editor/docks/workbench/issue_actions/issue_hierarchy.gd)

## 构建与回退

现有工作台在 SCons 构建时枚举 `editor/docks/workbench/issue_actions/*.gd`，由 `editor_builders.py` 将脚本生成到 `IssueActions.gen.h`。侧栏编译单元把每个动作挂到 `WorkbenchIssueDetail` 下，复用现有业务会话。新增、删除或修改动作需重新构建编辑器。天璇 Python 服务独立部署，复用原有字段与权限检查。可部署上一版服务和编辑器恢复原入口，数据库保留已有关系。[生成器](../editor/editor_builders.py) · [原生挂载](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

## 实测与交接

Mac 上的 `a0697dd9` 基线支持创建时指定父单。三次对既有工单的 PATCH 均返回 422，旧详情缺少操作控件。Windows 候选通过真实命令面板、已登录的原生侧栏和真实天璇服务复验。增挂和解绑均返回 200，反向成环由服务返回 409。独立只读账号在每次写操作后核对父子关联与原工单字段。关闭服务并重新打开数据库后，原始正文和验收条件仍可读回。[Mac 基线观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1750#issuecomment-7067782101) · [Windows 候选、请求序列及回读](../data-collection/gonggong-ai-workbench-plan1-i03.json)

```sh
python tests/editor/run_workbench_issue_hierarchy.py --godot <候选编辑器> --report <I03报告>
python tests/editor/run_workbench_issue_detail.py --godot <同一编辑器> --report <I02报告>
python -m pytest -q customizations/components/tianxuan/server/test_issue_hierarchy.py customizations/components/tianxuan/server/test_issue_ancestor_acl.py customizations/components/tianxuan/server/test_issue_number.py customizations/components/tianxuan/server/test_module_issues.py
```

服务测试覆盖多层和自循环、相互挂载、两个写者竞争同一子单、项目错配、祖先授权变更和只读账号。960 × 640 的原生窗口验证了溢出时的滚动范围，并检查层级按钮及关闭按钮可完整进入视口。此候选交给父会话核对目标主线、完成签发并写回工单。双平台组合与最终协作组合另见 [F01](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743) 和 [Q13](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)。

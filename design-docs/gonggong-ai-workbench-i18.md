# I18　为当前工单附加本机文件

在 Godot 的 AI Workbench 中登录项目，打开工单详情，点击「添加本机文件…」并选择一个文件。控件将文件名和二进制内容发给当前项目的天璇服务，沿用多宝单对象 1 MiB 的上限。回执到达后，详情重新读取 I14 的附件列表并选中刚绑定的版本。用户可查看完整 SHA-256、来源和修订，点击「另存所选版本…」保存。收不到回执时可重新选择同一个文件。[原工单 #1759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1759) · [I14 版本读取和保存](gonggong-ai-workbench-i14.md)

## 附件绑定

原生会话向 `POST /api/v1/issues/by-number/{number}/artifacts?project=...` 发送单个文件的名称及 Base64 内容。项目、编号、已认证账号共同确定工单。服务先核对编辑权限和祖先需求的写权限，从接收的字节计算摘要，使用工单 ID、文件名和摘要定位不可变多宝对象。对象属于现有受保护的 `requirement-` 来源命名空间，原始对象读取沿用该工单当前的访问权限。[上传适配器](../customizations/components/tianxuan/server/issue_upload_api.py) · [来源权限](../customizations/components/tianxuan/server/tianxuan_core.py)

天璇在取得写事务后再次检查目标和权限。首次绑定追加一条 I14 的 `work.submit_asset` 事件。后续同工单、同文件名且同字节的上传返回原事件版本，包括不同写入者并发提交。相同文件名的新内容取得独立版本，旧版本仍可下载。多宝已收件而工单绑定中断时，重试会读取同一多宝对象并补齐天璇事件。列表和下载继续通过 I14 的 GET 接口读取绑定，保存前复核内容摘要。[工单事件](../customizations/components/tianxuan/server/work_management.py) · [原生文件选择与保存控件](../editor/docks/workbench/issue_artifacts.gd)

## 构建和复验

`editor/SCsub` 将附件控件嵌入 `IssueCreation.gen.h`，由侧栏 C++ 编译单元消费。服务通过现有 native 模式注册上传路由。原生编辑器与配套服务一起部署，回退可恢复上一对编辑器和服务。事件与对象沿用原表，I14 可继续读取已绑定的附件。

```sh
python tests/editor/run_workbench_issue_upload.py --godot <候选编辑器> --report <报告路径>
python tests/editor/run_workbench_issue_artifacts.py --godot <同一编辑器> --report <I14报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_issue_upload.py customizations/components/tianxuan/server/test_issue_artifacts.py customizations/components/tianxuan/server/test_native_api.py customizations/components/tianxuan/server/test_work_management.py
```

探针在隔离的临时项目打开候选编辑器，操作真实文件列表和确认按钮。测试服务在第一次写入后独立回读工单事件，再让客户端收到 HTTP 503。后续重选、同名新内容、返回旧版本和另存两份文件均经真实 HTTP 接口验证。Python 复开两个存储，比对原始字节、实际保存文件和当前项目引用。服务测试另行覆盖两次持久化之间的中断、并发、空文件以及权限撤销。[定向探针](../tests/editor/run_workbench_issue_upload.py) · [候选与回执](../data-collection/gonggong-ai-workbench-plan1-i18.json)

# D07 双用户编辑设计正文

两位有写权限的账号在工作台打开「设计文档」，从列表选择同一文档，再点击「编辑正文」。一方保存后，另一方的阅读窗口自动读取新修订，并保留正在编辑的草稿。双方修改不同段落时，第二次保存会合并两人的修改。D04 以空白行分段，一个段落可以包含多行。[D07 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1787) · [D04 编辑入口](gonggong-ai-workbench-d04.md)

两人修改同一段时，「保存」暂停。上框保留本地完整草稿，下框显示对方提交的修订号与完整正文。可复制对方的段落，在上框编写最终正文，点击「核对两份正文…」并确认，再点击「保存」。取消确认仍可继续核对。服务以已核对的修订号校验写入，其间发生的第三次编辑也会触发版本检查。

## 通道与写入

窗口使用当前天璇会话连接所选文档的 WebSocket 房间。收到快照、修订或变更通知后，按文档 ID 与版本读取原文及作者。选择文档、关闭窗口或切换账号会结束原订阅。按修订号打开的历史引用始终定位到指定修订。[工作台会话](../editor/docks/workbench/business_session.gd) · [协作适配](../editor/docks/workbench/document_collaboration.gd)

保存先发送 D04 的条件 PATCH。版本落后时，编辑器调用 `POST /api/v1/docs/{id}/merge/preview`，服务验证写权限、编辑起点和原文，再用文曲三方合并器比较以空白行划分的段落。预览返回合并草稿或远端冲突正文，写入继续沿用带 `expected_version` 和 `call_id` 的 PATCH。成功回执丢失时可用同一请求核对结果。[服务接口](../customizations/components/tianxuan/server/api.py) · [文曲合并](../customizations/components/tianxuan/wenqu/wenqu.py)

## 构建与验证

协作脚本与 D04 会话脚本均作为 `BusinessSession.gen.h` 的输入，由原生侧栏挂载到当前业务会话。更换脚本需要重建编辑器，回退使用配套的先前编辑器与天璇服务。服务沿用已有文档、版本和幂等回执表。[构建输入](../editor/SCsub) · [原生挂载](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

在安装天璇服务依赖的 Python 环境中执行下列命令。探针启动一个临时服务和两个独立的 headless 编辑器，分别使用租户管理员和受邀编辑账号。实际读取双方的 D04 控件，核对不同段合并、同段不同行冲突、取消确认后的服务端原文和确认后的第五个修订，并核对丢失合并成功回执时的重试记录。[定向验证回执](../data-collection/gonggong-ai-workbench-plan1-d07.json)

```sh
python tests/editor/run_workbench_document_collaboration.py --godot <候选编辑器> --report <回执路径>
```

上游 D04 的 macOS 观察覆盖服务写入、原生读取和关闭重开后的段落定位。总单另有 Windows 服务端双连接实测。此次 D07 原生联动的验证平台为 Windows。[D04 macOS 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1863#issuecomment-7065749950) · [总单 Windows 服务端观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1709#issuecomment-7066453423)

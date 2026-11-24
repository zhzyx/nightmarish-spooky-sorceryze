# C07 资产归属选择器

在 Godot 的 AI 工作台点击「打开多宝资产…」，填写来源模块、不可变版本与对象路径，再点击「查看现有归属」。没有业务关系的对象可作为当前草稿的引用。同一对象属于多个模块时，确认按钮要求先选择一个模块或「仅作引用，保留当前会话」。同名模块显示稳定 ID。取消后原会话、草稿与工单保持原样。[工单 #1785](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785) · [设计条款 C07](gonggong-ai-workbench-plan1.md#c07)

显式选择业务模块会打开该模块概览。在现有工单的详情内点击「从此工单打开资产…」，则从其模块的资产列表选择对象，直接回到原工单的草稿。确认前工作台再次读取对象、模块关系和来源工单。来源读权撤销、关系移除或工单移至其他模块时要求重新选择。两种入口只在显式发送后提交聊天消息。[C03 关系及来源权限](gonggong-ai-workbench-c03.md) · [C06 工作位置与草稿](gonggong-ai-workbench-c06.md)

## 输入与接收

新增的只读接口为 `GET /api/v1/native/asset-context/{source}/{revision}/{path}?project=…`。天璇沿用当前身份与 C03 的对象标识，校验多宝原件的读取权限和字节，再从当前项目回读有权查看的关系。响应包含 `asset_id`、`source_module`、`revision`、`path`、`sha256` 以及含稳定 ID 与显示名的 `modules`。认证、读权或对象版本错误返回错误状态。该读取无需建单或建立关联。[业务接口](../customizations/components/tianxuan/server/business_asset_api.py)

其他原生资产视图也可向工作台的 `WorkbenchAssetPicker.open_standalone_asset` 直接传入已打开对象的 `source_module`、`revision` 和 `path`，进入同一选择器。原生控件把可复制的精确定位串加入对应输入框。业务会话发送时在本轮快照中保存 `duobao:<asset_id>` 及多宝版本，工单入口还保留工单 ID。编辑者从草稿删除定位串后，该条引用随之移除。本机会话的输入框保存可编辑的完整定位串。工作台通过 C06 的天璇请求接口使用当前项目与账号。[原生控件](../editor/docks/workbench/asset_picker.gd) · [每条消息的上下文](gonggong-ai-workbench-c05.md)

## 构建与复验

编辑器构建将控件脚本与既有模块选择器一起生成到 `module_selector.gen.h`，由原生侧栏装入。更新这些控件后重新构建编辑器。回退时使用上一个已验证的编辑器及其配套资源和天璇服务。后端沿用已有多宝与天璇表。[构建入口](../editor/SCsub)

从仓库根使用已安装天璇服务测试依赖的 Python 执行以下命令。原生运行器用临时数据库和隔离的编辑器副本，从命令面板实际打开侧栏。它核对无归属、同名双归属、取消、已发出查询的迟到回应，以及工单继承；服务端回读发送快照和操作前后的工单 ID。

```powershell
Remove-Item Env:GONGGONG_WORKSPACE -ErrorAction SilentlyContinue
python -B -X utf8 tests/editor/run_workbench_asset_ownership.py --godot bin/godot.windows.editor.x86_64.exe --report bin/c07-native.json
python -B -X utf8 -m pytest -q -p no:cacheprovider customizations/components/tianxuan/server/test_business_assets.py
```

既有 Mac 实测覆盖双关系、未建单与来源读权撤销。Windows 原生运行的候选、控件和目标接收回执随本卡保存。[Mac 双归属回读](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785#issuecomment-7060361063) · [Mac 权限回读](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785#issuecomment-7062657668) · [候选与验证回执](../data-collection/gonggong-ai-workbench-plan1-c07.json)

## C06 验证来源

C06 的方法记录引用工作者实测回执的原始字节。主线合入 `8b48bd11844073a0d73499899991f7ee6f3b712f` 时扩充了回执，导致原摘要校验失败。本卡追加保存工作者的原始实测文件，发布后的主线回执沿用原路径。方法记录追加引用校正，并用整合后的编辑器复验进行中的查询取消。[C06 工作者实测原件](../data-collection/gonggong-ai-workbench-c06-initial-receipt.json) · [C06 主线整合回执](../data-collection/gonggong-ai-workbench-plan1-c06.json) · [C06 合入 PR](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1936)

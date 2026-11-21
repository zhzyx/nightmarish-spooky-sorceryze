# 旧布局和工单链接打开统一工作台

[U13 工单 #1791](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791) 依赖 U03、U04、U05 和 U11。顶栏保留现有的工作台按钮。命令面板、可重绑定快捷键、侧栏和展开视图继续使用同一个聊天控件。编辑器插件仍可按名称访问 AI Chat 或天枢原生面板，工作区菜单仍可进入天枢的工单、归档和多宝工具。

### 恢复布局与会话

上一版在项目的 `.godot/editor/editor_layout.cfg` 中保存 `[docks]` 下的 `dock_12` 及 `dock_12_selected_tab_idx`。加载器先从原始顺序识别所选项。选中 `AIChatMainScreen` 或 `DaqianMainScreen` 时，编辑器展开工作台，共用原会话控件。两个原面板继续按旧键保存，顶栏隐藏其标签。旧布局只记录当前页，展开视图默认返回 3D 编辑区。选择其他主屏的旧布局仍回到对应编辑区。

新布局在 `[docks/AIChatMainScreen]` 下保存侧栏可见性和当前只读咨询的位置。位置包含天璇工单 ID、编号，以及服务、账号、业务项目和编辑器项目目录共同计算的摘要。重启并重新认证后，工作台按同一身份读取工单详情并打开原会话。切换项目或账号时清除待恢复的位置。历史内容继续由天璇按权限返回。

### 工单链接

天枢看板、工单详情和检查器通过原有的卡片绑定函数产生 `https://github.com/<owner>/<repo>/issues/<number>`。点击卡片编号会进入工作台。也可在工单详情的编号框粘贴旧链接或天璇页面生成的 `/issues/<id>` 路径。绝对天璇地址可使用原生编辑器的本地网页入口或当前部署指定的 `TIANXUAN_PUBLIC_ORIGIN`。

工作台按完整 GitHub URL 读取天枢已有的 external-context 关联，要求当前项目中有唯一的直接目标工单；旧需求树关联可定位其唯一根工单。工作台验证目标 ID、当前项目、详情编号与修订，随后沿 U11 的 `for-issue` 接口定位当前用户的只读咨询。缺少关联、多义关联和无权读取时显示反馈。保留“查看 GitHub 原单”链接，用户可回到原站。

### 验证与回退

在安装了天璇测试依赖的 Python 环境，从仓库根运行以下命令。Windows 传入候选编辑器 EXE，macOS 传入包外的裸编辑器可执行文件及其配套天枢 UI 包。探针使用系统临时目录、回环服务、独立账号和无窗口编辑器。

```sh
python tests/editor/run_workbench_legacy_routes.py --godot <candidate-editor> --report <report.json>
```

探针先从编辑器在两张同名工单中各发送一条消息。随后加载上一版实录的主屏顺序，分别选择旧 AI Chat、旧天枢和 Script，并从实际天枢卡片和天璇网页路径核对原会话及消息 ID。保存侧栏后重启，先检查自动恢复，再用另一业务项目检查隔离。窗口按钮、侧栏展开和宿主启动探针另有回归核验。[Windows 验证记录](../data-collection/gonggong-ai-workbench-plan1-u13.json)

回退时恢复前一编辑器及配套天枢 UI 包。旧版继续识别原布局键与选中下标。工单、外部关联及咨询历史保存在原天璇服务中。

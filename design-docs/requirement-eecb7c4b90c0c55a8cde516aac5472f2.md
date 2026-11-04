# AI chat 界面显示与布局优化

<!-- gonggong-request:requirement-eecb7c4b90c0c55a8cde516aac5472f2 -->

关联 Issue： https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/55

2026-11-05 用户明确要求接手并开始优化 AI chat 显示和布局，替代此前“文字咨询、待明确异常”的范围。原始需求摘要为 eecb7c4b90c0c55a8cde516aac5472f2f3388ade103dbf9a2c6add9d4088809f。

本轮交付为 Windows Godot 编辑器 UI 源码候选，基线 b123479a；工作树为 D:/GongGong/.worktrees/issue55-ui，以下相对路径均以此为基准。仅调整 editor/docks/ai_chat_dock.cpp 的布局：限制高级设置占用高度、长模型名称省略、工具操作可换行、输入区域归组。现有主工作区 Issue #51 调试改动不进入候选。连接协议、权限行为、框架与有效发布不在本轮范围。

验收：窄窗口内操作不被整行最小宽度推出；高级设置可独立滚动；输入、附件和发送操作归组；消息正常换行；连接、发送、停止、附件和高级选项信号保持。必要检查为差异检查、API 对照及相关界面回归；目标编译器为 Windows MSVC，编译与实际界面覆盖须明确记录，不能复用旧二进制声称新候选通过。完成源码候选与检查后停止本轮，不自动合入、发布或切换引擎。

入口：issue_gate.py --intake-only 已回读 Issue #55 为 open / type:bug / status:in-progress；执行者为当前 Codex。已回查 gonggong-check、冻结纲领及元衡规则；这是本地自查，不是独立准入批准。

## 首轮候选与验证

- 高级设置限定为 200 × EDSCALE 高度，内部滚动；折叠同时隐藏外层容器，保持 AdvancedSettings 类型和选项父子关系。
- 模型及后端选择框不再按最长名称计算最小宽度，过长文本显示省略号；下拉列表保留完整条目。
- 编译操作和图片操作改用 HFlowContainer，空间不足时换行；编译控制仍在高级设置外，维持既有可见性约定。
- 附件、队列、输入和发送操作归入 ChatComposerPanel；消息区继续使用剩余高度和现有智能换行。
- MSVC 14.51.36231 对本候选 ai_chat_dock.cpp 执行 /Zs 语法检查通过，git diff --check 通过；使用候选头文件及 D:/GongGong 中既有生成头文件回退，不代表完整编译、链接或运行验收。
- 待验收：新候选构建后，在 640/960/1440 像素宽度和 100%/150% 缩放下检查长模型名、设置展开/折叠、长消息、附件、排队、发送/停止及 Agent 切换。当前没有可用的 SCons Python 模块，也未用旧编辑器二进制冒充新候选。
- 状态：本地源码候选，未提交、未合入、未切换发布。提交前仍需正式 issue_gate，提交后需 git-check --require-committed。Issue 保持进行中。
- 上报：验证来源保存在 data-collection/issue55-ui-candidate.json；当前未取得 reporter 的实际宿主身份绑定，因此未声称已排队、落库或消费。

## 更新主线并准备提交（2026-11-05）

用户追加要求：更新 Git 仓库到最新本地版本，再提交本次更改。已 fetch origin，并将本任务分支快进至 1b0a33fd5e3a579e70c46aedeb67dc3f179c2130。主工作区仍有其他任务的未提交修改，本次不代其提交或移动分支。

已解决与 #52 紧凑顶栏的六处文本冲突，保留新主线的四种后端、会话命名、全窗显示和构建状态布局。连接/模型区与操作顶栏改用流式容器，宽屏并排、窄屏换行；高级设置滚动区及输入归组在此基线上继续生效。冲突后重新执行 MSVC /Zs，通过；未执行完整编译、链接或视觉验收。旧候选记录保持原样，新证据见 data-collection/issue55-ui-updated-candidate.json。

本次授权交付是本地 Git 提交；不包含推送、合入主线或发布。Issue 继续保持进行中。实际文件事件通过 diting-files record 写入；不表示数据库投递或下游消费。

## 独立回归审查（2026-11-05）

本轮仅交付独立测试和评价，不修改 #56 的 UI 实现。测试基线 e776639f；整合候选 cpp/h、console 包装器及实际引擎 SHA256 见 `data-collection/issue55-layout-regression/build-input.json`，均在运行前后核对。路径基准为本需求所在仓库根；本轮独立工作树的实际位置属于宿主上下文，不是持久化解析基准。目标为 Windows/MSVC 已构建候选，物理窗口 640/960/1440 × 900、编辑器缩放 100%/150%，每例独立进程；为窄窗压力验证显式放宽编辑器默认最小窗口。

交付 `tests/editor/ai_chat_layout_regression.gd` 和 `tests/editor/run_ai_chat_layout.py`，要求构建回执与摘要匹配；覆盖长模型名、设置滚动/弹窗关闭、四附件、长消息、发送/停止、会话草稿/附件恢复。原生 AIChat 22 用例/254 断言通过，100% 三宽通过；150% 三宽失败：发送/停止位于 y946，超出900高度，640宽另有横向裁剪。原生行为断言通过。首轮受网络权限影响的 headless 探索记录不作为隔离附件缺陷证据。完整结论及未决项见 `data-collection/issue55-layout-regression/review.json`；测试期间新增诊断字段的逐例输入修正另有记录。没有截图或发布批准；不得将几何测试等同人工视觉通过。

停止条件：已将必须修复项交 #56；等待其新固定源码/构建事件后仅重验受影响150%场景。Issue继续进行中，不自动关闭、合入或切换有效安装。正式门禁及提交后核验仍需执行。

候选2增量构建后按新摘要仅重验150%受影响矩阵（headless，未占用#49桌面）。960/1440折叠初始状态已恢复；四附件时Send y879/h50仅可见21，640横向限制定位到外层编辑器VBox的872最小宽（AI Chat自身574）。新报告 `data-collection/issue55-layout-regression/candidate2-review.json` 不覆盖原生首轮失败记录；仍需修复和对应候选验收。

## 最终独立布局回归：候选6

#56交付冻结三源码与console/实际引擎摘要后，因底部工具栏影响所有宽度，本次重跑六组原生矩阵。全部通过，包含长草稿+四附件组合、设置弹窗、长模型名、发送停止、会话草稿/附件恢复、切回3D/Script完整菜单恢复。逐例实际测试脚本摘要及前后源码/产物校验见 `data-collection/issue55-layout-regression/candidate6-native/summary.json`，独立评价见 `candidate6-review.json`（以上data-collection目录为其解析基准），三张主视图PNG随证据交付。候选4的剩余失败另保留，未把其源码漂移后的补验当作通过。

独立评价仅覆盖精确候选6布局；后续实现提交须保持相同源码摘要。已有初始会话标题乱码已交#51/#56，不宣称修复；真实外部模型服务、实际构建/重启中的窄窗表现未由本矩阵验收。无远端合入、安装切换或交付批准；由协调者按实现候选提交和相同证据串行完成后续交付。

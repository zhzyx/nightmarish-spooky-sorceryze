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

## 2026-11-05 全工单推进事件

实际截图确认设置面板挤压输入区，且新主线页签再次乱码。为补齐 #55/#51 原生候选证据，在独立 issue-progress 工作树以 Windows x64/MSVC、tests=yes、accesskit/d3d12/angle=no 增量构建；复制 #49 已编译对象缓存供 SCons 重新判定，不复用旧二进制作为候选。仅验证本地候选，不切换有效安装。编译器 Python 已定位到项目 build-support，纠正此前未找到 SCons 的环境观察。

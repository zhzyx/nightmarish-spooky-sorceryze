# 编辑器受控命令覆盖补齐

授权来源：Codex 用户要求汇总仍需截图/鼠标键盘接管的界面，独立任务批量修复，持续实现、编译、独立验收及 main 交付。基线 origin/main e2a1d2b7。当前副本 codex-editor-command-coverage。

目标：复核 F01–F15，建立可追溯矩阵，按依赖补齐语义接口及 macOS 测试隔离。平台 macOS arm64，Clang，headless 编辑器验证；像素、IME、原生窗口及外部认证验收保持独立未知。禁用桌面控制。

边界：不触碰模型自动刷新/移除按钮、原聊天运行进程、全局设置；不实现模型自我授权。密码、exclude、编辑场景内容排除及咨询/工具关闭、宿主确认、实例旧值、回环 Bearer/session/busy 边界保持。

## 生产工单
1. 测试隔离：统一 self-contained 可执行副本，保护真实 EditorSettings，验证摘要不变。
2. 可发现性：只读描述、分页与截断、动态主屏、延迟弹窗发现、受控文本与控件语义。
3. 专用宿主/业务命令：AI Chat 非授权动作、资源/场景/设置、观察与路由恢复，逐项独立验收。

## 验收与停止条件
每项需记录代码证据、实际命令测试、拒绝路径和容量边界；编译与独立审查通过，正式门禁、精确 CI、main 回读及关联 Issue 完整验收。未支持/未实测不标通过。依赖范围通过实际子工单追踪，不把本矩阵作为第二套工单账本。


## 来源工单及认领
父单 [#386](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/386)；测试隔离 [#389](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/389)；发现与语义 [#388](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/388)。当前操作者 kaiyunxue。原聊天继续负责 #217 模型按钮及其运行进程；#385 马良界面和 #365 天枢更名在途，保留对方写入责任。

## 覆盖矩阵（首批实现与独立验收；不冒称视觉实测）

| 编号 | 基线复核及首批结果 | 已执行验证/保留范围 |
|---|---|---|
| F01 | 保留 AI Chat page_only，专用宿主命令覆盖状态/草稿/发送请求/停止/会话/模型/连接/队列/登录请求；模型工具无 host_context 拒绝；写命令即使 autoexec 也需新人工确认 | 已测草稿、发送请求取消、停止、会话切换、模型及≥100索引冲突、端点配置；未执行真实登录/浏览器认证，队列保留原宿主处理链 |
| F02 | 新增 Tree/ItemList/TabBar/ColorPicker/ScrollContainer 发现、读取和语义动作；条目分页与JSON数字转换 | 原生与真实编辑器验证；PopupMenu、Curve/Gradient、GraphEdit 由 [#407](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/407) 继续 |
| F03 | 原有 reveal_target 已展开/选标签/滚入视口；新增 scroll_to 明确坐标语义 | 不新增任意OS键鼠绕过。激活、上下文和图拖放业务语义归 #407；焦点/IME/原生窗口像素仍未知 |
| F04 | read_text、append_text、Unicode范围替换、选区/光标、LineEdit提交、有限撤销 | 确认/实例/旧文本与选区变化拒绝；8192 UTF8输入。TextEdit多光标选择拒绝；撤销只恢复最后本接口写入，最多128目标 |
| F05 | 自动目标描述值/选区/范围/选项/禁用只读原因/窗口实例/几何/焦点 | 文本和条目/页面均有UTF8 JSON字节预算。核心/显式别名仍保留原摘要，详情可从自动目标、read_items及inspect_ui取得 |
| F06 | find_targets/HTTP/client支持offset/total/next_offset/has_more；区分扫描截断和分页字节截断 | 45字段无重漏分页；8192目标/50000节点真实构造与明确lower_bound；不得把截断时总数当真实全集 |
| F07 | 基线已有树变化监听；BFS修复深层原生页先耗尽容量导致新页丢失 | 真实延迟Window/字段发现和关闭观察；PopupMenu原生Window专项归 #407 |
| F08 | 动态列举主屏，按原生名称/显示标题/layout_key选择，歧义拒绝 | 最新马良/大千 main上的实际切换、6种布局/重启顺序均已验证 |
| F09 | open_resource统一编辑入口；路径/符号链接拒绝，加载前确认绑定文件摘要和编辑器实例 | Gradient资源打开、越界拒绝、确认往返；不把资源加载作为无确认的引导准备 |
| F10 | 基础节点创建、叶子删除/移动、改名、多选、属性、UndoRedo；复用原生NodePath/动画引用维护；运行请求强制人工确认 | 真实节点/属性/动画重命名→移动→撤销往返与headless子进程运行/停止。100节点/16KiB快照；完整子树、脚本/继承/实例、资源/信号/导入导出归 [#408](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/408) |
| F11 | 新增独立读取、显式同型新增/更新项目设置、受限EditorSettings外观/语言设置；支持JSON基本类型、字典/数组、向量和颜色 | 私有设置Color、项目Vector2i往返；文件审批期间变化拒绝；凭据/ai_chat/行为与输入策略拒绝。自动Inspector也排除host权限命名空间与凭据字段 |
| F12 | inspect_scene/inspect_ui提供分页结构、实例/父实例、路径和几何；保护子树省略；get_editor_state保持16KiB契约 | 44节点分页、UI树50000节点边界；截断/省略明确。不是像素截图或完整未截断进程快照 |
| F13 | 基线已有GET /v1/requests；新增state、cancel及有界events轮询，CLI同步支持 | Bearer/session拒绝、精确取消、幂等取消、元数据事件与gap；8连接/5秒等原上限保留。未宣称SSE长连接订阅 |
| F14 | 新增field_value/window_closed/request_completed | 实际字段与弹窗、命令完成观察；project_setting观察拒绝凭据键。request_completed是路由结果，异步业务仍须状态/业务证据，run_requested不能当进程完成 |
| F15 | 256条/900秒的本地结果摘要原子落盘，先记录不确定性再执行；恢复不自动重放；损坏拒绝；独占写入与POSIX存活核对 | 干净退出/SIGKILL/未知效果/过期/损坏恢复、同时双编辑器与同时回收死进程实测；不保存草稿/旧值/凭据，不是签名授权记录。短acquiring锁崩溃保守保留；非POSIX崩溃恢复需人工处理 |

## 批次与责任
首批把测试隔离、目标语义和宿主路由放在同一候选联调，因为授权/确认/实例校验与真实编辑器验收不可拆开宣称成功。主关联 #386，各受影响子项分别留证。#388/#389/#407/#408 已建立原生 parent/sub-issue 并回读。#389按其隔离验收独立收尾；#388/父单不因基础部分合入而完成。#407/#408由本任务在首批main接收后连续推进，不将登记或交接当实现。

目标平台限定 macOS arm64。首批未改模型自动刷新/移除按钮、未重启原聊天进程。main已从 e2a1d2b7 经 e061f84e 整合到 1d080f65，保留马良/大千顺序、大文件读取及运行候选激活结果。tab_order runner保留新main六阶段验证并改用统一隔离助手。最新基线重新构建并通过53个原生用例/1144断言、独立19组命令和6组锁验收、6项隔离测试、原HTTP路由及六阶段布局；原始用户设置在隔离测试前后摘要一致。

## 容量与授权验收约束
保留遍历50000节点、8192自动目标/128显式目标、文本8192 UTF-8字节、旧值JSON16384字节、32引导步骤、状态16KiB/数组100项、路由32KiB/256回执/900秒、HTTP8KiB头/32KiB正文/8连接/5秒。新增分页需明确截断与总数含义，不宣称截断扫描外的真实总数。所有写入先预览再按宿主实际确认执行，并复核目标实例和旧值；secret/exclude/page_only/编辑场景排除保持。

像素、布局缩放与遮挡、焦点/滚动/弹窗层级高亮、IME及快捷键、macOS文件/保存退出、外部认证终端/浏览器和返回编辑器：待真实视觉验收，命令回执不替代。当前任务不控制用户桌面。

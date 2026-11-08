# 编辑器残余命令式能力批量修复

用户授权：有命令式不支持的，得到全部列表后新建任务批量修复。本聊天为该新任务。来源：原工单 #483 的明确用户委托，#483 仅作来源，不复用其 owner/binding。

基线 b21a9cd1ea6c9e922765a60e22cae4e0014a82fd。原只读审计 SHA256 f52ae7902e5915798c02773098ca7699161b53ef090bc7dfdb3a5bfaf4055268；审计仅源码，不代表本版所有窗口实测。

## 完整验收范围

- C3-parent_close_rename: 关闭/重命名AI Chat父会话标签。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-ordinary_manual_child_create_close: 新建/关闭普通手动子会话及父子层级管理。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-scheduler_task_lifecycle: 定时器任务列表/详情/CRUD/启停/立即运行/选择任务/关闭运行会话。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-manual_model_reasoning: AI设置：手动模型ID与推理强度。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-runtime_paths_cli_configuration: AI设置/共工环境：Node、Codex、工作流/编译Python和CodeBuddy入口路径。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-chat-attachments: AI Chat添加图片/从剪贴板粘图/删除附件/带附件原子提交。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-viewport-spatial-gestures: 2D/3D视口相机平移/绕转/自由缩放、射线拾取和gizmo拖拽等指针手势。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-timeline-keys: 动画时间轴的关键帧/轨道选择、拖动/剪切复制等时间轴编辑手势。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-tile-polygon-paint: TileMap画布笔刷/自由涂绘、2D多边形逐点拖拽。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-custom-compound-controls: 未在actions中广告的自绘/插件操作，Tree多列单元格/checkbox编辑、RichText元数据链接等。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-live-game-input: 运行中嵌入/独立游戏的键盘、鼠标、手柄游戏输入。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-menu-open-and-direct-capture: 稳定打开标准/全局MenuBar菜单及直接获取当前编辑器截图回执。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-local-change-history-ui: AI Chat修改记录/本轮差异/历史快照浏览页。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-mounted-host-chat: 天枢/大千挂载的AI Chat宿主页之普通外部文本续接。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。
- C3-CodeBuddy-review: CodeBuddy原生连接下的内部只读子验收。补实际声明式语义、对象/父会话/权限/状态/代际检查，读回真实回执及失败；已有路径优先。

## 约束与交付

隔离 checkout、私有项目和 headless 验证；不接触正在运行的生产编辑器、原项目、483 配置历史队列 binding、候选或用户应用。禁止键鼠/焦点劫持、文件注入、假历史及绕过授权。

已有5类人工确认操作保持人工确认；7类 OS/认证/视觉边界保留，不作为模型自我授权。系统权限、登录秘密、支付、纯视觉判断不旁路。实现需独立审查、编译和原生业务夹具；逐项记录已修、未覆盖与未知。提交通过正式门禁、签名 PR、精确 CI 及 main 回读才算交付，部分完成不能报告全部完成。

## 已实现接口和真实范围

本需求的正式工单为 [#559](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/559)。原审计分类保留在 `data-collection/requests/editor-command-gaps-batch-20261108/baseline-inventory.json`。所有新操作经现有权限/咨询策略及真实宿主确认路径，JSON中的source、confirmed和旧快照都不产生权限。

| 原清单项 | 新声明式接口 | 实际边界 |
| --- | --- | --- |
| 父会话关闭/重命名 | chat_sessions / chat_close_session(agent_id) / chat_rename_session(agent_id,value) | 关闭包含真实历史删除，需新人工确认；托管验收子不能被直接改名/关闭 |
| 普通手动子会话 | chat_create_child(parent_id) / chat_close_session | 精确当前顶层父、层级/容量检查；专用review流程保持独立 |
| 定时任务生命周期 | chat_schedules / chat_schedule_create,update,delete,enable,run,select | 稳定schedule_id；定义含title,prompt,frequency,unit；立即运行的业务完成另验 |
| 模型/推理 | chat_configuration / chat_set_model_id / chat_set_reasoning | reasoning只能选实际广告元数据，不修改凭据或工具策略 |
| 运行路径/CLI | chat_set_runtime_field / chat_set_cli_path | node,codex,workflow_python,build_python走共享环境锁；CodeBuddy入口仅已有绝对JS文件并绑定内容摘要 |
| 图片附件 | chat_attachments / chat_attachment_add,paste,remove / chat_send_message | 文件16MiB；先用原生header-only API限制8192边长、32M像素再解码；clipboard只读图像；编码预算沿原生；发送绑定实际附件和空正文草稿 |
| 2D/3D空间 | viewport_state,set_view,pick,selection_state,transform_selection | 真实native相机与world/local/view单选Node3D delta；ray仅可见原生静态mesh三角形；已有scene属性写可设对象绝对变换 |
| 动画轨道关键帧 | animation_state,add_track,remove_track,insert_key,remove_key,move_key,select_keys,copy_keys,cut_keys,paste_keys | native有限轨道/类型；实际当前时间轴选择；typed内部clipboard不碰OS；导入/压缩/事件轨道/资源值等拒绝 |
| TileMap/多边形 | tilemap_state,set_cells / polygon_state,set_points | 显式atlas cells及256点native Polygon2D/CollisionPolygon2D；不注入自由手势 |
| 复合/自绘控件 | read_tree_cells/edit_tree_cell；read_richtext_links/activate_richtext_link；read_semantic_actions/invoke_semantic_action | 复合控件声明只映射已有原生后代动作；没有任意method/signal入口；未适配的纯自绘插件内部仍未覆盖 |
| 运行中游戏输入 | game_input_query / game_input_state / game_action_pulse | 真实debugger peer+代际+runtime token；独立InputMap动作源，限时自动释放，保留物理/API输入；不注入键鼠/手柄OS事件 |
| 菜单/截图 | read_menubar_menus/open_menubar_menu；capture_editor | 截图只捕获编辑器viewport，人工确认，生成PNG路径/摘要；headless明确不可用；不声称含OS全局菜单或嵌入游戏叠图 |
| 本地修改历史 | chat_history / chat_show_history / chat_show_changes | 本会话真实snapshot ID与原生浏览页；不伪造历史，不授予还原权限 |
| 挂载宿主聊天 | chat_host_context / chat_host_send_message | 实际Control/tree/composer父、会话/代际、Issue/request/candidate owner重验，再走普通_send；不放宽554专用入口 |
| CodeBuddy只读子验收 | delegate_review / get_parent_context | native父→子→父；写、真实shell、构建、再委派拒绝；同ACP会话不能升级权限；原生Glob/Grep关闭，读取经宿主 |

### 参数与回执

宿主chat写动作保留`manual_confirmation_required`，所有新增空间写也需新人工确认。`chat_*`仅外部host路由可达，模型不能凭action字符串直接取得宿主权限。现有自动执行不批准这些真人边界。

空间命令target为当前编辑场景内路径；`dimension`是2d/3d；相机`index`为0..3。`viewport_pick`的value为world-space origin/direction/max_distance；`viewport_transform_selection`为mode/space/delta。TileMap使用顶层`cells:[{coords,source_id,atlas_coords,alternative}]`；动画copy/cut/select使用顶层keys，paste使用`value:{keys,offset}`，add_track使用track_type/path/property。明确返回不支持的对象、类型、容量、播放/恢复状态和漂移，不能以文件修改假装实时编辑成功。

游戏pulse的value含`name,duration(0.01..2),strength(0..1],request_id,runtime_token`；query先观察实际runtime，state回读generation及真实接收/释放回执。定时基于游戏主循环的unscaled timer，调试断点会推迟timer和完成回执；没有硬件/墙钟实时保证。`requested`/`send_requested`与`business_completed:false`只表示请求送达，不等于任务完成。

复合声明元数据格式为`ai_control_semantic_actions:[{name,target:相对后代路径,action:已支持原生动作}]`。调用为`invoke_semantic_action(value:{name,arguments})`；仅允许原生输入字段，拒绝父级/同级路径、递归别名和任意方法名。声明、实际子对象和全部旧状态在确认后重验，不字符串化未验证Object元数据。

### 仍未覆盖及验收边界

此批实现不是所有窗口、所有插件和所有原生手势的全覆盖。纯自绘插件内部需各自真实适配；2D几何拾取、多选/子gizmo、蒙皮/粒子/插件拾取、动画事件/音频/bezier/压缩轨道、TileMap terrain/scene collection及多边形孔洞等没有由本批开放。运行游戏仅有InputMap语义pulse，不提供原始键鼠/手柄事件。

真实账号/provider、真实剪贴板图片、生产历史差异、GUI截图像素及macOS全局菜单视觉、IME/焦点/硬件仍按证据分别保留未知。非空历史diff已通过私有candidate的实际native write_file创建真实snapshot并打开真实差异页验证，未伪造历史。私有夹具的provider/工单/账号是明确mock，模拟宿主确认信号不是真人批准。只读限制不等于独立OS沙箱或绝对凭据读取隔离。5类原人工确认和7类OS/认证/视觉边界仍保留，未绕过。

验证记录的编译artifact、源manifest、测试组和独立审查见同需求data-collection目录。已实现接口、静态核查、私有原生测试、真实生产验收、CI、签名交付与main回读分别记录。原#483生产编辑器/owner/项目/队列/历史和用户应用均不由本任务修改或重启。

## CI修正来源

首个签名候选c8a966（作者40b89ac）在PR #564的静态与Windows严格编译检查失败，未合入。修正importlib loader空值保护、规范include/版权头、继承成员同名局部变量以及有界计数的整数符号比较；未放宽警告、权限或CI。原始测试/独立审查原件保留，增量证明及必要重编/复验另存ci-correction-validation.json与ci-correction-independent-review.json。远端成功、main合入及原单整体验收仍各自需要真实回执。

第二个签名候选d539e1（作者43ea5069，PR #565）的静态检查、clang-cl编辑器和导出模板已通过，但MSVC编辑器在新动作列表分页报C4701。另加offset/limit显式初始化及四个实际原生断言；msvc-init-validation.json与独立增量审查保留这个失败及后继验证，不覆盖旧报告，不放宽编译警告。

第三个候选374cdb（PR #566）未合入：MSVC编辑器在Polygon2D/CollisionPolygon2D相邻分支发现C4456，修正仅为后一局部变量更名。同时独立实际原生检查复现SceneTreeEditor通用Tree单元格编辑可经自动执行绕过专用场景改名的真人确认。新增保护按真实SceneTreeEditor祖先及原生回调所有者拒绝该通用写入口，提示使用已有scene_rename_node；普通Tree仍保留原有行为。5组原生回归覆盖专用确认、普通Tree、重挂载和复合声明，原始发现及修复独立证据另存tree-boundary-*，不覆盖早期审查。额外-Wshadow-all探测在未修改的dynamic_bvh.h既有字段遮蔽处失败，未修改该无关文件，亦不记为通过；常规构建和实际后继CI分别核验。

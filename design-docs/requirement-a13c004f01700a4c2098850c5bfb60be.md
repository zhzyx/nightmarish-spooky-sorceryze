# 将 AIChat 置于编辑器最左侧

<!-- gonggong-request:requirement-a13c004f01700a4c2098850c5bfb60be -->

Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/58 。路径基准：本工作副本仓库根。

原始目标：将 AIChat 相关界面元素调整到最左侧，并在保存布局、重启后保持。评论 6637202998 明确目标为顶部主屏标签栏中 2D 左侧；后续 6637588160、6637614630 延续仅排序、不迁移 Dock、其他同级顺序及功能不变的限制。中途泛化评论不覆盖此前已明确的目标。

本次交付：现有排序实现的专项回归源码、澄清文档和证据。基线锁定 1b0a33fd；Windows x86_64 编辑器，复用协调者提供、独立校验 SHA 的已安装 main 二进制，不新增引擎编译。现有 editor/editor_node.cpp 已先注册 AIChatDock 再注册 2D/3D/Script；无需重复排序补丁。受影响模块仅 tests/editor 和本需求记录，不写其他工作副本。

验收与停止条件：AI Chat 主屏标签为第一项、几何位置位于 2D 左侧；逐项切换全部同级标签后可回到 AI Chat 输入区；正常关闭实际保存 editor_layout.cfg，连续两次独立进程重启后可见标签与保存顺序均保持。上述证据满足即停止实现，不扩展架构。headless 专项不覆盖外观截图、真实远端模型调用、所有用户自定义布局、其他平台或编译器。

验证命令：`python tests/editor/run_ai_chat_tab_order.py --godot <isolated-copy.exe> --report <new-report.json>`。持久报告路径均以仓库根解析，见 data-collection/issue58-tab-order/summary.json 及 main-ready.json。测试程序启动隔离临时项目和隔离用户配置，不操作已安装用户窗口。

当前结论：锁定 main 已满足排序、同级切换及保存重启要求；只交付回归与证据。远端状态、独立批准、串行发布由协调者回读后处理，本记录不声称已关闭 Issue 或已合入。

补充复核：#56 candidate6 的两种复制入口均在60秒内未退出，保留 candidate6-final.json 与 candidate6-direct.json 为失败证据，未归因为排序缺陷、未宣称该候选通过；该候选后续复核归 #56/#55。初始 runtime.json 为夹具临时目录权限失败留下的 running 状态，并非实际运行或通过；main-ready.json 是当前交付脚本的实际成功证据。

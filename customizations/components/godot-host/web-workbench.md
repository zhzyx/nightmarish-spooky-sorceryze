# Godot 内嵌 Web 工作台

路径均相对仓库根。需求与验收追踪：#1454，`design-docs/godot-web-platforms-20261118.md`。

## 使用

macOS 和 Windows 图形编辑器的主工作区新增「天璇」页签。输入现有天璇站点的 HTTPS 地址，点击「连接」，即可使用该站点提供的文曲、需求、工单、多宝、搜索、账号及设置。地址保存在本机编辑器设置 `network/web_platform/url`，多个项目共用；不填写令牌、账号密码或查询参数。本机开发服务允许 `http://localhost`、`http://127.0.0.1` 和 `http://[::1]`。

这是完整站点的原生浏览视图，网站功能、账号权限与服务部署保持由原平台管理。登录 Cookie 与站点存储使用当前系统用户的浏览器数据目录：macOS 使用 WebKit 应用身份，Windows 使用 LocalAppData/Godot/WebPlatform/WebView2；不写入项目或仓库。退出登录使用站点入口。按钮提供后退、前进及刷新／重试；切换编辑器页签隐藏浏览视图。网页不具有本机命令执行桥。

导航与新窗口限制在配置地址的同一来源；不同域名、协议或端口的单点登录及外部链接会被阻止。需要这些能力的部署须单独明确接入范围。上传使用系统文件面板；macOS 下载须选择不存在的文件名，已有文件不覆盖，Windows 下载使用 WebView2 标准界面。macOS 11.0–11.2 可浏览页面，下载需要 macOS 11.3 或更新版本。

## 当前支持范围

macOS 使用系统 WKWebView；Windows 的 MSVC / clang-cl 编辑器使用 WebView2。Windows 需要已安装的 Microsoft Edge WebView2 Evergreen Runtime，编辑器包须同时包含相同架构的 WebView2Loader.dll 和许可证文件；缺失或版本过旧时显示修复提示，点击刷新／重试重新初始化。编辑器本身不会下载或安装运行时。Linux 和 Windows MinGW 构建显示尚不支持提示。后台模式保留编辑器入口、布局与设置，不创建原生浏览器。真实显示器上的输入法、焦点、文件面板，以及生产 HTTPS 登录，需要分别验收。

编译 macOS 编辑器沿仓库 SCons 流程，`editor/docks/SCsub` 仅在 macOS 编译 Objective-C++ 后端，`platform/macos/detect.py` 仅为编辑器链接 WebKit。Windows 编辑器构建前运行 `python tools/install_webview2.py` 获取摘要固定的官方 SDK；SCons 只验证本地依赖并把 loader 与许可证复制到 bin，不在探测构建图时联网。详见 `thirdparty/webview2/README.md`。其他平台保留可链接的空工厂。此变更不替换有效安装、服务或数据库；回退可关闭工作台或使用保留的旧编辑器。

## 静默验证

以下测试使用隔离目录和构建，不切换用户桌面或键鼠焦点：

- `tests/editor/TestWebPlatformPolicy.cc` 与 `editor/docks/WebPlatformNative.cpp` 独立编译，验证来源解析、危险 URL、同源策略与下载来源。
- `tests/editor/TestWebPlatformMacOS.mm` 与原生后端独立编译为测试 app；其 bundle ID 必须以 `org.godotengine.webplatform.validation.` 开头，避免使用正常编辑器的浏览数据。传入隔离 HTTP 服务根地址，验证隐藏 NSWindow 内的真实 WKWebView、页面路径、缩放、隐藏、存储恢复、站外拦截和销毁。附加任一第三参数时要求真实天璇页面有标题、没有错误页，且隔离文档列表包含 `Godot native integration proof`。该文档只能在测试数据库准备，不能写入生产数据。
- Windows 在 MSVC developer shell 运行 `python tools/test_web_platform_windows.py --build-dir .godot/webview2-test --report .godot/webview2-test/result.json`。夹具使用不可见 HWND、隔离临时 profile 与两个本机来源，验证实际 DOM、历史、持久化、来源拒绝、布局、销毁和 renderer 崩溃后的显式重试；缺少 Runtime 会失败，不当作跳过成功。CI 只在临时 Windows runner 安装已核验微软签名的官方 Runtime。
- `tests/editor/web_platform_dock.gd` 是 EditorPlugin 探针。复制到临时项目的 `addons/web_platform/probe.gd`，用 `plugin.cfg` 启用；使用独立 self-contained 编辑器构建执行 `--headless --editor --path 临时项目`，避免改写正常用户设置。断言工作区入口、地址校验、设置、多尺寸布局及显示切换，输出 `WEB_PLATFORM_DOCK_OK` 后正常退出。不要用 `--script` 替换编辑器主循环。

测试程序使用实际后端；静默测试不等于已验证真实显示器交互，也不代表已接入生产服务。

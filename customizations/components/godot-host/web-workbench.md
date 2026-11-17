# Godot 内嵌 Web 工作台

路径均相对仓库根。需求与验收追踪：#1454，`design-docs/godot-web-platforms-20261118.md`。

## 使用

macOS 图形编辑器的主工作区新增「天璇」页签。输入现有天璇站点的 HTTPS 地址，点击「连接」，即可使用该站点提供的文曲、需求、工单、多宝、搜索、账号及设置。地址保存在本机编辑器设置 `network/web_platform/url`，多个项目共用；不填写令牌、账号密码或查询参数。本机开发服务允许 `http://localhost`、`http://127.0.0.1` 和 `http://[::1]`。

这是完整站点的原生浏览视图，网站功能、账号权限与服务部署保持由原平台管理。登录 Cookie 与站点存储保存在 WebKit 的应用数据目录，使用当前 macOS 用户和编辑器应用身份，不写入项目或仓库。退出登录使用站点入口。按钮提供后退、前进及刷新／重试；切换编辑器页签隐藏浏览视图。网页不具有本机命令执行桥。

导航与新窗口限制在配置地址的同一来源；不同域名、协议或端口的单点登录及外部链接会被阻止。需要这些能力的部署须单独明确接入范围。下载和上传通过系统文件面板选择文件；下载须选择不存在的文件名，已有文件不覆盖。macOS 11.0–11.2 可浏览页面，下载需要 macOS 11.3 或更新版本。

## 当前支持范围

已实现 macOS WKWebView 后端，使用系统 WebKit.framework，无需额外浏览器运行时。Windows 和 Linux 显示尚不支持提示，未宣称已实现嵌入。后台模式保留编辑器入口、布局与设置，不创建原生浏览器。真实显示器上的输入法、焦点、文件面板，以及生产 HTTPS 登录，需要分别验收。

编译 macOS 编辑器沿仓库 SCons 流程，`editor/docks/SCsub` 仅在 macOS 编译 Objective-C++ 后端，`platform/macos/detect.py` 仅为编辑器链接 WebKit。其他平台保留可链接的空工厂。此变更不替换有效安装、服务或数据库；回退可关闭工作台或使用保留的旧编辑器。

## 静默验证

以下测试使用隔离目录和构建，不切换用户桌面或键鼠焦点：

- `tests/editor/TestWebPlatformPolicy.cc` 与 `editor/docks/WebPlatformNative.cpp` 独立编译，验证来源解析、危险 URL、同源策略与下载来源。
- `tests/editor/TestWebPlatformMacOS.mm` 与原生后端独立编译为测试 app；其 bundle ID 必须以 `org.godotengine.webplatform.validation.` 开头，避免使用正常编辑器的浏览数据。传入隔离 HTTP 服务根地址，验证隐藏 NSWindow 内的真实 WKWebView、页面路径、缩放、隐藏、存储恢复、站外拦截和销毁。附加任一第三参数时要求真实天璇页面有标题、没有错误页，且隔离文档列表包含 `Godot native integration proof`。该文档只能在测试数据库准备，不能写入生产数据。
- `tests/editor/web_platform_dock.gd` 是 EditorPlugin 探针。复制到临时项目的 `addons/web_platform/probe.gd`，用 `plugin.cfg` 启用；使用独立 self-contained 编辑器构建执行 `--headless --editor --path 临时项目`，避免改写正常用户设置。断言工作区入口、地址校验、设置、多尺寸布局及显示切换，输出 `WEB_PLATFORM_DOCK_OK` 后正常退出。不要用 `--script` 替换编辑器主循环。

测试程序使用实际后端；静默测试不等于已验证真实显示器交互，也不代表已接入生产服务。

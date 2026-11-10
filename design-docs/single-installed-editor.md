# Windows 共工编辑器统一安装

关联 [工单 #722](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/722)，需求标识 `single-installed-editor`。

普通 Windows 入口使用主工作区 `project/godot/bin` 下同一经过校验的安装。安装时核对远端 main 及成功构建回执，启动时核对本地安装文件摘要。构建槽位与工作树只用于验证，构建时间不能决定默认版本。

维护者同步主检出，更新实际安装与桌面快捷方式，核对编辑器、工作台和控制台路径。清理范围限于已识别的旧安装和快捷方式，保留活跃工作树与用户工程。源代码交付及本机安装、清理回执分别在本工单跟踪。

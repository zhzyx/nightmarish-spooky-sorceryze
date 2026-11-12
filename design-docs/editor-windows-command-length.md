# Windows 原生命令的有界长脚本传输

需求：github:zhzyx/nightmarish-spooky-sorceryze#891；稳定标识 editor-windows-command-length-20261112，父项 #773。本文路径以仓库根解析。

## 来源与问题

真实父会话的一条约 12K 字符命令在 PowerShell UTF-16/Base64 包装后达到 32773 UTF-16 单元，未能启动。原请求与失败日志由父工单私有验收记录保留；不记录原始生产命令。12,000 个 Unicode 字符的工具输入限制仍有效，但不能据此推断 Windows 启动参数长度。

## 实现边界

修改既有 Godot 原生宿主，不新增模块或生产工具。输入是已批准的 pending_command、规范化 cwd、超时以及现有候选绑定。短包装器仍走 EncodedCommand；超过 4000 UTF-16 单元的包装器写到临时 UTF-8 ps1。脚本文本原样保存，包括原有 cwd、UTF-8 输出、try/catch、LASTEXITCODE 和 exit 包装。短小 EncodedCommand 在局部作用域读取并编译 ScriptBlock，然后在外层调用，避免加载器的 f/r/s 变量泄露。没有 -File 或 ExecutionPolicy 放宽。

Windows CREATE_NEW 原子建立新文件；写入句柄不继承，禁止其他写入和删除访问，FILE_FLAG_DELETE_ON_CLOSE 随最后句柄关闭清理。读取方只获取读权限并共享已有写/删除访问。创建、写入、flush、最终启动长度或启动失败沿原工具错误返回释放持有者；正常、异常、超时、取消和 dock 销毁同样释放。操作系统终止编辑器也关闭句柄。无权限或空间不足时拒绝且给出重试指导。

最终 argv 长度通过 OS_Windows 的实际 CRT 引号算法与 fix_path 计算，包含可执行文件、守卫参数和 NUL。超过 Windows 32767 单元时启动前拒绝，提示缩短目录或拆为分别批准的命令，不截断、不重写原批准内容。

现有候选校验、command_guard、恢复 journal、invocation 摘要、守卫结果、退出/超时/取消协议保持原路。临时路径只用于传输，恢复记录仍保存原请求，不以临时文件授权或恢复执行。

## 构建与回退

placement：native。实际编译输入为 editor/docks/ai_chat_dock.cpp/.h、platform/windows/os_windows.cpp/.h，经现有 SCsub 原生链接。宿主接口为现有 run_command。变更这些输入必须重建编辑器；不是可独立替换的运行包。严格 Windows editor tests=yes/warnings=extra/werror=yes 构建及同一候选实际原生循环验证在私有 bin/891-validation 留存，原始文件与二进制 SHA-256 随验证回执记录。回退恢复前一已验证二进制与对应源提交，保留原 journal 和采集记录。

## 验证与复盘

测试入口 tests/editor/run_ai_chat_integration.py --windows-commands 使用私有编辑器、离线 Issue/模型运输以及真实候选/来源守卫。验证短命令、超旧传输上限的 Unicode/引号脚本、带空格与单引号 cwd、stdout/stderr、exit7、throw、超时、取消和清理，以及明确输入上限；短长命令均检查加载器变量未泄露。工具实现没有测试旁路。

同域 editor-native-acceptance 的方法召回为空。复盘动作：Windows 命令预算按最终实际传输形式（UTF-16、编码、引号、守卫参数）计算；字符数不能替代最终长度；测例必须经过真实 native 工具循环。适用本 Windows 宿主；不能据此认定其他平台或其他 shell 的限制。可推翻试验是输入合法但最终参数越界，或短长两种路径出现输出、退出、来源保护差异。

全量既有 provenance guard 单测的 Windows 平台限制单独保留，不把 POSIX /bin/sh、killpg、macOS profile 断言或需要符号链接权限的用例视为本修复通过。选择可执行的真实删除/恢复、启动失败、退出、超时和无重放断言另行留证。

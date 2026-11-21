# D14 原生天璇业务身份

在 Godot 命令面板打开「Open AI Workbench」，点击侧栏的「天璇账号」。表单显示目标服务。填写邮箱、密码和业务项目即可登录；使用个人访问密钥时留空邮箱。成功后侧栏显示服务核实的姓名、角色和本次项目。再次打开表单即可换号或切换项目。点击「退出」会清空原生会话；密码登录取得的会话同时向原服务请求注销，个人密钥由签发者管理。[原工单 #1867](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867) · [D14 原始设计](gonggong-ai-workbench-plan1.md#d14)

服务地址取自启动环境的 `TIANXUAN_API`，默认 `http://127.0.0.1:8000`。远程服务使用 HTTPS。本地回环允许 HTTP。项目字段以 `TIANXUAN_PROJECT` 或天璇默认项目 `workspace` 初始化。既有启动器提供 `TIANXUAN_TOKEN` 时，侧栏仍先向服务验证实际身份。密码登录通过 `POST /api/v1/auth/session` 得到原生 Bearer 会话，两种凭据都经 `GET /api/v1/auth/me` 验证。交互输入的密码、会话和个人密钥仅限本次编辑器内存。重启后可重新登录。

## 业务请求

原生消费者从唯一的 `AIWorkbenchSidebar` 取得 `WorkbenchBusinessSession`。订阅 `identity_changed` 后用 `get_identity()` 回读可用身份，返回值包含 `id`、`name`、`role`、`project`。切换开始与新身份验证成功分别发出通知；消费者在旧身份清空时清理其私人内容、草稿和在途读回。通过 `await api_request(method, route, payload)` 发起同源请求，路径以 `/api/v1/` 开头，项目由会话追加到查询参数。服务按 Bearer 身份与当前权限处理请求。返回字典使用 `status` 和 `data`。网络失败、非法路由和身份变更后的迟到响应返回状态 0。401 清空身份并显示「凭据失效，请重新认证」，403 保留有效身份供继续只读工作。编辑器禁用 HTTP 重定向。[会话控件](../editor/docks/workbench/business_session.gd)

## 构建与复验

`editor/SCsub` 复用既有编辑器脚本生成器，把 `business_session.gd` 生成到 `BusinessSession.gen.h`。Windows、macOS 和 Linux 的侧栏 C++ 消费此头。更新需重新编译编辑器。回退采用上一已验证的编辑器二进制；天璇保留用户的私人工作位置。[侧栏挂载](../editor/docks/workbench/AIWorkbenchSidebar.cpp) · [构建定义](../editor/SCsub)

安装天璇服务测试依赖后，在隔离构建生成的编辑器上运行以下命令。探针从实际命令面板打开侧栏，在临时天璇服务创建管理员和只读用户，分别用密码与个人密钥登录，核对私人位置、项目隔离、在途回读、服务端拒绝写入、撤销后的原生提示及重新登录。它比较工程源文件原始摘要并检查项目和编辑器设置中的凭据字节。测试运行器自动清理临时服务和项目。

```sh
python tests/editor/run_workbench_business_session.py --godot <候选编辑器路径> --report <本地报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_account_registration.py customizations/components/tianxuan/server/test_module_locations.py
```

Mac 上两次既有回执覆盖账号、租户隔离和撤销后的服务行为。本卡 Windows 实测覆盖编辑器内的切号、重新认证提示与存储检查。[Mac 两账号回执](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7060361368) · [Mac 服务回归](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7062658872) · [候选与测试结果](../data-collection/gonggong-ai-workbench-plan1-d14.json)

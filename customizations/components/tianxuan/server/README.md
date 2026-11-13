# 天璇服务端

## 当前实现

`tianxuan_core.py`：标准库 + SQLite 的领域核心，可独立测试，不依赖网络与第三方包。

覆盖：注册/登录、文曲文档与版本、需求文档、司南工单与状态机、进度同步、事件流、AI 工具入口。

```sh
python -m unittest discover -s customizations/components/tianxuan/server -p "test_*.py" -v
```

## 目标技术栈

- FastAPI + PostgreSQL（生产）；SQLite 仅用于测试与嵌入式验证。
- SQLAlchemy 或 asyncpg 适配器；领域方法保持不变。
- Next.js 前端位于 `apps/tianxuan/`（后续切片）。

依赖在独立虚拟环境中安装，不污染 `project/runtime/python`；`requirements.txt` 在适配器落地时补齐。

## AI 工具面

`doc.create/update/read/list`、`requirement.create/plan`、`issue.create/transition/list`。
全部幂等、范围化、可审计；破坏性动作需平台策略门禁。

## 安全与边界

- 密码使用 PBKDF2-SHA256 + 随机盐；不存明文。
- 身份与权限由宿主/平台校验，领域层只做范围检查。
- 事件用于谛听回执与审计；不把凭据、提示词原文或本机路径写入事件。

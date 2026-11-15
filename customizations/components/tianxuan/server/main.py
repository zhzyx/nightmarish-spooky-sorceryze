"""Uvicorn 入口：通过环境变量选择 SQLite 文件并挂载模型网关与多宝合入队列。

用法：
    uvicorn main:app --host 127.0.0.1 --port 8000

``TIANXUAN_PROTECTED_BRANCHES`` 接受逗号分隔的保护分支模式（支持 ``fnmatch``
通配符，例如 ``main,release/*``）；受保护分支只能经多宝合入队列写入。
"""

import os
import shlex

from api import create_app
from duobao_bridge import GitService, PolicyError, parse_protected_branches
from gateway import ModelGateway
from merge_queue import MergeQueue
from tianxuan_core import Tianxuan

_DB_PATH = os.environ.get("TIANXUAN_DB", "tianxuan.db")
_GATEWAY_DB = os.environ.get("TIANXUAN_GATEWAY_DB", ":memory:")
_CHECKS = [shlex.split(part) for part in os.environ.get("TIANXUAN_MERGE_CHECKS", "").split(";") if part.strip()]
try:
    _PROTECTED_BRANCHES = parse_protected_branches(os.environ.get("TIANXUAN_PROTECTED_BRANCHES", ""))
except PolicyError as error:
    raise RuntimeError(f"invalid TIANXUAN_PROTECTED_BRANCHES: {error}") from error


def _required_approvals() -> int:
    raw = os.environ.get("TIANXUAN_REQUIRED_APPROVALS", "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"TIANXUAN_REQUIRED_APPROVALS must be a non-negative integer: {raw!r}") from error
    if value < 0:
        raise RuntimeError(f"TIANXUAN_REQUIRED_APPROVALS must be a non-negative integer: {raw!r}")
    return value


_REQUIRED_APPROVALS = _required_approvals()
_REQUIRED_CHECKS = tuple(
    item.strip() for item in os.environ.get("TIANXUAN_REQUIRED_CHECKS", "").split(",") if item.strip()
)

_STORE = Tianxuan(_DB_PATH)
_MERGE_QUEUE = MergeQueue(
    _DB_PATH,
    GitService(),
    checks=_CHECKS,
    protected_branches=_PROTECTED_BRANCHES,
    role_resolver=_STORE.role_of,
)
if os.environ.get("TIANXUAN_MERGE_WORKER", "1") != "0":
    _MERGE_QUEUE.start_worker()

if os.environ.get("TIANXUAN_EVENT_RETENTION_DAYS"):
    try:
        _STORE.prune_all_events(int(os.environ["TIANXUAN_EVENT_RETENTION_DAYS"]))
    except ValueError:
        pass

app = create_app(
    _STORE,
    gateway=ModelGateway(_GATEWAY_DB),
    merge_queue=_MERGE_QUEUE,
    protected_branches=_PROTECTED_BRANCHES,
    required_approvals=_REQUIRED_APPROVALS,
    required_checks=_REQUIRED_CHECKS,
)

"""Uvicorn 入口：通过环境变量选择 SQLite 文件并挂载模型网关与多宝合入队列。

用法：
    uvicorn main:app --host 127.0.0.1 --port 8000
"""

import os
import shlex

from api import create_app
from duobao_bridge import GitService
from gateway import ModelGateway
from merge_queue import MergeQueue
from tianxuan_core import Tianxuan

_DB_PATH = os.environ.get("TIANXUAN_DB", "tianxuan.db")
_GATEWAY_DB = os.environ.get("TIANXUAN_GATEWAY_DB", ":memory:")
_CHECKS = [shlex.split(part) for part in os.environ.get("TIANXUAN_MERGE_CHECKS", "").split(";") if part.strip()]

app = create_app(
    Tianxuan(_DB_PATH),
    gateway=ModelGateway(_GATEWAY_DB),
    merge_queue=MergeQueue(_DB_PATH, GitService(), checks=_CHECKS),
)

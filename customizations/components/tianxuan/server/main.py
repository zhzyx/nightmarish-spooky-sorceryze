"""Uvicorn 入口：通过环境变量选择 SQLite 文件并挂载模型网关。

用法：
    uvicorn main:app --host 127.0.0.1 --port 8000
"""

import os

from api import create_app
from gateway import ModelGateway
from tianxuan_core import Tianxuan

_DB_PATH = os.environ.get("TIANXUAN_DB", "tianxuan.db")
_GATEWAY_DB = os.environ.get("TIANXUAN_GATEWAY_DB", ":memory:")

app = create_app(Tianxuan(_DB_PATH), gateway=ModelGateway(_GATEWAY_DB))

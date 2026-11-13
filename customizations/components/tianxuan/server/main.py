"""Uvicorn 入口：通过环境变量选择 SQLite 文件。

用法：
    uvicorn main:app --host 127.0.0.1 --port 8000
"""

import os

from api import create_app
from tianxuan_core import Tianxuan

app = create_app(Tianxuan(os.environ.get("TIANXUAN_DB", "tianxuan.db")))

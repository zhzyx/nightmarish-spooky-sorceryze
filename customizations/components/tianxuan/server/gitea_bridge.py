"""桥接同级 duobao 模块的 Gitea 客户端；集中处理路径。"""

import sys
from pathlib import Path

_DUOBAO_DIR = Path(__file__).resolve().parents[1] / "duobao"
if str(_DUOBAO_DIR) not in sys.path:
    sys.path.insert(0, str(_DUOBAO_DIR))

from gitea_client import GiteaClient, GiteaError  # noqa: E402

__all__ = ["GiteaClient", "GiteaError"]

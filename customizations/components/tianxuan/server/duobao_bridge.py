"""桥接同级 duobao 模块；集中处理路径，避免 api.py 散落 sys.path 逻辑。"""

import sys
from pathlib import Path

_DUOBAO_DIR = Path(__file__).resolve().parents[1] / "duobao"
if str(_DUOBAO_DIR) not in sys.path:
    sys.path.insert(0, str(_DUOBAO_DIR))

from git_service import GitService, GitServiceError  # noqa: E402

__all__ = ["GitService", "GitServiceError"]

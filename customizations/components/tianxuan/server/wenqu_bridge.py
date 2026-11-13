"""桥接同级 wenqu 模块；集中处理路径，避免 api.py 散落 sys.path 逻辑。"""

import sys
from pathlib import Path

_WENQU_DIR = Path(__file__).resolve().parents[1] / "wenqu"
if str(_WENQU_DIR) not in sys.path:
    sys.path.insert(0, str(_WENQU_DIR))

from wenqu import build_ai_index, classify, export_markdown, search  # noqa: E402

__all__ = ["build_ai_index", "classify", "export_markdown", "search"]

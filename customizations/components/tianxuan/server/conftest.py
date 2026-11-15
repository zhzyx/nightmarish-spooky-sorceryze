"""服务端测试的公共环境。

既有 API 测试使用 ``X-Actor`` 作为简化身份；生产默认关闭该兼容入口，因此测试在
这里显式开启。认证模式测试会自行删除该变量以验证默认行为。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _allow_actor_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_ALLOW_ACTOR_HEADER", "1")

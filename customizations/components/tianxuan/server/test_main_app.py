"""入口应用测试：默认挂载模型网关且健康检查可用。"""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def test_main_app_mounts_model_gateway(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TIANXUAN_DB", str(tmp_path / "main.db"))
    monkeypatch.setenv("TIANXUAN_GATEWAY_DB", ":memory:")
    import main

    module = importlib.reload(main)
    client = TestClient(module.app)

    assert client.get("/api/v1/health").status_code == 200
    usage = client.get("/api/v1/models/usage", params={"tenant_id": "ten_demo"})
    assert usage.status_code == 200
    assert usage.json()["totals"]["cost_micros"] == 0

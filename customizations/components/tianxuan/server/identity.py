"""可插拔外部身份适配器。

身份只负责把外部主体（GitHub 用户、Tianshu 协作者、OIDC sub 等）解析到本地用户；
具体身份来源由适配器实现，核心与桥接不绑定 Git 或某个具体系统。
"""

from __future__ import annotations

import hmac
import os
from typing import Protocol


class IdentityAdapter(Protocol):
    """外部身份校验适配器。"""

    name: str

    def verify(self, subject: str, secret: str) -> bool:
        """校验外部主体与凭据；通过后由核心按 (provider, subject) 查绑定。"""
        ...


class StaticIdentityAdapter:
    """本地/测试用：显式打开后，subject 直接作为外部主体（仍须先绑定）。"""

    name = "static"

    def verify(self, subject: str, secret: str) -> bool:
        return bool(subject) and os.environ.get("TIANXUAN_ALLOW_STATIC_IDENTITY") == "1"


class SharedSecretIdentityAdapter:
    """共享密钥适配器：适用于 Tianshu 宿主或内部服务间身份。"""

    def __init__(self, name: str, env_name: str) -> None:
        self.name = name
        self._env_name = env_name

    def verify(self, subject: str, secret: str) -> bool:
        expected = os.environ.get(self._env_name, "")
        return bool(subject) and bool(expected) and bool(secret) and hmac.compare_digest(secret, expected)


_ADAPTERS: dict[str, IdentityAdapter] = {
    adapter.name: adapter
    for adapter in (
        StaticIdentityAdapter(),
        SharedSecretIdentityAdapter("tianshu", "TIANXUAN_IDENTITY_SECRET"),
        SharedSecretIdentityAdapter("github", "TIANXUAN_GITHUB_IDENTITY_SECRET"),
        SharedSecretIdentityAdapter("oidc", "TIANXUAN_OIDC_IDENTITY_SECRET"),
    )
}


def get_identity_adapter(name: str) -> IdentityAdapter | None:
    return _ADAPTERS.get(name.strip())


def adapter_names() -> list[str]:
    return sorted(_ADAPTERS)

"""可插拔外部身份适配器。

身份只负责把外部主体（GitHub 用户、Tianshu 协作者、OIDC sub 等）解析到本地用户；
具体身份来源由适配器实现，核心与桥接不绑定 Git 或某个具体系统。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.request
from collections import deque
from typing import Any, Protocol


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


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
_JWKS_CACHE: tuple[float, dict[str, Any]] = (0.0, {})


def _int_from_b64url(value: str) -> int:
    return int.from_bytes(_b64url_decode(value), "big")


def _load_jwks() -> dict[str, Any]:
    global _JWKS_CACHE
    raw = os.environ.get("TIANXUAN_OIDC_JWKS", "")
    if raw:
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else {}
        except ValueError:
            return {}
    url = os.environ.get("TIANXUAN_OIDC_JWKS_URL", "")
    if not url:
        return {}
    now = time.monotonic()
    cached_at, cached = _JWKS_CACHE
    if cached and now < cached_at:
        return cached
    try:
        with urllib.request.urlopen(url, timeout=3.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return cached or {}
    if not isinstance(payload, dict):
        return {}
    _JWKS_CACHE = (now + 300.0, payload)
    return payload


def _rs256_verify(signing_input: bytes, signature: bytes, jwks: dict[str, Any], kid: str) -> bool:
    keys = jwks.get("keys", [])
    if not isinstance(keys, list):
        return False
    candidates = [
        key for key in keys if isinstance(key, dict) and key.get("kty") == "RSA" and (not kid or key.get("kid") == kid)
    ]
    if kid and not candidates:
        return False
    for key in candidates:
        try:
            modulus = _int_from_b64url(str(key["n"]))
            exponent = _int_from_b64url(str(key["e"]))
        except (KeyError, ValueError, binascii.Error):
            continue
        size = (modulus.bit_length() + 7) // 8
        if len(signature) != size:
            continue
        try:
            decoded = pow(int.from_bytes(signature, "big"), exponent, modulus).to_bytes(size, "big")
        except (ValueError, OverflowError):
            continue
        if decoded[:2] != b"\x00\x01":
            continue
        rest = decoded[2:]
        separator = rest.find(b"\x00")
        if separator < 8 or any(byte != 0xFF for byte in rest[:separator]):
            continue
        expected = _SHA256_DIGEST_INFO + hashlib.sha256(signing_input).digest()
        if hmac.compare_digest(rest[separator + 1 :], expected):
            return True
    return False


class OidcJwtIdentityAdapter:
    """HS256 签名的 OIDC/JWT 适配器。

    密钥来自部署环境，token 由 OIDC 提供方签发；校验 alg、签名、sub、exp，
    可选校验 iss/aud。RS256/JWKS 适配器可在不改核心的前提下替换本类。
    """

    name = "oidc"

    def verify(self, subject: str, secret: str) -> bool:
        if not secret:
            return False
        parts = secret.split(".")
        if len(parts) != 3:
            return False
        try:
            header = json.loads(_b64url_decode(parts[0]))
            claims = json.loads(_b64url_decode(parts[1]))
            signature = _b64url_decode(parts[2])
        except (ValueError, binascii.Error, UnicodeDecodeError):
            return False
        if not isinstance(header, dict):
            return False
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        algorithm = str(header.get("alg", ""))
        if algorithm == "HS256":
            signing_key = os.environ.get("TIANXUAN_OIDC_SECRET", "")
            if not signing_key:
                return False
            expected = hmac.new(signing_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                return False
        elif algorithm == "RS256":
            if not _rs256_verify(signing_input, signature, _load_jwks(), str(header.get("kid", ""))):
                return False
        else:
            return False
        if not isinstance(claims, dict) or str(claims.get("sub", "")) != subject:
            return False
        expires = claims.get("exp")
        if expires is not None:
            try:
                if float(expires) <= time.time():
                    return False
            except (TypeError, ValueError):
                return False
        issuer = os.environ.get("TIANXUAN_OIDC_ISSUER", "")
        if issuer and str(claims.get("iss", "")) != issuer:
            return False
        audience = os.environ.get("TIANXUAN_OIDC_AUDIENCE", "")
        if audience:
            aud: Any = claims.get("aud")
            values = aud if isinstance(aud, list) else [aud]
            if audience not in values:
                return False
        return True


_ADAPTERS: dict[str, IdentityAdapter] = {
    adapter.name: adapter
    for adapter in (
        StaticIdentityAdapter(),
        SharedSecretIdentityAdapter("tianshu", "TIANXUAN_IDENTITY_SECRET"),
        SharedSecretIdentityAdapter("github", "TIANXUAN_GITHUB_IDENTITY_SECRET"),
        OidcJwtIdentityAdapter(),
    )
}


def get_identity_adapter(name: str) -> IdentityAdapter | None:
    return _ADAPTERS.get(name.strip())


def adapter_names() -> list[str]:
    return sorted(_ADAPTERS)


class AttemptLimiter:
    """进程内滑动窗口限流；多个副本部署时各副本独立计数。"""

    def __init__(self, limit: int = 10, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, provider: str, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._events.setdefault((provider, key), deque())
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()
            if len(bucket) >= self._limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_ATTEMPT_LIMITER = AttemptLimiter(limit=30)


def allow_identity_attempt(provider: str, key: str) -> bool:
    return _ATTEMPT_LIMITER.allow(provider, key)


def reset_identity_attempts() -> None:
    _ATTEMPT_LIMITER.reset()


def encode_test_jwt(secret: str, claims: dict[str, Any], *, algorithm: str = "HS256") -> str:
    """仅用于测试/本地验证的 HS256 token 生成器。"""
    header = _b64url_encode(json.dumps({"alg": algorithm, "typ": "JWT"}).encode("utf-8"))
    payload = _b64url_encode(json.dumps(claims).encode("utf-8"))
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url_encode(signature)}"

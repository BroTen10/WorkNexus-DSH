"""无第三方依赖的 HS256 Access/Refresh Token 工具。

企业 Token 只用于企业控制面，不要求官方 DSH 会话请求携带（需求书 §3.3）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class TokenError(ValueError):
    """Token 无效或已过期。"""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _encode(secret: str, payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    payload_part = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signing_input = f"{header_part}.{payload_part}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url(signature)}"


def _decode(secret: str, token: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode()
        expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(signature_part)):
            raise TokenError("invalid token signature")
        payload = json.loads(_b64url_decode(payload_part))
        if not isinstance(payload, dict):
            raise TokenError("invalid token payload")
        if payload.get("exp") is not None and float(payload["exp"]) < time.time():
            raise TokenError("token expired")
        return payload
    except TokenError:
        raise
    except Exception as error:
        raise TokenError("invalid token") from error


def create_access_token(
    subject: str,
    secret: str,
    expires_minutes: int,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {"sub": subject, "typ": "access", "exp": time.time() + expires_minutes * 60}
    if extra:
        payload.update(extra)
    return _encode(secret, payload)


def create_refresh_token(subject: str, secret: str, expires_days: int) -> str:
    return _encode(secret, {"sub": subject, "typ": "refresh", "exp": time.time() + expires_days * 86400})


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    payload = _decode(secret, token)
    if payload.get("typ") != "access":
        raise TokenError("not an access token")
    return payload


def decode_refresh_token(token: str, secret: str) -> dict[str, Any]:
    payload = _decode(secret, token)
    if payload.get("typ") != "refresh":
        raise TokenError("not a refresh token")
    return payload

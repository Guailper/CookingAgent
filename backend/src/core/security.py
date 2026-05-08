"""安全相关工具函数。

当前先提供密码哈希校验和公共业务 ID 生成能力，
后续可以继续在这里扩展 JWT、签名和权限辅助方法。
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

PASSWORD_HASH_ALGORITHM = "sha256"
PASSWORD_HASH_ITERATIONS = 390000
TOKEN_SIGNING_ALGORITHM = "HS256"


class TokenValidationError(ValueError):
    """访问令牌校验失败时抛出的异常。"""


def _urlsafe_b64encode(data: bytes) -> str:
    """把字节编码成 URL 安全的 Base64 字符串。"""

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _urlsafe_b64decode(data: str) -> bytes:
    """把 URL 安全的 Base64 字符串还原成字节。"""

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def hash_password(password: str) -> str:
    """把明文密码转换成可存库的安全哈希值。"""

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        PASSWORD_HASH_ALGORITHM,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    """校验明文密码与数据库中的哈希值是否匹配。"""

    try:
        algorithm, iteration_text, salt, expected_digest = stored_hash.split("$", maxsplit=3)
    except ValueError:
        return False

    normalized_algorithm = algorithm.removeprefix("pbkdf2_")

    derived_digest = hashlib.pbkdf2_hmac(
        normalized_algorithm,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iteration_text),
    ).hex()
    return hmac.compare_digest(derived_digest, expected_digest)


def generate_public_id(prefix: str) -> str:
    """生成对外暴露的业务 ID，例如 user_xxx、conv_xxx。"""

    normalized_prefix = prefix.strip().lower()
    random_suffix = secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]
    return f"{normalized_prefix}_{random_suffix}"


def create_access_token(subject: str, secret_key: str, expires_minutes: int) -> str:
    """生成签名访问令牌。

    当前阶段使用标准库实现一个轻量令牌，先满足登录鉴权和接口联调需要。
    """

    issued_at = int(time.time())
    header = {"alg": TOKEN_SIGNING_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + expires_minutes * 60,
    }

    encoded_header = _urlsafe_b64encode(
        json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    encoded_payload = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    encoded_signature = _urlsafe_b64encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    """校验并解析访问令牌。"""

    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", maxsplit=2)
    except ValueError as exc:
        raise TokenValidationError("访问令牌格式不正确。") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = _urlsafe_b64encode(
        hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected_signature, encoded_signature):
        raise TokenValidationError("访问令牌签名校验失败。")

    try:
        payload = json.loads(_urlsafe_b64decode(encoded_payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TokenValidationError("访问令牌载荷无法解析。") from exc

    expire_at = payload.get("exp")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenValidationError("访问令牌缺少有效的用户标识。")
    if not isinstance(expire_at, int) or expire_at < int(time.time()):
        raise TokenValidationError("访问令牌已过期。")

    return payload

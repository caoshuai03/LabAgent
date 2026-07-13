"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 安全工具——密码哈希（Argon2）与 JWT 签发/解析
"""
import time

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_password_hasher = PasswordHasher()


def hash_password(raw_password: str) -> str:
    """使用 Argon2 对明文密码进行哈希。"""
    return _password_hasher.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """校验明文密码与 Argon2 哈希是否匹配。"""
    try:
        return _password_hasher.verify(hashed_password, raw_password)
    except VerifyMismatchError:
        return False
    except Exception:
        # 哈希格式非法等情况一律视为校验失败
        return False


def create_token(user_id: int) -> str:
    """基于用户 ID 签发 JWT。"""
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "iat": now,
        "exp": now + settings.jwt_ttl_seconds,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def parse_token(token: str) -> int | None:
    """解析 JWT，返回 user_id；无效或过期返回 None。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    user_id = payload.get("user_id")
    return int(user_id) if user_id is not None else None

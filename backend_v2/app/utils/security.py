"""
安全工具函数：密码哈希、JWT令牌等
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import jwt

from app.config import get_settings

settings = get_settings()


def _preprocess_password(password: str) -> bytes:
    """
    密码预处理：使用 SHA-256 哈希
    解决 bcrypt 72 字节限制问题，同时统一密码长度
    
    bcrypt 只能处理最多 72 字节的密码。通过先进行 SHA-256 哈希，
    我们得到固定 64 字符的十六进制字符串（64 字节），然后转换为 bytes。
    这样无论原密码多长，都能被 bcrypt 正确处理。
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def get_password_hash(password: str) -> str:
    """
    生成密码哈希
    
    流程：
    1. 使用 SHA-256 预处理密码（解决 72 字节限制）
    2. 使用 bcrypt 生成哈希（加盐 + 慢哈希）
    
    返回：bcrypt 哈希字符串（格式：$2b$12$...）
    """
    preprocessed = _preprocess_password(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(preprocessed, salt)
    return hashed.decode("utf-8")


def _bcrypt_checkpw(password: bytes, hashed_password: str) -> bool:
    """
    安全的 bcrypt 密码验证封装
    
    处理不同 bcrypt 版本的哈希前缀兼容性问题：
    - $2a$: 旧版 bcrypt
    - $2b$: 新版 bcrypt（修复了 8 位字符问题）
    - $2x$, $2y$: PHP 等其他实现
    
    bcrypt.checkpw 本身已经是时间常数比较，不会泄露时间信息。
    """
    try:
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password, hashed_bytes)
    except (ValueError, TypeError, Exception):
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    验证顺序（保持向后兼容）：
    1. 新格式：SHA-256 预处理 + bcrypt（当前推荐）
    2. 旧格式：纯 bcrypt（无预处理，用于兼容旧账户）
    
    返回：True 表示验证成功，False 表示失败
    """
    preprocessed = _preprocess_password(plain_password)
    
    if _bcrypt_checkpw(preprocessed, hashed_password):
        return True
    
    try:
        plain_bytes = plain_password.encode("utf-8")
        if _bcrypt_checkpw(plain_bytes, hashed_password):
            return True
    except Exception:
        pass
    
    return False


def needs_migration(plain_password: str, hashed_password: str) -> bool:
    """
    检查密码是否需要迁移到新格式
    
    判断逻辑：
    - 如果旧格式（纯 bcrypt）验证成功，但新格式（SHA-256 + bcrypt）验证失败
    - 说明该密码是用旧方式创建的，建议迁移
    
    返回：True 表示需要迁移，False 表示已经是新格式或验证失败
    """
    try:
        plain_bytes = plain_password.encode("utf-8")
        
        if _bcrypt_checkpw(plain_bytes, hashed_password):
            preprocessed = _preprocess_password(plain_password)
            
            if not _bcrypt_checkpw(preprocessed, hashed_password):
                return True
    except Exception:
        pass
    
    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码JWT令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.JWTError:
        return None

"""
安全工具函数：密码哈希、JWT令牌等
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _preprocess_password(password: str) -> str:
    """
    密码预处理：使用 SHA-256 哈希
    解决 bcrypt 72 字节限制问题，同时统一密码长度
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    先尝试新格式（SHA-256 + bcrypt），如果失败再尝试旧格式（纯 bcrypt）
    """
    preprocessed = _preprocess_password(plain_password)
    if pwd_context.verify(preprocessed, hashed_password):
        return True
    try:
        if pwd_context.verify(plain_password, hashed_password):
            return True
    except Exception:
        pass
    return False


def get_password_hash(password: str) -> str:
    """
    生成密码哈希
    使用 SHA-256 预处理后再用 bcrypt 哈希，解决 72 字节限制
    """
    preprocessed = _preprocess_password(password)
    return pwd_context.hash(preprocessed)


def needs_migration(plain_password: str, hashed_password: str) -> bool:
    """
    检查密码是否需要迁移到新格式
    如果旧格式（纯 bcrypt）验证成功但新格式失败，则需要迁移
    """
    try:
        if pwd_context.verify(plain_password, hashed_password):
            preprocessed = _preprocess_password(plain_password)
            if not pwd_context.verify(preprocessed, hashed_password):
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

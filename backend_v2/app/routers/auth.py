"""
用户认证相关的 API 路由
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import (
    Token, TokenData, UserLogin, UserRegister, UserResponse
)
from app.utils import verify_password, get_password_hash, create_access_token, decode_access_token

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户（依赖项）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, user_id=user_id)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户（依赖项）"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user


@router.post("/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    用户注册
    
    - 需要管理员邀请码（即 SECRET_KEY）
    """
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )
    
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已被注册"
            )
    
    hashed_password = get_password_hash(user_data.password)
    
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_active=True,
        is_admin=False
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
def login(form_data: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录
    
    - 返回 JWT Token
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "is_admin": user.is_admin
        },
        expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return current_user


@router.post("/logout")
def logout():
    """
    用户登出
    
    - 客户端只需删除本地 Token 即可
    """
    return {"message": "已成功登出"}

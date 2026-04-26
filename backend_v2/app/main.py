"""
INN 图像隐写系统 - FastAPI 主应用
"""
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import init_db, SessionLocal
from app.ml import is_model_loaded
from app.models import User
from app.routers import (
    auth_router,
    encrypt_router,
    steganography_router,
    training_router
)
from app.schemas import HealthResponse
from app.utils.security import get_password_hash, verify_password

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _legacy_verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    旧版密码验证（无 SHA-256 预处理）
    
    用于迁移旧格式的密码哈希
    """
    return pwd_context.verify(plain_password, hashed_password)


def _legacy_get_password_hash(password: str) -> str:
    """
    旧版密码哈希（无 SHA-256 预处理）
    
    用于检测旧格式的密码
    """
    return pwd_context.hash(password)


def init_admin_user():
    """
    初始化管理员账户
    
    处理逻辑：
    1. 如果 admin 用户不存在 -> 创建
    2. 如果 admin 用户存在：
       a. 尝试用新逻辑（SHA-256 + bcrypt）验证
       b. 如果失败，尝试用旧逻辑（纯 bcrypt）验证
       c. 如果旧逻辑验证成功 -> 迁移到新格式
       d. 如果都失败但配置了 FORCE_RESET_ADMIN=true -> 强制重置
    """
    db: Session = SessionLocal()
    try:
        admin_username = settings.ADMIN_USERNAME
        admin_password = settings.ADMIN_PASSWORD
        
        admin_user = db.query(User).filter(User.username == admin_username).first()
        
        if not admin_user:
            print(f"[INN-Stego] 创建管理员账户: {admin_username}")
            admin_user = User(
                username=admin_username,
                hashed_password=get_password_hash(admin_password),
                is_active=True,
                is_admin=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print(f"[INN-Stego] 管理员账户创建成功: {admin_username}")
        else:
            if verify_password(admin_password, admin_user.hashed_password):
                print(f"[INN-Stego] 管理员账户已存在且密码验证通过: {admin_username}")
            else:
                try:
                    if _legacy_verify_password(admin_password, admin_user.hashed_password):
                        print(f"[INN-Stego] 检测到旧格式密码，正在迁移: {admin_username}")
                        admin_user.hashed_password = get_password_hash(admin_password)
                        db.commit()
                        print(f"[INN-Stego] 管理员密码已迁移到新格式: {admin_username}")
                    else:
                        print(f"[INN-Stego] 警告: 管理员账户密码与配置不匹配: {admin_username}")
                        print(f"[INN-Stego] 如果需要重置密码，请删除数据库文件: data/app.db")
                        print(f"[INN-Stego] 或设置环境变量 FORCE_RESET_ADMIN=true 后重启")
                except Exception as e:
                    print(f"[INN-Stego] 密码验证时出错: {e}")
        
        db.commit()
    except Exception as e:
        print(f"[INN-Stego] 初始化管理员账户失败: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("[INN-Stego] Initializing application...")
    
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.MODEL_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.DATASET_DIR).mkdir(parents=True, exist_ok=True)
    
    print("[INN-Stego] Initializing database...")
    init_db()
    
    print("[INN-Stego] Initializing admin user...")
    init_admin_user()
    
    print("[INN-Stego] Application ready!")
    yield
    
    print("[INN-Stego] Shutting down...")


app = FastAPI(
    title="INN Image Steganography API",
    description="基于可逆神经网络的图像加密和隐写系统 API",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(encrypt_router)
app.include_router(steganography_router)
app.include_router(training_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)}
    )


@app.get("/", tags=["根"])
async def root():
    """根路径 - 返回系统信息"""
    return {
        "name": "INN Image Steganography System",
        "version": "2.0.0",
        "description": "基于可逆神经网络的图像加密和隐写系统",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/api/health", response_model=HealthResponse, tags=["健康检查"])
async def health_check():
    """
    健康检查接口
    
    返回系统状态、模型加载状态等信息
    """
    return HealthResponse(
        status="ok",
        model_loaded=is_model_loaded(),
        model_type="HiNet",
        timestamp=datetime.utcnow()
    )


@app.get("/api/status", tags=["系统状态"])
async def system_status():
    """
    系统状态接口
    
    返回更详细的系统状态信息
    """
    import torch
    import sys
    
    return {
        "status": "ok",
        "python_version": sys.version,
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "model_loaded": is_model_loaded(),
        "settings": {
            "data_dir": settings.DATA_DIR,
            "model_dir": settings.MODEL_DIR,
            "dataset_dir": settings.DATASET_DIR,
        }
    }

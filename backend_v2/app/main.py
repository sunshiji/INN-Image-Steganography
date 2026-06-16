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

from app.config import get_settings
from app.database import init_db
from app.ml import is_model_loaded
from app.routers import (
    auth_router,
    encrypt_router,
    steganography_router,
    training_router
)
from app.schemas import HealthResponse

settings = get_settings()


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

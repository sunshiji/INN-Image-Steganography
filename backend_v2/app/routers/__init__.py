"""
路由模块
"""
from app.routers.auth import router as auth_router
from app.routers.encrypt import router as encrypt_router
from app.routers.steganography import router as steganography_router
from app.routers.training import router as training_router

__all__ = [
    "auth_router",
    "encrypt_router",
    "steganography_router",
    "training_router"
]

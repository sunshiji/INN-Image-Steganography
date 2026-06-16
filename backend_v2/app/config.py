"""
应用配置管理
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = Field(default="sqlite:///./data/app.db")
    
    # JWT
    SECRET_KEY: str = Field(default="inn-stego-dev-secret-key-2024")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)
    
    # 管理员账户
    ADMIN_USERNAME: str = Field(default="admin")
    ADMIN_PASSWORD: str = Field(default="admin123")
    
    # 服务器
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    
    # 数据目录
    DATA_DIR: str = Field(default="./data")
    UPLOAD_DIR: str = Field(default="./data/uploads")
    MODEL_DIR: str = Field(default="./data/models")
    DATASET_DIR: str = Field(default="./data/datasets")
    
    # HiNet
    HINET_WEIGHTS_PATH: Optional[str] = Field(default=None)
    
    # 训练配置
    TRAINING_BATCH_SIZE: int = Field(default=8)
    TRAINING_EPOCHS: int = Field(default=1000)
    TRAINING_LR: float = Field(default=1e-5)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

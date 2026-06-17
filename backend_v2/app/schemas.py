"""
Pydantic 数据模型
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models import TaskType, TrainingStatus


# 认证相关
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


# 任务相关
class TaskBase(BaseModel):
    task_type: TaskType
    parameters: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskResponse(BaseModel):
    id: int
    user_id: Optional[int]
    task_type: TaskType
    psnr: Optional[float]
    ssim: Optional[float]
    entropy_original: Optional[float]
    entropy_encrypted: Optional[float]
    npcr: Optional[float]
    uaci: Optional[float]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# 加密相关
class EncryptRequest(BaseModel):
    r: float = Field(default=3.9991, ge=3.57, le=4.0)
    x0: float = Field(default=0.37291, ge=0, le=1)
    n0: int = Field(default=500, ge=0)
    rounds: int = Field(default=2, ge=1)


class EncryptResponse(BaseModel):
    encrypted_image: str
    key: dict
    metrics: dict


class DecryptRequest(BaseModel):
    r: float = Field(default=3.9991)
    x0: float = Field(default=0.37291)
    n0: int = Field(default=500)
    rounds: int = Field(default=2)
    H: int
    W: int
    C: int = 3


# 隐写相关
class EncodeResponse(BaseModel):
    stego_image: str
    stego_key: str
    recovery_image: str
    metrics: dict


class DecodeResponse(BaseModel):
    secret_image: str
    mode: str


# 训练相关
class TrainingConfig(BaseModel):
    job_name: str = Field(default="HiNet Training")
    epochs: int = Field(default=1000, ge=1)
    batch_size: int = Field(default=8, ge=1)
    learning_rate: float = Field(default=1e-5, ge=1e-7)
    val_freq: int = Field(default=20, ge=1)
    save_freq: int = Field(default=20, ge=1)
    dataset_path: Optional[str] = None


class TrainingJobResponse(BaseModel):
    id: int
    job_name: str
    description: Optional[str]
    status: TrainingStatus
    current_epoch: int
    total_epochs: int
    batch_size: int
    learning_rate: float
    best_psnr: Optional[float]
    best_ssim: Optional[float]
    best_loss: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TrainingProgress(BaseModel):
    job_id: int
    status: TrainingStatus
    current_epoch: int
    total_epochs: int
    current_loss: Optional[float]
    best_psnr: Optional[float]
    best_ssim: Optional[float]


# 健康检查
class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_type: str
    timestamp: datetime

"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    Text, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class TaskType(str, enum.Enum):
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    ENCODE = "encode"
    DECODE = "decode"
    PIPELINE_ENCRYPT_ENCODE = "pipeline_encrypt_encode"
    PIPELINE_DECODE_DECRYPT = "pipeline_decode_decrypt"


class TrainingStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    tasks = relationship("Task", back_populates="owner")
    training_jobs = relationship("TrainingJob", back_populates="owner")


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    
    input_image_path = Column(String(500), nullable=True)
    cover_image_path = Column(String(500), nullable=True)
    secret_image_path = Column(String(500), nullable=True)
    output_image_path = Column(String(500), nullable=True)
    
    parameters = Column(Text, nullable=True)
    
    psnr = Column(Float, nullable=True)
    ssim = Column(Float, nullable=True)
    entropy_original = Column(Float, nullable=True)
    entropy_encrypted = Column(Float, nullable=True)
    npcr = Column(Float, nullable=True)
    uaci = Column(Float, nullable=True)
    
    key_data = Column(Text, nullable=True)
    
    status = Column(String(50), default="completed")
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    owner = relationship("User", back_populates="tasks")


class TrainingJob(Base):
    __tablename__ = "training_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    job_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    dataset_path = Column(String(500), nullable=True)
    model_save_path = Column(String(500), nullable=True)
    
    status = Column(SQLEnum(TrainingStatus), default=TrainingStatus.PENDING)
    
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=1000)
    batch_size = Column(Integer, default=8)
    learning_rate = Column(Float, default=1e-5)
    
    best_psnr = Column(Float, nullable=True)
    best_ssim = Column(Float, nullable=True)
    best_loss = Column(Float, nullable=True)
    
    loss_history = Column(Text, nullable=True)
    psnr_history = Column(Text, nullable=True)
    
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    owner = relationship("User", back_populates="training_jobs")


class Dataset(Base):
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    path = Column(String(500), nullable=False)
    
    train_count = Column(Integer, default=0)
    val_count = Column(Integer, default=0)
    
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    version_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    model_path = Column(String(500), nullable=False)
    
    trained_epochs = Column(Integer, default=0)
    final_loss = Column(Float, nullable=True)
    final_psnr = Column(Float, nullable=True)
    
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

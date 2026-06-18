"""
模型训练管理 API 路由
支持 Web 界面启动训练、监控进度、管理数据集
"""
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, TrainingJob, TrainingStatus
from app.routers.auth import get_current_active_user
from app.ml import (
    HiNetTrainer, TrainingConfig,
    get_training_status, list_all_training_status
)
from app.schemas import TrainingJobResponse, TrainingProgress

settings = get_settings()
router = APIRouter(prefix="/api/training", tags=["训练"])

_trainers: dict = {}


class TrainingStartRequest(BaseModel):
    job_name: str = "HiNet Training"
    epochs: int = 1000
    batch_size: int = 8
    learning_rate: float = 1e-5
    val_freq: int = 20
    save_freq: int = 20
    dataset_path: Optional[str] = None


def ensure_directories():
    """确保必要的目录存在"""
    os.makedirs(settings.DATASET_DIR, exist_ok=True)
    os.makedirs(settings.MODEL_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.get("/status")
async def get_all_training_status(
    current_user: User = Depends(get_current_active_user)
):
    """
    获取所有训练任务的状态
    
    返回所有训练任务的当前状态、进度、指标等
    """
    status_map = list_all_training_status()
    return {
        "jobs": [
            {
                "job_id": job_id,
                **status
            }
            for job_id, status in status_map.items()
        ]
    }


@router.get("/status/{job_id}")
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取指定训练任务的状态
    """
    status = get_training_status(job_id)
    if status is None:
        if job_id in _trainers:
            trainer = _trainers[job_id]
            return trainer.get_status()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="训练任务不存在"
        )
    return status


@router.post("/start", response_model=TrainingJobResponse)
async def start_training(
    request: TrainingStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    启动训练任务
    
    参数:
        job_name: 任务名称
        epochs: 训练轮数
        batch_size: 批次大小
        learning_rate: 学习率
        val_freq: 验证频率
        save_freq: 保存频率
        dataset_path: 数据集路径 (可选，默认使用标准数据集)
    """
    ensure_directories()
    
    train_path = request.dataset_path or os.path.join(settings.DATASET_DIR, "train")
    val_path = os.path.join(settings.DATASET_DIR, "val")
    
    if not os.path.exists(train_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"训练数据集不存在: {train_path}"
        )
    
    job = TrainingJob(
        user_id=current_user.id,
        job_name=request.job_name,
        dataset_path=train_path,
        status=TrainingStatus.PENDING,
        total_epochs=request.epochs,
        batch_size=request.batch_size,
        learning_rate=request.learning_rate,
        created_at=datetime.utcnow()
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    config = TrainingConfig(
        epochs=request.epochs,
        batch_size=request.batch_size,
        learning_rate=request.learning_rate,
        val_freq=request.val_freq,
        save_freq=request.save_freq
    )
    
    trainer = HiNetTrainer(
        job_id=job.id,
        config=config,
        train_path=train_path,
        val_path=val_path if os.path.exists(val_path) else None,
        model_save_dir=settings.MODEL_DIR
    )
    
    _trainers[job.id] = trainer
    
    trainer.start_training()
    
    job.status = TrainingStatus.RUNNING
    job.started_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    
    return job


@router.post("/stop/{job_id}")
async def stop_training(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    停止指定的训练任务
    """
    if job_id not in _trainers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="训练任务不存在"
        )
    
    trainer = _trainers[job_id]
    trainer.stop_training()
    
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if job:
        job.status = TrainingStatus.STOPPED
        db.commit()
    
    return {"message": f"训练任务 {job_id} 已停止"}


@router.get("/jobs", response_model=List[TrainingJobResponse])
async def list_training_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    列出训练任务历史
    """
    jobs = db.query(TrainingJob).filter(
        TrainingJob.user_id == current_user.id
    ).order_by(
        TrainingJob.created_at.desc()
    ).limit(limit).all()
    
    return jobs


@router.get("/datasets")
async def list_datasets(
    current_user: User = Depends(get_current_active_user)
):
    """
    列出可用的数据集
    """
    ensure_directories()
    
    datasets = []
    dataset_dir = Path(settings.DATASET_DIR)
    
    if dataset_dir.exists():
        for item in dataset_dir.iterdir():
            if item.is_dir():
                train_path = item / "train"
                val_path = item / "val"
                
                train_count = 0
                val_count = 0
                
                if train_path.exists():
                    train_count = len(list(train_path.glob("*")))
                if val_path.exists():
                    val_count = len(list(val_path.glob("*")))
                
                datasets.append({
                    "name": item.name,
                    "path": str(item),
                    "train_count": train_count,
                    "val_count": val_count
                })
    
    return {"datasets": datasets}


@router.post("/datasets/upload")
async def upload_dataset(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    split_ratio: float = Form(default=0.8),
    current_user: User = Depends(get_current_active_user)
):
    """
    上传数据集
    
    参数:
        name: 数据集名称
        files: 图像文件列表
        split_ratio: 训练集比例 (默认 0.8)
    """
    ensure_directories()
    
    dataset_path = Path(settings.DATASET_DIR) / name
    train_path = dataset_path / "train"
    val_path = dataset_path / "val"
    
    if dataset_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="数据集名称已存在"
        )
    
    train_path.mkdir(parents=True, exist_ok=True)
    val_path.mkdir(parents=True, exist_ok=True)
    
    import random
    random.shuffle(files)
    
    split_idx = int(len(files) * split_ratio)
    train_files = files[:split_idx]
    val_files = files[split_idx:]
    
    for i, file in enumerate(train_files):
        ext = Path(file.filename).suffix or ".png"
        save_path = train_path / f"train_{i:04d}{ext}"
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
    
    for i, file in enumerate(val_files):
        ext = Path(file.filename).suffix or ".png"
        save_path = val_path / f"val_{i:04d}{ext}"
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
    
    return {
        "message": "数据集上传成功",
        "name": name,
        "train_count": len(train_files),
        "val_count": len(val_files)
    }


@router.delete("/datasets/{name}")
async def delete_dataset(
    name: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    删除数据集
    """
    dataset_path = Path(settings.DATASET_DIR) / name
    
    if not dataset_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    shutil.rmtree(dataset_path)
    
    return {"message": f"数据集 {name} 已删除"}


@router.get("/models")
async def list_models(
    current_user: User = Depends(get_current_active_user)
):
    """
    列出已保存的模型
    """
    model_dir = Path(settings.MODEL_DIR)
    models = []
    
    if model_dir.exists():
        for item in model_dir.glob("*.pt"):
            stat = item.stat()
            models.append({
                "name": item.name,
                "path": str(item),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    return {"models": models}


@router.get("/models/{model_name}")
async def download_model(
    model_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    下载模型文件
    """
    model_path = Path(settings.MODEL_DIR) / model_name
    
    if not model_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型文件不存在"
        )
    
    return FileResponse(
        path=str(model_path),
        filename=model_name,
        media_type="application/octet-stream"
    )


@router.delete("/models/{model_name}")
async def delete_model(
    model_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    删除模型文件
    """
    model_path = Path(settings.MODEL_DIR) / model_name
    
    if not model_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型文件不存在"
        )
    
    model_path.unlink()
    
    return {"message": f"模型 {model_name} 已删除"}

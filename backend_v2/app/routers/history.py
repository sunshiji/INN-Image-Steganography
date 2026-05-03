"""
历史记录 API 路由
用于管理任务历史记录、图像查看和密钥下载
"""
import io
import json
import os
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path as PathParam
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.config import get_settings
from app.database import get_db
from app.models import User, Task, TaskType
from app.routers.auth import get_current_active_user

settings = get_settings()
router = APIRouter(prefix="/api/history", tags=["历史记录"])


class TaskDetailResponse(BaseModel):
    id: int
    user_id: Optional[int]
    task_type: TaskType
    input_image_path: Optional[str]
    cover_image_path: Optional[str]
    secret_image_path: Optional[str]
    output_image_path: Optional[str]
    parameters: Optional[str]
    psnr: Optional[float]
    ssim: Optional[float]
    entropy_original: Optional[float]
    entropy_encrypted: Optional[float]
    npcr: Optional[float]
    uaci: Optional[float]
    key_data: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: List[TaskDetailResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=TaskListResponse)
async def get_task_list(
    task_type: Optional[str] = Query(None, description="任务类型过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取任务历史记录列表
    
    参数:
        task_type: 任务类型过滤 (encrypt, decrypt, encode, decode)
        page: 页码
        page_size: 每页数量
    
    返回:
        任务列表和总数
    """
    query = db.query(Task).filter(Task.user_id == current_user.id)
    
    if task_type:
        try:
            task_type_enum = TaskType(task_type)
            query = query.filter(Task.task_type == task_type_enum)
        except ValueError:
            pass
    
    total = query.count()
    
    tasks = query.order_by(Task.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return TaskListResponse(
        tasks=[TaskDetailResponse.model_validate(task) for task in tasks],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取任务详情
    
    参数:
        task_id: 任务ID
    
    返回:
        任务详细信息
    """
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    return TaskDetailResponse.model_validate(task)


@router.get("/{task_id}/image/{image_type}")
async def get_task_image(
    task_id: int,
    image_type: str = PathParam(..., description="图像类型: input, cover, secret, output"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取任务相关的图像
    
    参数:
        task_id: 任务ID
        image_type: 图像类型 (input, cover, secret, output)
    
    返回:
        图像文件流
    """
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    image_path_map = {
        "input": task.input_image_path,
        "cover": task.cover_image_path,
        "secret": task.secret_image_path,
        "output": task.output_image_path,
    }
    
    image_path = image_path_map.get(image_type)
    
    if not image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"该任务没有 {image_type} 类型的图像"
        )
    
    full_path = Path(image_path)
    if not full_path.is_absolute():
        full_path = Path(settings.DATA_DIR) / image_path
    
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图像文件不存在"
        )
    
    task_type_str = task.task_type.value if task.task_type else "task"
    
    return FileResponse(
        path=str(full_path),
        media_type="image/png",
        filename=f"{task_type_str}_{task_id}_{image_type}.png"
    )


@router.get("/{task_id}/key/download")
async def download_task_key(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    下载任务密钥
    
    参数:
        task_id: 任务ID
    
    返回:
        密钥文件下载
    """
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if not task.key_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该任务没有保存密钥"
        )
    
    try:
        key_json = json.loads(task.key_data)
        key_str = json.dumps(key_json, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        key_str = task.key_data
    
    key_bytes = key_str.encode("utf-8")
    key_io = io.BytesIO(key_bytes)
    
    task_type_str = task.task_type.value if task.task_type else "task"
    
    return StreamingResponse(
        key_io,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={task_type_str}_key_{task_id}.json"
        }
    )


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    删除任务记录
    
    参数:
        task_id: 任务ID
    
    返回:
        删除结果
    """
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    db.delete(task)
    db.commit()
    
    return {"message": "任务已删除", "task_id": task_id}
